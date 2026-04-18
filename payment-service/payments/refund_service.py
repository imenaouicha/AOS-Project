# payments/refund_service.py

import uuid
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from .models import Transaction, Refund, PaymentStatus, CancellationType, Wallet
from .tasks import process_refund
import logging

logger = logging.getLogger(__name__)

class RefundService:
    """
    Service de calcul et traitement des remboursements
    """
    
    # Pénalités en fonction des heures avant départ
    PENALTY_RULES = {
        'full_refund_hours': 48,      # +48h : remboursement total
        'half_refund_hours': 24,      # 24-48h : remboursement 50%
        'no_refund_hours': 0,         # -24h : pas de remboursement
    }
    
    @classmethod
    def calculate_refund_amount(cls, transaction, hours_before_departure, cancellation_type):
        """
        Calcule le montant à rembourser selon les règles
        
        Args:
            transaction: La transaction de paiement
            hours_before_departure: Heures restantes avant le départ
            cancellation_type: Type d'annulation (passenger/driver/refusal)
        
        Returns:
            dict: {
                'passenger_refund': montant remboursé au passager,
                'driver_compensation': montant pour le conducteur,
                'platform_refund': commission remboursée,
                'percentage': pourcentage remboursé
            }
        """
        total_amount = transaction.amount
        platform_commission = transaction.commission
        driver_amount = transaction.driver_amount
        
        # Cas 1: Conducteur annule ou refuse → remboursement total au passager
        if cancellation_type in [CancellationType.DRIVER, CancellationType.REFUSAL]:
            return {
                'passenger_refund': total_amount,
                'driver_compensation': Decimal('0'),
                'platform_refund': platform_commission,
                'percentage': Decimal('100'),
                'penalty_to_driver': True
            }
        
        # Cas 2: Passager annule → calcul selon délai
        if cancellation_type == CancellationType.PASSENGER:
            if hours_before_departure >= cls.PENALTY_RULES['full_refund_hours']:
                # +48h : remboursement total
                return {
                    'passenger_refund': total_amount,
                    'driver_compensation': Decimal('0'),
                    'platform_refund': platform_commission,
                    'percentage': Decimal('100'),
                    'penalty_to_driver': False
                }
            
            elif hours_before_departure >= cls.PENALTY_RULES['half_refund_hours']:
                # 24-48h : remboursement 50%
                half_amount = total_amount / Decimal('2')
                return {
                    'passenger_refund': half_amount,
                    'driver_compensation': driver_amount / Decimal('2'),
                    'platform_refund': platform_commission / Decimal('2'),
                    'percentage': Decimal('50'),
                    'penalty_to_driver': False
                }
            
            else:
                # -24h : pas de remboursement
                return {
                    'passenger_refund': Decimal('0'),
                    'driver_compensation': driver_amount,
                    'platform_refund': Decimal('0'),
                    'percentage': Decimal('0'),
                    'penalty_to_driver': False
                }
        
        return None
    
    @classmethod
    def process_cancellation_refund(cls, transaction_id, booking_id, cancellation_type, reason, departure_time, cancelled_at=None):
        """
        Traite un remboursement suite à une annulation
        
        Args:
            transaction_id: ID de la transaction
            booking_id: ID de la réservation
            cancellation_type: Type d'annulation
            reason: Raison de l'annulation
            departure_time: Heure de départ prévue
            cancelled_at: Date/heure de l'annulation (default: now)
        """
        from .models import Transaction, Refund, Wallet, RefundStatus
        
        if cancelled_at is None:
            cancelled_at = timezone.now()
        
        try:
            transaction = Transaction.objects.get(id=transaction_id)
            
            # Vérifier que le paiement a été effectué
            if transaction.status != PaymentStatus.COMPLETED:
                return {
                    'success': False,
                    'error': 'Seules les transactions complétées peuvent être remboursées'
                }
            
            # Calculer les heures avant départ
            time_diff = departure_time - cancelled_at
            hours_before = time_diff.total_seconds() / 3600
            
            # Calculer le remboursement
            refund_calc = cls.calculate_refund_amount(transaction, hours_before, cancellation_type)
            
            if refund_calc is None:
                return {'success': False, 'error': 'Type d\'annulation invalide'}
            
            # Créer le remboursement
            refund = Refund.objects.create(
                transaction=transaction,
                booking_id=booking_id,
                amount=refund_calc['passenger_refund'],
                percentage=refund_calc['percentage'],
                cancellation_type=cancellation_type,
                cancellation_reason=reason,
                hours_before_departure=int(hours_before),
                driver_compensation=refund_calc['driver_compensation'],
                platform_fee_returned=refund_calc['platform_refund'],
                status=RefundStatus.PROCESSING
            )
            
            # Rembourser le passager (créditer son wallet)
            if refund_calc['passenger_refund'] > 0:
                wallet, _ = Wallet.objects.get_or_create(user_id=transaction.user_id)
                wallet.add_balance(refund_calc['passenger_refund'])
                logger.info(f"Passager {transaction.user_id} remboursé de {refund_calc['passenger_refund']} DZD")
            
            # Si pénalité conducteur (annulation conducteur)
            if refund_calc.get('penalty_to_driver', False):
                # Déduire une pénalité du wallet du conducteur
                # Ou marquer le conducteur comme pénalisé
                logger.info(f"Conducteur pénalisé pour annulation")
            
            # Mettre à jour le statut
            refund.status = RefundStatus.COMPLETED
            refund.completed_at = timezone.now()
            refund.save()
            
            # Mettre à jour la transaction
            transaction.status = PaymentStatus.REFUNDED
            transaction.save()
            
            # Publier un message RabbitMQ
            cls._publish_refund_message(transaction, refund, refund_calc)
            
            return {
                'success': True,
                'refund_id': str(refund.id),
                'refund_amount': float(refund_calc['passenger_refund']),
                'percentage': float(refund_calc['percentage']),
                'driver_compensation': float(refund_calc['driver_compensation']),
                'hours_before': hours_before
            }
            
        except Transaction.DoesNotExist:
            return {'success': False, 'error': 'Transaction non trouvée'}
        except Exception as e:
            logger.error(f"Erreur remboursement: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def _publish_refund_message(cls, transaction, refund, refund_calc):
        """Publier un message RabbitMQ pour le remboursement"""
        from .consumers import RabbitMQClient
        
        rabbitmq = RabbitMQClient()
        message = {
            'event': 'refund_processed',
            'booking_id': str(refund.booking_id),
            'transaction_id': str(transaction.id),
            'refund_id': str(refund.id),
            'amount': float(refund_calc['passenger_refund']),
            'percentage': float(refund_calc['percentage']),
            'cancellation_type': refund.cancellation_type,
            'timestamp': refund.completed_at.isoformat()
        }
        rabbitmq.publish_message(settings.RABBITMQ_QUEUE_BOOKING, message)