import socket
import requests
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken
from django.http import JsonResponse
from django.utils import timezone
from .models import User, Profile, RefreshToken, UserSession
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer, 
    UserPermissionsSerializer, UserBasicInfoSerializer,
    ProfileSerializer, ChangePasswordSerializer, UserSessionSerializer
)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = JWTRefreshToken.for_user(user)
            UserSession.objects.create(
                user=user,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                is_active=True
            )
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            user.last_login = timezone.now()
            user.save()
            session = UserSession.objects.create(
                user=user,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                is_active=True
            )
            refresh = JWTRefreshToken.for_user(user)
            RefreshToken.objects.create(
                user=user,
                token=str(refresh),
                expires_at=timezone.now() + timezone.timedelta(days=7)
            )
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'session_id': session.id
            })
        return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        session_id = request.data.get('session_id')
        if session_id:
            UserSession.objects.filter(id=session_id, user=request.user).update(
                logout_time=timezone.now(), is_active=False
            )
        refresh_token = request.data.get('refresh')
        if refresh_token:
            RefreshToken.objects.filter(token=refresh_token).update(revoked=True)
        return Response({'message': 'Déconnexion réussie'})


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({
            'user': UserSerializer(request.user).data,
            'profile': ProfileSerializer(request.user.profile).data
        })


class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not user.check_password(serializer.validated_data['old_password']):
                return Response({'old_password': 'Ancien mot de passe incorrect.'}, status=400)
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'message': 'Mot de passe modifié avec succès.'})
        return Response(serializer.errors, status=400)


class MySessionsView(generics.ListAPIView):
    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user, is_active=True)


class UserPermissionsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            return Response({
                'id': user.id,
                'can_publish_trip': user.can_publish_trip(),
                'can_book_trip': user.can_book_trip(),
                'is_blocked': user.is_blocked,
                'is_verified': user.is_verified,
                'role': user.role
            })
        except User.DoesNotExist:
            return Response({'error': 'Utilisateur non trouvé'}, status=404)


class UserBasicInfoView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            profile = user.profile
            return Response({
                'id': user.id,
                'full_name': user.get_full_name(),
                'email': user.email,
                'phone': user.phone,
                'profile_picture': profile.profile_picture.url if profile.profile_picture else None,
                'rating_as_driver': float(profile.rating_as_driver),
                'rating_as_passenger': float(profile.rating_as_passenger)
            })
        except User.DoesNotExist:
            return Response({'error': 'Utilisateur non trouvé'}, status=404)


class HealthCheckView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return JsonResponse({
            "status": "healthy",
            "service": "auth-service",
            "server": socket.gethostbyname(socket.gethostname()),
            "database": "connected",
            "timestamp": timezone.now().isoformat()
        })
        # Ajoutez ces fonctions après vos classes API existantes

def home_page(request):
    return render(request, 'base.html')

def register_page(request):
    return render(request, 'register.html')

def login_page(request):
    return render(request, 'login.html')

@login_required
def profile_page(request):
    return render(request, 'profile.html')

@login_required
def dashboard_page(request):
    return render(request, 'dashboard.html')