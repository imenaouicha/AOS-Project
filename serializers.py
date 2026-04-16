from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, Profile, RefreshToken, UserSession


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            'profile_picture', 'city', 'bio', 'driver_license_number',
            'verification_status', 'rating_as_driver', 'rating_as_passenger',
            'trips_as_driver', 'trips_as_passenger'
        ]
        read_only_fields = ['verification_status', 'rating_as_driver', 'rating_as_passenger']


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'full_name',
            'phone', 'role', 'profile', 'is_verified', 'is_blocked',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'email', 'is_verified', 'is_blocked', 'date_joined', 'last_login']

    def get_full_name(self, obj):
        return obj.get_full_name()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'password', 'password_confirm',
                  'first_name', 'last_name', 'phone', 'role']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Les mots de passe ne correspondent pas."})
        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({"email": "Cet email est déjà utilisé."})
        phone = attrs.get('phone')
        if phone and User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError({"phone": "Ce numéro est déjà utilisé."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        phone = validated_data.pop('phone', None)
        return User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data.get('role', 'passenger'),
            phone=phone
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(email=attrs['email'], password=attrs['password'])
        if not user:
            raise serializers.ValidationError("Email ou mot de passe incorrect.")
        if not user.is_active:
            raise serializers.ValidationError("Ce compte est désactivé.")
        if user.is_blocked:
            raise serializers.ValidationError(f"Compte bloqué : {user.blocked_reason or 'Non spécifiée'}")
        attrs['user'] = user
        return attrs


class UserPermissionsSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    can_publish_trip = serializers.BooleanField()
    can_book_trip = serializers.BooleanField()
    is_blocked = serializers.BooleanField()
    is_verified = serializers.BooleanField()
    role = serializers.CharField()


class UserBasicInfoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField(allow_null=True)
    profile_picture = serializers.CharField(allow_null=True)
    rating_as_driver = serializers.FloatField()
    rating_as_passenger = serializers.FloatField()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Les mots de passe ne correspondent pas."})
        return attrs


class UserSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = ['id', 'ip_address', 'user_agent', 'login_time', 'logout_time', 'is_active']
        read_only_fields = ['id', 'login_time']