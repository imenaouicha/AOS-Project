# payments/tasks.py

import json
import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from .models import Transaction, Wallet, PaymentStatus, Refund
from .invoice import generate_pdf_receipt

logger = logging.getLogger(__name__)


class RabbitMQClient:
    """Client pour interagir avec RabbitMQ"""
    
    def __init__(self):
        try:
            import pika
            self.pika = pika
            self.connection_params = pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                credentials=pika.PlainCredentials(
                    settings.RABBITMQ_USER,
                    settings.RABBITMQ_PASSWORD
                )
            )
        except ImportError:
            logger.warning("pika not installed, RabbitMQ disabled")
            self.pika = None
    
    def connect(self):
        """Établir la connexion à RabbitMQ"""
        if not self.pika:
            return False
            
        try:
            credentials = self.pika.PlainCredentials(
                settings.RABBITMQ_USER, 
                settings.RABBITMQ_PASSWORD
            )
            parameters = self.pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            self.connection = self.pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            logger.info(f"Connecté à RabbitMQ sur {settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}")
            return True
        except Exception as e:
            logger.error(f"Erreur connexion RabbitMQ: {e}")
            return False
    
    def publish_message(self, queue, message, exchange=''):
        """Publier un message dans une queue RabbitMQ"""
        if not self.pika:
            logger.info(f"[SIMULATION] Message publié dans {queue}: {message.get('event', 'unknown')}")
            return True
        
        try:
            if not self.connect():
                return False
            
            # Déclarer la queue (durable pour persistance)
            self.channel.queue_declare(queue=queue, durable=True)
            
            # Publier le message
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=queue,
                body=json.dumps(message, ensure_ascii=False),
                properties=self.pika.BasicProperties(
                    delivery_mode=2,  # Message persistant
                    content_type='application/json'
                )
            )
            
            logger.info(f"Message publié dans {queue}: {message.get('event', 'unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur publication: {e}")
            return False
        finally:
            if hasattr(self, 'connection') and self.connection:
                self.connection.close()
    
    def close(self):
        """Fermer la connexion"""
        if hasattr(self, 'connection') and self.connection and self.connection.is_open:
            self.connection.close()


@shared_task
def process_payment_confirmation(transaction_id):
    """
    Tâche asynchrone pour traiter une confirmation de paiement
    
    Args:
        transaction_id: ID de la transaction à confirmer
    
    Returns:
        dict: Résultat du traitement
    """
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        
        # Vérifier que la transaction est en attente de traitement
        if transaction.status != PaymentStatus.PROCESSING:
            logger.warning(f"Transaction {transaction_id} n'est pas en traitement (statut: {transaction.status})")
            return {
                'success': False, 
                'error': f'Transaction non traitable (statut: {transaction.status})'
            }
        
        # Mettre à jour le statut à COMPLETED
        transaction.status = PaymentStatus.COMPLETED
        transaction.completed_at = timezone.now()
        transaction.save()
        
        logger.info(f"Transaction {transaction_id} confirmée avec succès")
        
        # Générer le reçu PDF
        try:
            receipt_path = generate_pdf_receipt(transaction)
            logger.info(f"Reçu PDF généré: {receipt_path}")
        except Exception as e:
            logger.error(f"Erreur génération PDF: {str(e)}")
            receipt_path = None
        
        # Publier un message pour le Booking Service
        rabbitmq = RabbitMQClient()
        message = {
            'event': 'payment_confirmed',
            'transaction_id': str(transaction.id),
            'booking_id': str(transaction.booking_id) if transaction.booking_id else None,
            'user_id': str(transaction.user_id),
            'amount': float(transaction.amount),
            'commission': float(transaction.commission),
            'driver_amount': float(transaction.driver_amount),
            'status': 'confirmed',
            'timestamp': transaction.completed_at.isoformat()
        }
        
        rabbitmq.publish_message('booking_queue', message)
        
        # Publier un message pour le Notification Service
        notification_message = {
            'event': 'payment_success',
            'user_id': str(transaction.user_id),
            'type': 'email',
            'subject': 'Confirmation de paiement',
            'content': f"""
Votre paiement de {transaction.amount} DZD a été confirmé.
Transaction N°: {transaction.id}
Montant: {transaction.amount} DZD
Commission: {transaction.commission} DZD
            """,
            'receipt_url': f"/api/payments/transactions/{transaction.id}/receipt/"
        }
        
        rabbitmq.publish_message('notification_queue', notification_message)
        
        return {
            'success': True,
            'transaction_id': str(transaction.id),
            'status': transaction.status,
            'receipt_path': receipt_path,
            'amount': float(transaction.amount),
            'commission': float(transaction.commission)
        }
        
    except Transaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} non trouvée")
        return {'success': False, 'error': 'Transaction non trouvée'}
    except Exception as e:
        logger.error(f"Erreur traitement paiement: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def process_wallet_payment(transaction_id):
    """
    Traitement des paiements par portefeuille
    
    Args:
        transaction_id: ID de la transaction
    
    Returns:
        dict: Résultat du traitement
    """
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        wallet = Wallet.objects.get(user_id=transaction.user_id)
        
        if wallet.subtract_balance(transaction.amount):
            # Paiement réussi - appeler la confirmation
            logger.info(f"Paiement wallet réussi pour transaction {transaction_id}")
            result = process_payment_confirmation(transaction_id)
            return result
        else:
            # Solde insuffisant
            transaction.status = PaymentStatus.FAILED
            transaction.failure_reason = "Solde insuffisant"
            transaction.failed_at = timezone.now()
            transaction.save()
            
            logger.warning(f"Solde insuffisant pour transaction {transaction_id}")
            
            # Publier un message d'échec
            rabbitmq = RabbitMQClient()
            message = {
                'event': 'payment_failed',
                'transaction_id': str(transaction.id),
                'booking_id': str(transaction.booking_id) if transaction.booking_id else None,
                'user_id': str(transaction.user_id),
                'reason': 'Solde insuffisant',
                'timestamp': transaction.failed_at.isoformat()
            }
            rabbitmq.publish_message('booking_queue', message)
            
            return {'success': False, 'error': 'Solde insuffisant'}
            
    except Transaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} non trouvée")
        return {'success': False, 'error': 'Transaction non trouvée'}
    except Wallet.DoesNotExist:
        logger.error(f"Wallet non trouvé pour transaction {transaction_id}")
        return {'success': False, 'error': 'Portefeuille non trouvé'}
    except Exception as e:
        logger.error(f"Erreur paiement wallet: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def process_refund(transaction_id, reason):
    """
    Tâche asynchrone pour traiter un remboursement
    
    Args:
        transaction_id: ID de la transaction à rembourser
        reason: Raison du remboursement
    
    Returns:
        dict: Résultat du traitement
    """
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        
        # Vérifier que la transaction peut être remboursée
        if transaction.status != PaymentStatus.COMPLETED:
            raise Exception(f"Seules les transactions complétées peuvent être remboursées (statut: {transaction.status})")
        
        # Calculer le montant à rembourser (sans la commission)
        refund_amount = transaction.amount - transaction.commission
        
        # Mettre à jour le statut de la transaction
        transaction.status = PaymentStatus.REFUNDED
        transaction.save()
        
        # Créer l'enregistrement de remboursement
        refund = Refund.objects.create(
            transaction=transaction,
            amount=refund_amount,
            reason=reason,
            status='completed',
            completed_at=timezone.now()
        )
        
        # Créditer le wallet du passager
        wallet, created = Wallet.objects.get_or_create(user_id=transaction.user_id)
        wallet.add_balance(refund_amount)
        
        logger.info(f"Remboursement effectué pour transaction {transaction_id}: {refund_amount} DZD")
        
        # Publier un message pour le Booking Service
        rabbitmq = RabbitMQClient()
        message = {
            'event': 'payment_refunded',
            'transaction_id': str(transaction.id),
            'booking_id': str(transaction.booking_id) if transaction.booking_id else None,
            'user_id': str(transaction.user_id),
            'amount': float(refund_amount),
            'original_amount': float(transaction.amount),
            'commission': float(transaction.commission),
            'reason': reason,
            'timestamp': refund.completed_at.isoformat()
        }
        
        rabbitmq.publish_message('booking_queue', message)
        
        # Publier une notification
        notification_message = {
            'event': 'payment_refunded',
            'user_id': str(transaction.user_id),
            'type': 'email',
            'subject': 'Remboursement effectué',
            'content': f"""
Votre remboursement de {refund_amount} DZD a été effectué.
Transaction N°: {transaction.id}
Motif: {reason}
Montant remboursé: {refund_amount} DZD
            """
        }
        
        rabbitmq.publish_message('notification_queue', notification_message)
        
        return {
            'success': True,
            'refund_id': str(refund.id),
            'transaction_id': str(transaction.id),
            'amount': float(refund_amount),
            'original_amount': float(transaction.amount),
            'status': 'completed'
        }
        
    except Transaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} non trouvée")
        return {'success': False, 'error': 'Transaction non trouvée'}
    except Exception as e:
        logger.error(f"Erreur remboursement: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def send_payment_receipt_email(transaction_id, email):
    """
    Envoyer le reçu par email (simulé)
    
    Args:
        transaction_id: ID de la transaction
        email: Adresse email du destinataire
    
    Returns:
        dict: Résultat de l'envoi
    """
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        
        # Simuler l'envoi d'email
        logger.info(f"Email envoyé à {email}: Reçu pour transaction {transaction_id}")
        logger.info(f"Montant: {transaction.amount} DZD")
        logger.info(f"Statut: {transaction.status}")
        
        # Dans un vrai projet, vous utiliseriez:
        # from django.core.mail import send_mail
        # send_mail(
        #     subject='Votre reçu de paiement',
        #     message=f'Votre paiement de {transaction.amount} DZD a été confirmé.',
        #     from_email='noreply@covoiturage.dz',
        #     recipient_list=[email],
        #     fail_silently=False,
        # )
        
        return {
            'success': True, 
            'email_sent': email,
            'transaction_id': str(transaction_id)
        }
        
    except Transaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} non trouvée pour envoi email")
        return {'success': False, 'error': 'Transaction non trouvée'}
    except Exception as e:
        logger.error(f"Erreur envoi email: {str(e)}")
        return {'success': False, 'error': str(e)}