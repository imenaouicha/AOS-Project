import requests
import json
from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum
from django.conf import settings
from .models import Booking
from .serializers import BookingSerializer
from .rabbitmq import send_booking_event

# URLs des autres microservices (à configurer dans settings.py)
USERS_SERVICE_URL = getattr(settings, 'USERS_SERVICE_URL', 'http://localhost:8001')
TRIPS_SERVICE_URL = getattr(settings, 'TRIPS_SERVICE_URL', 'http://localhost:8002')
PAYMENT_SERVICE_URL = getattr(settings, 'PAYMENT_SERVICE_URL', 'http://localhost:8003')

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

    def _verify_user_exists(self, user_id):
        """Vérifie que l'utilisateur existe via le microservice Users"""
        try:
            response = requests.get(
                f"{USERS_SERVICE_URL}/users/{user_id}",
                timeout=5
            )
            if response.status_code == 200:
                return True, response.json()
            return False, None
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Erreur appel Users service: {e}")
            return False, None

    def _verify_trip_exists(self, trip_id, seats_requested):
        """Vérifie que le trajet existe et qu'il y a assez de places"""
        try:
            # Vérifier si le trajet existe
            response = requests.get(
                f"{TRIPS_SERVICE_URL}/trips/{trip_id}",
                timeout=5
            )
            if response.status_code != 200:
                return False, None, "Trip not found"
            
            trip_data = response.json()
            max_seats = trip_data.get('max_seats', 6)
            available_seats = trip_data.get('available_seats', max_seats)
            
            # Vérifier les places disponibles
            if seats_requested > available_seats:
                return False, trip_data, f"Only {available_seats} seats available, requested {seats_requested}"
            
            return True, trip_data, None
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Erreur appel Trips service: {e}")
            return False, None, "Trip service unavailable"

    def _process_payment(self, amount, payment_method, card_info=None):
        """Traite le paiement via le microservice Paiement"""
        try:
            payload = {
                "amount": amount,
                "method": payment_method
            }
            if card_info and payment_method == 'card':
                payload["card_info"] = card_info
            
            response = requests.post(
                f"{PAYMENT_SERVICE_URL}/payment/process",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return True, result.get('transaction_id'), None
                else:
                    return False, None, result.get('error', 'Payment failed')
            else:
                return False, None, f"Payment service error: {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Erreur appel Payment service: {e}")
            return False, None, "Payment service unavailable"

    def create(self, request, *args, **kwargs):
        user_id = request.data.get('user_id')
        trip_id = request.data.get('trip_id')
        seats_requested = int(request.data.get('seats_booked', 1))
        payment_method = request.data.get('payment_method', 'card')
        card_info = request.data.get('card_info', None)

        # ============================================
        # 1. VÉRIFICATION : L'utilisateur existe-t-il ?
        # ============================================
        if not user_id or not trip_id:
            return Response(
                {'error': 'user_id and trip_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_exists, user_data = self._verify_user_exists(user_id)
        if not user_exists:
            return Response(
                {'error': f'User {user_id} not found or service unavailable'},
                status=status.HTTP_404_NOT_FOUND
            )
        print(f"✅ Utilisateur vérifié: {user_data.get('name')}")

        # ============================================
        # 2. VÉRIFICATION : Le trajet existe ? Places disponibles ?
        # ============================================
        trip_exists, trip_data, trip_error = self._verify_trip_exists(trip_id, seats_requested)
        if not trip_exists:
            return Response(
                {'error': trip_error},
                status=status.HTTP_400_BAD_REQUEST
            )
        print(f"✅ Trajet vérifié: {trip_data.get('destination')} - {trip_data.get('available_seats')} places restantes")
        
        # ============================================
        # 3. VÉRIFICATION : Paiement
        # ============================================
        # Calcul du montant (si le prix est dans trip_data)
        amount = trip_data.get('price', 25.00) * seats_requested
        
        payment_success, transaction_id, payment_error = self._process_payment(
            amount, payment_method, card_info
        )
        
        if not payment_success:
            return Response(
                {'error': f'Payment failed: {payment_error}'},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )
        print(f"✅ Paiement traité: {transaction_id}")

        # ============================================
        # 4. CRÉATION DE LA RÉSERVATION (avec transaction atomique)
        # ============================================
        with transaction.atomic():
            # Vérification finale des places (concurrence)
            current_seats = Booking.objects.select_for_update().filter(
                trip_id=trip_id
            ).exclude(status='cancelled').aggregate(
                total=Sum('seats_booked')
            )['total'] or 0

            max_seats = trip_data.get('max_seats', 6)
            
            if current_seats + seats_requested > max_seats:
                return Response(
                    {'error': f'No seats available. {current_seats}/{max_seats} seats taken.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Déterminer le statut initial
            # - Paiement carte réussi → confirmed
            # - Paiement espèces → pending (en attente validation conducteur)
            status_initial = 'confirmed' if payment_method == 'card' else 'pending'

            booking = Booking.objects.create(
                user_id=user_id,
                trip_id=trip_id,
                seats_booked=seats_requested,
                status=status_initial
            )
            
            # ============================================
            # 5. RÉSERVER LES PLACES DANS LE SERVICE TRIPS
            # ============================================
            try:
                reserve_response = requests.post(
                    f"{TRIPS_SERVICE_URL}/trips/{trip_id}/reserve",
                    json={"seats": seats_requested},
                    timeout=5
                )
                if reserve_response.status_code != 200:
                    print(f"⚠️ Erreur réservation places dans Trips: {reserve_response.text}")
            except Exception as e:
                print(f"⚠️ Erreur appel Trips reserve: {e}")

        # ============================================
        # 6. ENVOI DE L'ÉVÉNEMENT À RABBITMQ
        # ============================================
        try:
            send_booking_event({
                "event": "booking_created",
                "bookingId": booking.id,
                "userId": booking.user_id,
                "tripId": booking.trip_id,
                "seats": booking.seats_booked,
                "amount": amount,
                "transactionId": transaction_id
            })
            print("✅ Message envoyé à RabbitMQ")
        except Exception as e:
            print(f"⚠️ Erreur RabbitMQ: {e}")

        serializer = BookingSerializer(booking)
        
        # Retourner la réponse avec les détails du paiement
        response_data = serializer.data
        response_data['payment'] = {
            'transaction_id': transaction_id,
            'amount': amount,
            'method': payment_method
        }
        
        return Response(response_data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        """Mise à jour du statut (annulation, confirmation)"""
        try:
            booking = self.get_object()
        except Exception:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        new_status = request.data.get('status')
        old_status = booking.status

        if not new_status:
            return Response(
                {'error': 'status field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_status not in ['pending', 'confirmed', 'cancelled']:
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        booking.status = new_status
        booking.save()

        # Si annulation, libérer les places dans Trips
        if new_status == 'cancelled' and old_status != 'cancelled':
            try:
                # Appeler Trips pour libérer les places
                requests.post(
                    f"{TRIPS_SERVICE_URL}/trips/{booking.trip_id}/cancel",
                    json={"seats": booking.seats_booked},
                    timeout=5
                )
                print(f"✅ Places libérées pour l'annulation du booking {booking.id}")
            except Exception as e:
                print(f"⚠️ Erreur lors de la libération des places: {e}")

        serializer = BookingSerializer(booking)
        return Response(serializer.data, status=status.HTTP_200_OK)