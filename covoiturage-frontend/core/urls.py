from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('publish/', views.publish_trip, name='publish_trip'),
    path('search/', views.search_trips, name='search_trips'),
    path('trip/<int:trip_id>/', views.trip_detail, name='trip_detail'),
    path('booking/<int:trip_id>/confirm/', views.confirm_booking, name='confirm_booking'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
]