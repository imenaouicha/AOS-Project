# payments/views.py - Version COMPLÈTE pour tests Postman
from django.utils import timezone
import logging
import requests
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.conf import settings
from decimal import Decimal

from .models import Transaction, Wallet, PaymentStatus, PaymentMethod
from .serializers import (
    TransactionSerializer, 
    CreatePaymentSerializer, 
    ConfirmPaymentSerializer,
    WalletSerializer, 
    AddBalanceSerializer, 
    RefundSerializer
)
from .invoice import generate_pdf_receipt
from .tasks import process_payment_confirmation, process_refund
from .consumers import RabbitMQClient

logger = logging.getLogger(__name__)

# ============================================================
# HEALTH CHECK
# ============================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check pour Consul"""
    return Response({
        'status': 'healthy',
        'service': 'payment-service',
        'version': '1.0.0',
        'ip': '127.0.0.1'
    })


# ============================================================
# PAYMENT ENDPOINTS
# ============================================================

@api_view(['POST'])
@permission_classes([AllowAny])  # MODIFIÉ POUR TESTS
def create_payment(request):
    """Créer un nouveau paiement avec publication RabbitMQ"""
    serializer = CreatePaymentSerializer(data=request.data)
    if serializer.is_valid():
        try:
            # Pour les tests - user_id fixe
            user_id = "11111111-1111-1111-1111-111111111111"
            
            booking_id = serializer.validated_data['booking_id']
            amount = serializer.validated_data['amount']
            payment_method = serializer.validated_data['payment_method']
            metadata = serializer.validated_data.get('metadata', {})
            
            # Vérifier si un paiement existe déjà
            existing = Transaction.objects.filter(
                booking_id=booking_id,
                status__in=[PaymentStatus.PENDING, PaymentStatus.PROCESSING, PaymentStatus.COMPLETED]
            ).first()
            
            if existing:
                return Response({
                    'success': False,
                    'error': 'Un paiement existe déjà pour cette réservation',
                    'transaction_id': str(existing.id)
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Créer la transaction
            transaction = Transaction.objects.create(
                booking_id=booking_id,
                user_id=user_id,
                amount=amount,
                payment_method=payment_method,
                metadata=metadata,
                status=PaymentStatus.PENDING
            )
            
            # Calculer la commission
            transaction.calculate_commission()
            transaction.save()
            
            # Si paiement par portefeuille, traiter immédiatement
            if payment_method == 'wallet':
                wallet = Wallet.objects.filter(user_id=user_id).first()
                if wallet and wallet.subtract_balance(amount):
                    transaction.status = PaymentStatus.COMPLETED
                    transaction.completed_at = transaction.completed_at.now()
                    transaction.save()
                    
                    # Générer le reçu
                    receipt_path = generate_pdf_receipt(transaction)
                    
                    # Publier le message de confirmation
                    rabbitmq = RabbitMQClient()
                    message = {
                        'event': 'payment_confirmed',
                        'transaction_id': str(transaction.id),
                        'booking_id': str(booking_id),
                        'user_id': str(user_id),
                        'amount': float(amount),
                        'status': 'confirmed',
                        'timestamp': transaction.completed_at.isoformat()
                    }
                    rabbitmq.publish_message('booking_queue', message)
                    
                    return Response({
                        'success': True,
                        'transaction_id': transaction.id,
                        'status': transaction.status,
                        'receipt_url': f"/api/payments/receipt/{transaction.id}/",
                        'message': 'Paiement effectué avec succès'
                    }, status=status.HTTP_200_OK)
                else:
                    transaction.status = PaymentStatus.FAILED
                    transaction.failure_reason = "Solde insuffisant"
                    transaction.save()
                    return Response({
                        'success': False,
                        'error': 'Solde insuffisant dans le portefeuille'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Pour les autres méthodes de paiement, publier un message de création
            rabbitmq = RabbitMQClient()
            message = {
                'event': 'payment_created',
                'transaction_id': str(transaction.id),
                'booking_id': str(booking_id),
                'user_id': str(user_id),
                'amount': float(amount),
                'status': transaction.status,
                'payment_method': payment_method,
                'timestamp': transaction.initiated_at.isoformat()
            }
            
            rabbitmq.publish_message('booking_queue', message)
            
            return Response({
                'success': True,
                'transaction_id': transaction.id,
                'status': transaction.status,
                'message': 'Paiement créé avec succès, en attente de confirmation'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Erreur création paiement: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])  # MODIFIÉ POUR TESTS
def confirm_payment(request):
    """Confirmer un paiement - lance une tâche Celery"""
    serializer = ConfirmPaymentSerializer(data=request.data)
    if serializer.is_valid():
        try:
            transaction = Transaction.objects.get(id=serializer.validated_data['transaction_id'])
            
            # Vérification d'autorisation désactivée pour les tests
            
            # Vérifier que la transaction est en attente
            if transaction.status != PaymentStatus.PENDING:
                return Response({
                    'success': False,
                    'error': f'Cette transaction ne peut pas être confirmée (statut: {transaction.status})'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Changer le statut en processing pour déclencher la tâche
            transaction.status = PaymentStatus.PROCESSING
            transaction.save()
            
            # Lancer la tâche Celery asynchrone
            task = process_payment_confirmation.delay(str(transaction.id))
            
            return Response({
                'success': True,
                'transaction_id': transaction.id,
                'status': 'processing',
                'task_id': task.id,
                'message': 'Paiement en cours de traitement'
            }, status=status.HTTP_200_OK)
            
        except Transaction.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Transaction non trouvée'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Erreur confirmation paiement: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])  # MODIFIÉ POUR TESTS
def get_transaction_history(request):
    """Récupérer l'historique des transactions"""
    # Pour les tests - user_id fixe
    user_id = "11111111-1111-1111-1111-111111111111"
    transactions = Transaction.objects.filter(user_id=user_id).order_by('-initiated_at')
    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])  # MODIFIÉ POUR TESTS
def get_transaction_detail(request, transaction_id):
    """Récupérer les détails d'une transaction"""
    transaction = get_object_or_404(Transaction, id=transaction_id)
    serializer = TransactionSerializer(transaction)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def download_receipt(request, transaction_id):
    """Télécharger le reçu PDF"""
    transaction = get_object_or_404(Transaction, id=transaction_id)
    
    # Générer le reçu
    receipt_path = generate_pdf_receipt(transaction)
    
    # Retourner le fichier
    return FileResponse(
        open(receipt_path, 'rb'),
        as_attachment=True,
        filename=f'recu_paiement_{transaction_id}.pdf'
    )


# ============================================================
# WALLET ENDPOINTS
# ============================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_wallet(request):
    """Récupérer le portefeuille - version test avec user_id fixe"""
    # Pour les tests, on utilise un user_id fixe
    user_id = "11111111-1111-1111-1111-111111111111"
    wallet, created = Wallet.objects.get_or_create(user_id=user_id)
    serializer = WalletSerializer(wallet)
    return Response(serializer.data)



@api_view(['POST'])
@permission_classes([AllowAny])
def add_balance(request):
    """Ajouter du solde au portefeuille"""
    user_id = "11111111-1111-1111-1111-111111111111"
    serializer = AddBalanceSerializer(data=request.data)
    if serializer.is_valid():
        amount = serializer.validated_data['amount']
        wallet, created = Wallet.objects.get_or_create(user_id=user_id)
        wallet.add_balance(amount)
        
        # Créer une transaction de recharge - booking_id peut être None maintenant
        Transaction.objects.create(
            booking_id=None,  # ← Maintenant c'est autorisé
            user_id=user_id,
            amount=amount,
            commission=0,
            driver_amount=amount,
            payment_method='wallet',
            status=PaymentStatus.COMPLETED,
            completed_at=timezone.now(),
            metadata={'type': 'recharge', 'description': 'Recharge de portefeuille'}
        )
        
        return Response({
            'success': True,
            'new_balance': wallet.balance,
            'message': f'{amount} DZD ajoutés avec succès'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# REFUND ENDPOINTS
# ============================================================

@api_view(['POST'])
@permission_classes([AllowAny])  # MODIFIÉ POUR TESTS
def refund_payment(request, transaction_id):
    """Demander un remboursement"""
    try:
        transaction = get_object_or_404(Transaction, id=transaction_id)
        
        # Vérification d'autorisation désactivée pour les tests
        
        # Vérifier que la transaction peut être remboursée
        if transaction.status != PaymentStatus.COMPLETED:
            return Response({
                'error': f'Seules les transactions complétées peuvent être remboursées (statut: {transaction.status})'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        reason = request.data.get('reason', 'Remboursement demandé par l\'utilisateur')
        
        # Lancer la tâche de remboursement asynchrone
        task = process_refund.delay(str(transaction_id), reason)
        
        return Response({
            'success': True,
            'transaction_id': transaction_id,
            'task_id': task.id,
            'message': 'Demande de remboursement en cours de traitement'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur remboursement: {str(e)}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# WEBHOOK ENDPOINTS
# ============================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def webhook_callback(request):
    """Webhook pour les paiements externes (CIB, Edahabia, etc.)"""
    transaction_id = request.data.get('transaction_id')
    status_payment = request.data.get('status')
    external_reference = request.data.get('external_reference')
    
    if not transaction_id:
        return Response({'error': 'transaction_id required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        
        if status_payment == 'success':
            transaction.status = PaymentStatus.PROCESSING
            transaction.transaction_id = external_reference
            transaction.payment_gateway_response = request.data
            transaction.save()
            
            # Lancer la confirmation
            task = process_payment_confirmation.delay(str(transaction.id))
            
            return Response({
                'status': 'ok',
                'task_id': task.id
            }, status=status.HTTP_200_OK)
            
        elif status_payment == 'failed':
            transaction.status = PaymentStatus.FAILED
            transaction.failure_reason = request.data.get('reason', 'Paiement échoué')
            transaction.save()
            
            return Response({'status': 'ok'}, status=status.HTTP_200_OK)
        
        return Response({'status': 'ignored'}, status=status.HTTP_200_OK)
        
    except Transaction.DoesNotExist:
        return Response({'error': 'Transaction not found'}, status=status.HTTP_404_NOT_FOUND)
    from django.shortcuts import render

@api_view(['GET'])
@permission_classes([AllowAny])
def home_page(request):
    return render(request, 'payments/home.html')