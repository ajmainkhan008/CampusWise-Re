
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    RegisterView,
    StudentProfileView,
    ChangePasswordView,
    InternshipAdminStatsView,
    InternshipImportView,
    InternshipDraftListView,
    InternshipDraftDetailView,
    InternshipDraftApproveView,
    InternshipDraftRejectView,
    InternshipAdminManageView,
    InternshipAdminDetailManageView,
    InternshipAdminHistoryView,
    InternshipListView,
    InternshipDetailView,
    InternshipBookmarkToggleView,
    InternshipBookmarkListView,
)

urlpatterns = [
    # Auth
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', StudentProfileView.as_view(), name='student_profile'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change_password'),

    # Admin Internship Management Endpoints
    path('internships/admin/stats/', InternshipAdminStatsView.as_view(), name='internship_admin_stats'),
    path('internships/admin/import/', InternshipImportView.as_view(), name='internship_admin_import'),
    path('internships/admin/drafts/', InternshipDraftListView.as_view(), name='internship_admin_drafts'),
    path('internships/admin/drafts/<int:import_id>/', InternshipDraftDetailView.as_view(), name='internship_admin_draft_detail'),
    path('internships/admin/drafts/<int:import_id>/approve/', InternshipDraftApproveView.as_view(), name='internship_admin_draft_approve'),
    path('internships/admin/drafts/<int:import_id>/reject/', InternshipDraftRejectView.as_view(), name='internship_admin_draft_reject'),
    path('internships/admin/manual/', InternshipAdminManageView.as_view(), name='internship_admin_manual'),
    path('internships/admin/manage/<int:internship_id>/', InternshipAdminDetailManageView.as_view(), name='internship_admin_detail_manage'),
    path('internships/admin/history/', InternshipAdminHistoryView.as_view(), name='internship_admin_history'),

    # Student Internship Endpoints
    path('internships/', InternshipListView.as_view(), name='internship_list'),
    path('internships/<int:internship_id>/', InternshipDetailView.as_view(), name='internship_detail'),
    path('internships/<int:internship_id>/bookmark/', InternshipBookmarkToggleView.as_view(), name='internship_bookmark_toggle'),
    path('internships/bookmarks/', InternshipBookmarkListView.as_view(), name='internship_bookmarks_list'),
]

