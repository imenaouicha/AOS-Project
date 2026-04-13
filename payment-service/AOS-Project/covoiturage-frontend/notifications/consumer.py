import pika
import json
import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

class NotificationConsumer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.connect()
    
    def connect(self):
        try:
            credentials = pika.PlainCredentials(
                settings.RABBITMQ_USER, 
                settings.RABBITMQ_PASSWORD
            )
            parameters = pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                credentials=credentials
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue='notifications', durable=True)
            print("✅ Connected to RabbitMQ")
            logger.info("Connected to RabbitMQ")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            logger.error(f"Connection failed: {e}")
    
    def process_notification(self, ch, method, properties, body):
        try:
            print("📨 Message reçu !")
            data = json.loads(body)
            notification_type = data.get('type')
            print(f"   Type: {notification_type}")
            print(f"   Data: {data}")
            
            if notification_type == 'booking_confirmation':
                print("✉️ Envoi d'email...")
                self.send_booking_confirmation(data)
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print("✅ Message traité avec succès")
        except Exception as e:
            print(f"❌ Error: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def send_booking_confirmation(self, data):
        try:
            subject = f"Booking Confirmation - Trip #{data.get('trip_id')}"
            message = f"""
Hello {data.get('passenger_name')},

Your booking has been confirmed!

Trip Details:
From: {data.get('departure')}
To: {data.get('destination')}
Date: {data.get('date')}
Seats: {data.get('seats')}
Price: {data.get('price')} DA

Thank you!
"""
            print(f"   Email envoyé à: {data.get('email')}")
            # send_mail(subject, message, 'noreply@covoiturage.com', [data.get('email')])
            print("   (Email simulé - décommentez send_mail pour de vrais emails)")
            logger.info(f"Email sent to {data.get('email')}")
        except Exception as e:
            print(f"   Email failed: {e}")
    
    def start_consuming(self):
        if not self.channel:
            self.connect()
        self.channel.basic_consume(queue='notifications', on_message_callback=self.process_notification, auto_ack=False)
        print("🚀 Started consuming notifications...")
        print("   En attente de messages...")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        if self.channel:
            self.channel.stop_consuming()
        if self.connection:
            self.connection.close()
        print("👋 Consumer arrêté")

consumer = NotificationConsumer()