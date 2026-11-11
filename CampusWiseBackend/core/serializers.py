
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, Student


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password]
    )

    department = serializers.CharField(required=False, allow_blank=True)
    batch = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            'id',
            'student_id',
            'email',
            'password',
            'department',
            'batch',
            'role'
        ]
        read_only_fields = ['id', 'role']

    def create(self, validated_data):
        department = validated_data.pop('department', '')
        batch = validated_data.pop('batch', '')

        user = User.objects.create_user(
            **validated_data,
            role='student'
        )

        Student.objects.create(
            user=user,
            department=department,
            batch=batch
        )

        return user


class StudentProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', required=False, allow_blank=True)
    last_name = serializers.CharField(source='user.last_name', required=False, allow_blank=True)
    student_id = serializers.CharField(source='user.student_id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)
    profile_image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Student
        fields = [
            'student_id',
            'first_name',
            'last_name',
            'email',
            'department',
            'batch',
            'section',
            'profile_image',
            'role'
        ]

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})

        instance.user.first_name = user_data.get(
            'first_name', instance.user.first_name
        )
        instance.user.last_name = user_data.get(
            'last_name', instance.user.last_name
        )
        instance.user.save()

        return super().update(instance, validated_data)
