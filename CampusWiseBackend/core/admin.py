
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Student, Event


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
