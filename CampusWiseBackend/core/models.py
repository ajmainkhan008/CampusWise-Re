
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, student_id, email, password=None, **extra_fields):
        if not student_id:
            raise ValueError("Student ID is required")

        email = self.normalize_email(email)

        user = self.model(
            student_id=student_id,
            email=email,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, student_id, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(
            student_id,
            email,
            password,
            **extra_fields
        )


class User(AbstractUser):
    username = None

    student_id = models.CharField(max_length=20, unique=True)
    email = models.EmailField(unique=True)

    ROLE_CHOICES = [
        ('student', 'Student'),
        ('admin', 'Admin'),
    ]

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='student'
    )

    USERNAME_FIELD = 'student_id'
    REQUIRED_FIELDS = ['email']

    objects = UserManager()

    def __str__(self):
        return self.student_id


class Student(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='student_profile'
    )

    department = models.CharField(max_length=100, blank=True)
    batch = models.CharField(max_length=30, blank=True)
    section = models.CharField(max_length=30, blank=True)

    profile_image = models.ImageField(
        upload_to='student_profiles/',
        blank=True,
        null=True
    )

    def __str__(self):
        return self.user.student_id


class Event(models.Model):
    VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('students', 'Students Only'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    date = models.DateTimeField()
    location = models.CharField(max_length=200)

    visibility = models.CharField(
        max_length=10,
        choices=VISIBILITY_CHOICES,
        default='students'
    )

    is_published = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class InternshipImport(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    EXTRACTION_STATUS_CHOICES = [
        ('success', 'Success'),
        ('partial', 'Partial / Manual Needed'),
        ('failed', 'Failed'),
        ('not_internship', 'Not an Internship'),
    ]

    email_subject = models.CharField(max_length=255)
    sender_email = models.EmailField(blank=True)
    original_email_content = models.TextField()
    source_link = models.URLField(max_length=500, blank=True)
    content_hash = models.CharField(max_length=64, db_index=True)
    import_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    extraction_status = models.CharField(max_length=20, choices=EXTRACTION_STATUS_CHOICES, default='success')
    extraction_result = models.JSONField(default=dict, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='imported_notices'
    )
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_imports'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email_subject} ({self.get_import_status_display()})"


class Internship(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]
    VISIBILITY_CHOICES = [
        ('students', 'Students Only'),
        ('public', 'Public'),
    ]

    import_record = models.OneToOneField(
        InternshipImport, on_delete=models.SET_NULL, null=True, blank=True, related_name='internship'
    )
    company_name = models.CharField(max_length=200, db_index=True)
    company_logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    position = models.CharField(max_length=200, db_index=True)
    description = models.TextField()
    eligibility = models.TextField(blank=True)
    required_skills = models.JSONField(default=list, blank=True)
    location = models.CharField(max_length=200, blank=True)
    employment_type = models.CharField(max_length=50, blank=True, default='On-site')
    stipend = models.CharField(max_length=100, blank=True)
    application_deadline = models.DateField(null=True, blank=True, db_index=True)
    application_url = models.URLField(max_length=500, blank=True)
    application_email = models.EmailField(blank=True)
    application_instructions = models.TextField(blank=True)
    source_link = models.URLField(max_length=500, blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='students')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_internships'
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_internships'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']

    def is_expired(self):
        from django.utils import timezone
        from django.utils.dateparse import parse_date
        import datetime
        if not self.application_deadline:
            return False
        dl = self.application_deadline
        if isinstance(dl, str):
            dl = parse_date(dl)
        elif isinstance(dl, datetime.datetime):
            dl = dl.date()
        if dl:
            return dl < timezone.now().date()
        return False

    def check_and_update_expiry(self):
        if self.status == 'open' and self.is_expired():
            self.status = 'closed'
            self.save(update_fields=['status', 'updated_at'])
            return True
        return False

    def save(self, *args, **kwargs):
        if self.is_expired():
            self.status = 'closed'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.position} at {self.company_name}"


class InternshipBookmark(models.Model):
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='internship_bookmarks'
    )
    internship = models.ForeignKey(
        Internship, on_delete=models.CASCADE, related_name='bookmarked_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'internship')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.student_id} - {self.internship.position}"


class InternshipReviewLog(models.Model):
    ACTION_CHOICES = [
        ('imported', 'Imported'),
        ('extracted', 'Extracted with Gemini'),
        ('edited', 'Edited'),
        ('approved', 'Approved & Published'),
        ('rejected', 'Rejected'),
        ('status_changed', 'Status Changed'),
        ('deleted', 'Deleted'),
    ]

    internship_import = models.ForeignKey(
        InternshipImport, on_delete=models.CASCADE, related_name='review_logs', null=True, blank=True
    )
    internship = models.ForeignKey(
        Internship, on_delete=models.CASCADE, related_name='review_logs', null=True, blank=True
    )
    admin = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='admin_review_logs'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.admin.student_id} - {self.action} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"

