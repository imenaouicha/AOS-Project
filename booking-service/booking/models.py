from django.db import models

class Booking(models.Model):
    user_id = models.IntegerField()
    trip_id = models.IntegerField()
    status_choices = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled')
    ]
    seats_booked = models.IntegerField(default=1)
    status = models.CharField(max_length=10, choices=status_choices, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
       return "Booking " + str(self.id)