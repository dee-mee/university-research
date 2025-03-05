from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import Profile

# class RegisterSerializer(serializers.ModelSerializer):
#     first_name = serializers.CharField(required=True)
#     middle_name = serializers.CharField(required=True)
#     last_name = serializers.CharField(required=True)
#     phone_number = serializers.CharField(required=True)
#     id_number = serializers.CharField(required=True)
#     dob = serializers.DateField(required=True)
#     gender = serializers.ChoiceField(choices=[('male', 'Male'), ('female', 'Female')])
#     email = serializers.EmailField(required=True)
#     password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
#     password2 = serializers.CharField(write_only=True, required=True)

#     class Meta:
#         model = User
#         fields = ('first_name', 'middle_name', 'last_name', 'phone_number', 'id_number', 'dob', 'gender', 'email', 'password', 'password2')

#     def validate_id_number(self, value):
#         if Profile.objects.filter(id_number=value).exists():
#             raise serializers.ValidationError("A user with that ID number already exists.")
#         return value

#     def validate_phone_number(self, value):
#         if Profile.objects.filter(phone_number=value).exists():
#             raise serializers.ValidationError("A user with that phone number already exists.")
#         return value

#     def validate_email(self, value):
#         if User.objects.filter(email=value).exists():
#             raise serializers.ValidationError("A user with that email already exists.")
#         return value

#     def validate(self, attrs):
#         if attrs['password'] != attrs['password2']:
#             raise serializers.ValidationError({"password": "Password fields didn't match."})
#         return attrs

#     def create(self, validated_data):
#         user = User.objects.create(
#             username=validated_data['email'],  # Set username to email
#             email=validated_data['email'],
#             first_name=validated_data['first_name'],
#             last_name=validated_data['last_name']
#         )
#         user.set_password(validated_data['password'])
#         user.save()
#         Profile.objects.create(
#             user=user,
#             middle_name=validated_data['middle_name'],
#             phone_number=validated_data['phone_number'],
#             id_number=validated_data['id_number'],
#             dob=validated_data['dob'],
#             gender=validated_data['gender']
#         )
#         return user

# serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import Profile

class RegisterSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(required=True, max_length=30)
    middle_name = serializers.CharField(required=False, max_length=30, allow_blank=True)
    last_name = serializers.CharField(required=True, max_length=30)
    phone_number = serializers.CharField(required=True, max_length=15)
    id_number = serializers.CharField(required=True, max_length=20)
    dob = serializers.DateField(required=True)
    gender = serializers.ChoiceField(choices=[('male', 'Male'), ('female', 'Female')])
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = (
            'first_name', 'middle_name', 'last_name', 'phone_number', 
            'id_number', 'dob', 'gender', 'email', 
            'password', 'password2'
        )

    def validate_id_number(self, value):
        if Profile.objects.filter(id_number=value).exists():
            raise serializers.ValidationError("A user with that ID number already exists.")
        return value

    def validate_phone_number(self, value):
        if Profile.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A user with that phone number already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        # Remove non-User model fields
        validated_data.pop('password2')
        middle_name = validated_data.pop('middle_name', '')

        try:
            # Create User
            user = User.objects.create(
                username=validated_data['email'],
                email=validated_data['email'],
                first_name=validated_data['first_name'],
                last_name=validated_data['last_name']
            )
            user.set_password(validated_data['password'])
            user.save()

            # Create Profile
            Profile.objects.create(
                user=user,
                middle_name=middle_name,
                phone_number=validated_data['phone_number'],
                id_number=validated_data['id_number'],
                dob=validated_data['dob'],
                gender=validated_data['gender']
            )

            return user
        except Exception as e:
            # If user creation fails, rollback the transaction
            user.delete()
            raise serializers.ValidationError(str(e))
        
class LoginSerializer(serializers.Serializer):
    id_number = serializers.CharField()
    password = serializers.CharField()

class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()