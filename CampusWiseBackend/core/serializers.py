
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import (
    User,
    Student,
    Internship,
    InternshipImport,
    InternshipBookmark,
    InternshipReviewLog,
)


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


class InternshipSerializer(serializers.ModelSerializer):
    is_bookmarked = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()

    class Meta:
        model = Internship
        fields = [
            'id',
            'company_name',
            'company_logo',
            'position',
            'description',
            'eligibility',
            'required_skills',
            'location',
            'employment_type',
            'stipend',
            'application_deadline',
            'application_url',
            'application_email',
            'application_instructions',
            'source_link',
            'visibility',
            'status',
            'published_at',
            'is_bookmarked',
            'is_expired',
            'days_left',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'published_at', 'created_at', 'updated_at']

    def get_is_bookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return InternshipBookmark.objects.filter(student=request.user, internship=obj).exists()
        return False

    def get_is_expired(self, obj):
        return obj.is_expired()

    def get_days_left(self, obj):
        if not obj.application_deadline:
            return None
        from django.utils import timezone
        from django.utils.dateparse import parse_date
        import datetime
        dl = obj.application_deadline
        if isinstance(dl, str):
            dl = parse_date(dl)
        elif isinstance(dl, datetime.datetime):
            dl = dl.date()
        if not dl:
            return None
        diff = (dl - timezone.now().date()).days
        return max(0, diff)


class InternshipImportSerializer(serializers.ModelSerializer):
    internship_id = serializers.SerializerMethodField()
    created_by_id = serializers.CharField(source='created_by.student_id', read_only=True)
    reviewed_by_id = serializers.CharField(source='reviewed_by.student_id', read_only=True)

    class Meta:
        model = InternshipImport
        fields = [
            'id',
            'email_subject',
            'sender_email',
            'original_email_content',
            'source_link',
            'content_hash',
            'import_status',
            'extraction_status',
            'extraction_result',
            'rejection_reason',
            'created_by_id',
            'reviewed_by_id',
            'reviewed_at',
            'created_at',
            'updated_at',
            'internship_id',
        ]
        read_only_fields = ['id', 'content_hash', 'created_at', 'updated_at']

    def get_internship_id(self, obj):
        if hasattr(obj, 'internship') and obj.internship:
            return obj.internship.id
        return None


class InternshipBookmarkSerializer(serializers.ModelSerializer):
    internship = InternshipSerializer(read_only=True)

    class Meta:
        model = InternshipBookmark
        fields = ['id', 'internship', 'created_at']
        read_only_fields = ['id', 'created_at']


class InternshipReviewLogSerializer(serializers.ModelSerializer):
    admin_id = serializers.CharField(source='admin.student_id', read_only=True)

    class Meta:
        model = InternshipReviewLog
        fields = ['id', 'action', 'remarks', 'admin_id', 'created_at']
        read_only_fields = ['id', 'created_at']

