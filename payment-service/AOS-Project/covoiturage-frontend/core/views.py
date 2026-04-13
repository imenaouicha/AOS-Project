import requests
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings

def home(request):
    return render(request, 'index.html')

def register(request):
    if request.method == 'POST':
        user_data = {
            'username': request.POST.get('username'),
            'email': request.POST.get('email'),
            'password': request.POST.get('password'),
            'first_name': request.POST.get('first_name'),
            'last_name': request.POST.get('last_name'),
            'role': request.POST.get('role', 'passenger')
        }
        
        try:
            response = requests.post(
                f"{settings.AUTH_SERVICE_URL}/api/auth/register/",
                json=user_data
            )
            if response.status_code == 201:
                messages.success(request, 'Registration successful! Please login.')
                return redirect('login')
            else:
                messages.error(request, 'Registration failed')
        except Exception as e:
            messages.error(request, f'Service unavailable: {str(e)}')
    
    return render(request, 'register.html')

def login_view(request):
    if request.method == 'POST':
        credentials = {
            'username': request.POST.get('username'),
            'password': request.POST.get('password')
        }
        
        try:
            response = requests.post(
                f"{settings.AUTH_SERVICE_URL}/api/auth/login/",
                json=credentials
            )
            if response.status_code == 200:
                data = response.json()
                request.session['access_token'] = data.get('access')
                request.session['refresh_token'] = data.get('refresh')
                request.session['user'] = data.get('user')
                messages.success(request, 'Login successful!')
                return redirect('home')
            else:
                messages.error(request, 'Invalid credentials')
        except Exception as e:
            messages.error(request, f'Service unavailable: {str(e)}')
    
    return render(request, 'login.html')

def logout_view(request):
    request.session.flush()
    messages.success(request, 'Logged out successfully')
    return redirect('home')

def profile(request):
    if not request.session.get('access_token'):
        messages.error(request, 'Please login first')
        return redirect('login')
    
    try:
        headers = {'Authorization': f"Bearer {request.session['access_token']}"}
        response = requests.get(
            f"{settings.AUTH_SERVICE_URL}/api/auth/profile/",
            headers=headers
        )
        if response.status_code == 200:
            user_data = response.json()
            return render(request, 'profile.html', {'user': user_data})
        else:
            messages.error(request, 'Failed to fetch profile')
            return redirect('home')
    except Exception as e:
        messages.error(request, f'Service unavailable: {str(e)}')
        return redirect('home')

def publish_trip(request):
    if not request.session.get('access_token'):
        messages.error(request, 'Please login first')
        return redirect('login')
    
    if request.method == 'POST':
        trip_data = {
            'departure': request.POST.get('departure'),
            'destination': request.POST.get('destination'),
            'departure_date': request.POST.get('departure_date'),
            'departure_time': request.POST.get('departure_time'),
            'available_seats': int(request.POST.get('available_seats')),
            'price_per_seat': float(request.POST.get('price_per_seat')),
            'description': request.POST.get('description'),
        }
        
        try:
            headers = {'Authorization': f"Bearer {request.session['access_token']}"}
            response = requests.post(
                f"{settings.TRIP_SERVICE_URL}/api/trips/",
                json=trip_data,
                headers=headers
            )
            if response.status_code == 201:
                messages.success(request, 'Trip published successfully!')
                return redirect('home')
            else:
                messages.error(request, 'Failed to publish trip')
        except Exception as e:
            messages.error(request, f'Trip service unavailable: {str(e)}')
    
    return render(request, 'publish.html')

def search_trips(request):
    trips = []
    if request.GET.get('departure'):
        params = {
            'departure': request.GET.get('departure'),
            'destination': request.GET.get('destination'),
            'date': request.GET.get('date')
        }
        
        try:
            response = requests.get(
                f"{settings.TRIP_SERVICE_URL}/api/trips/search/",
                params=params
            )
            if response.status_code == 200:
                trips = response.json()
        except Exception as e:
            messages.error(request, f'Trip service unavailable: {str(e)}')
    
    return render(request, 'search.html', {'trips': trips})

def trip_detail(request, trip_id):
    try:
        response = requests.get(f"{settings.TRIP_SERVICE_URL}/api/trips/{trip_id}/")
        if response.status_code == 200:
            trip = response.json()
            return render(request, 'trip_detail.html', {'trip': trip})
        else:
            messages.error(request, 'Trip not found')
            return redirect('search')
    except Exception as e:
        messages.error(request, f'Trip service unavailable: {str(e)}')
        return redirect('search')

def confirm_booking(request, trip_id):
    if not request.session.get('access_token'):
        return redirect('login')
    
    if request.method == 'POST':
        booking_data = {
            'trip_id': trip_id,
            'seats_booked': int(request.POST.get('seats', 1))
        }
        
        try:
            headers = {'Authorization': f"Bearer {request.session['access_token']}"}
            response = requests.post(
                f"{settings.BOOKING_SERVICE_URL}/api/bookings/",
                json=booking_data,
                headers=headers
            )
            if response.status_code == 201:
                messages.success(request, 'Booking confirmed!')
                return redirect('my_bookings')
            else:
                messages.error(request, 'Booking failed')
        except Exception as e:
            messages.error(request, f'Booking service unavailable: {str(e)}')
    
    return redirect('trip_detail', trip_id=trip_id)

def my_bookings(request):
    if not request.session.get('access_token'):
        messages.error(request, 'Please login first')
        return redirect('login')
    
    bookings = []
    try:
        headers = {'Authorization': f"Bearer {request.session['access_token']}"}
        response = requests.get(
            f"{settings.BOOKING_SERVICE_URL}/api/bookings/my-bookings/",
            headers=headers
        )
        if response.status_code == 200:
            bookings = response.json()
    except Exception as e:
        messages.error(request, f'Booking service unavailable: {str(e)}')
    
    return render(request, 'my_bookings.html', {'bookings': bookings})

def admin_dashboard(request):
    if not request.session.get('access_token'):
        messages.error(request, 'Please login first')
        return redirect('login')
    
    user = request.session.get('user', {})
    if user.get('role') != 'admin':
        messages.error(request, 'Access denied')
        return redirect('home')
    
    stats = {}
    try:
        headers = {'Authorization': f"Bearer {request.session['access_token']}"}
        response = requests.get(
            f"{settings.TRIP_SERVICE_URL}/api/trips/stats/",
            headers=headers
        )
        if response.status_code == 200:
            stats['trips'] = response.json()
    except Exception as e:
        messages.error(request, f'Error fetching stats: {str(e)}')
    
    return render(request, 'admin_dashboard.html', {'stats': stats})