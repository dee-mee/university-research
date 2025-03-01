from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import Profile

class RegisterSerializer(serializers.ModelSerializer):
    reg_number = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('reg_number', 'password', 'password2', 'email')

    def validate_reg_number(self, value):
        if Profile.objects.filter(reg_number=value).exists():
            raise serializers.ValidationError("A user with that registration number already exists.")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        user = User.objects.create(
            username=validated_data['email'],  # Set username to email
            email=validated_data['email']
        )
        user.set_password(validated_data['password'])
        user.save()
        Profile.objects.create(user=user, reg_number=validated_data['reg_number'])
        return user

class LoginSerializer(serializers.Serializer):
    reg_number = serializers.CharField()
    password = serializers.CharField()

class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()