import pika
import json

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.queue_declare(queue='notifications', durable=True)

message = {
    "type": "booking_confirmation",
    "trip_id": 999,
    "passenger_name": "Test User",
    "departure": "Alger",
    "destination": "Oran",
    "date": "2026-04-01",
    "time": "14:00",
    "seats": 2,
    "price": 500,
    "email": "test@example.com"
}

channel.basic_publish(
    exchange='',
    routing_key='notifications',
    body=json.dumps(message),
    properties=pika.BasicProperties(delivery_mode=2)
)

print("✅ Message envoyé à RabbitMQ !")
connection.close()