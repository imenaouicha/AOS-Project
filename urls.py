from django.urls import path
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    # Pages HTML
    path('', TemplateView.as_view(template_name='base.html'), name='home'),
    path('register/', TemplateView.as_view(template_name='register.html'), name='register'),
    path('login/', TemplateView.as_view(template_name='login.html'), name='login'),
    path('profile/', TemplateView.as_view(template_name='profile.html'), name='profile'),
    path('trips/', TemplateView.as_view(template_name='trips.html'), name='trips'),
    
    # APIs
    path('api/auth/register/', views.RegisterView.as_view(), name='api_register'),
    path('api/auth/login/', views.LoginView.as_view(), name='api_login'),
    path('api/auth/logout/', views.LogoutView.as_view(), name='api_logout'),
    path('api/auth/profile/', views.ProfileView.as_view(), name='api_profile'),
    path('api/auth/change-password/', views.ChangePasswordView.as_view(), name='api_change_password'),
    path('api/auth/sessions/', views.MySessionsView.as_view(), name='api_sessions'),
    path('api/auth/health/', views.HealthCheckView.as_view(), name='api_health'),
    path('api/auth/users/<int:user_id>/permissions/', views.UserPermissionsView.as_view(), name='api_user_permissions'),
    path('api/auth/users/<int:user_id>/basic/', views.UserBasicInfoView.as_view(), name='api_user_basic'),
]