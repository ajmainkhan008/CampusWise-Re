
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User,
    Student,
    Event,
    Internship,
    InternshipImport,
    InternshipBookmark,
    InternshipReviewLog,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('student_id', 'password')}),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('CampusWise', {'fields': ('role',)}),
        ('Permissions', {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions'
            )
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined')
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'student_id',
                'email',
                'password1',
                'password2',
                'role',
                'is_staff',
                'is_superuser'
            ),
        }),
    )

    list_display = ('student_id', 'email', 'role', 'is_staff')
    search_fields = ('student_id', 'email')
    ordering = ('student_id',)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'batch')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'location', 'visibility', 'is_published')
    list_filter = ('visibility', 'is_published')
    search_fields = ('title', 'location')


@admin.register(Internship)
class InternshipAdmin(admin.ModelAdmin):
    list_display = ('position', 'company_name', 'location', 'employment_type', 'status', 'application_deadline', 'published_at')
    list_filter = ('status', 'employment_type', 'visibility')
    search_fields = ('position', 'company_name', 'location', 'description')
    ordering = ('-published_at', '-created_at')


@admin.register(InternshipImport)
class InternshipImportAdmin(admin.ModelAdmin):
    list_display = ('email_subject', 'sender_email', 'import_status', 'extraction_status', 'created_at')
    list_filter = ('import_status', 'extraction_status')
    search_fields = ('email_subject', 'sender_email', 'original_email_content')
    ordering = ('-created_at',)


@admin.register(InternshipBookmark)
class InternshipBookmarkAdmin(admin.ModelAdmin):
    list_display = ('student', 'internship', 'created_at')
    search_fields = ('student__student_id', 'internship__position', 'internship__company_name')


@admin.register(InternshipReviewLog)
class InternshipReviewLogAdmin(admin.ModelAdmin):
    list_display = ('admin', 'action', 'created_at')
    list_filter = ('action',)
    search_fields = ('admin__student_id', 'remarks')

