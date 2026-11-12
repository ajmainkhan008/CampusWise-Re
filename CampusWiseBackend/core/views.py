
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Q, Count

from .serializers import (
    RegisterSerializer,
    StudentProfileSerializer,
    InternshipSerializer,
    InternshipImportSerializer,
    InternshipBookmarkSerializer,
    InternshipReviewLogSerializer,
)
from .models import (
    Student,
    Internship,
    InternshipImport,
    InternshipBookmark,
    InternshipReviewLog,
)
from services.gemini_extraction import (
    compute_content_hash,
    extract_internship_with_gemini,
    sanitize_input_text,
)


class IsAdminUserRole(BasePermission):
    """Allows access only to authenticated admin users."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'admin'
        )


class IsStudentOrAdmin(BasePermission):
    """Allows access to authenticated students and admins."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['student', 'admin']
        )



class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class StudentProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        student, created = Student.objects.get_or_create(
            user=request.user
        )

        serializer = StudentProfileSerializer(
            student,
            context={'request': request}
        )

        return Response(serializer.data)

    def patch(self, request):
        student, created = Student.objects.get_or_create(
            user=request.user
        )

        serializer = StudentProfileSerializer(
            student,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not old_password or not new_password:
            return Response(
                {'error': 'Both passwords are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user

        if not user.check_password(old_password):
            return Response(
                {'error': 'Current password is incorrect.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from django.contrib.auth.password_validation import validate_password
            validate_password(new_password, user)

        except ValidationError as error:
            return Response(
                {'error': list(error.messages)},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()

        return Response({
            'message': 'Password changed successfully.'
        })


# ==========================================
# ADMIN INTERNSHIP MANAGEMENT ENDPOINTS
# ==========================================

class InternshipAdminStatsView(APIView):
    """
    Returns high-level statistics for the admin dashboard (FR-37/FR-39).
    """
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        today = timezone.now().date()
        # Automatically update any open internships whose deadline has passed
        Internship.objects.filter(status='open', application_deadline__lt=today).update(
            status='closed', updated_at=timezone.now()
        )

        total = Internship.objects.count()
        published = Internship.objects.filter(status='open').count()
        closed = Internship.objects.filter(status='closed').count()
        pending_review = InternshipImport.objects.filter(import_status='pending').count()
        rejected = InternshipImport.objects.filter(import_status='rejected').count()

        return Response({
            'total_internships': total,
            'published_internships': published,
            'pending_review': pending_review,
            'closed_internships': closed,
            'rejected_imports': rejected,
        })


class InternshipImportView(APIView):
    """
    Admin imports CDC email content. Extracts structured data using Gemini (FR-37, FR-38, FR-58).
    """
    permission_classes = [IsAdminUserRole]
    parser_classes = [JSONParser]

    def post(self, request):
        email_subject = request.data.get('email_subject', '').strip()
        sender_email = request.data.get('sender_email', '').strip()
        original_email_content = request.data.get('original_email_content', '').strip()
        source_link = request.data.get('source_link', '').strip()
        allow_duplicate = request.data.get('allow_duplicate', False)

        if not email_subject:
            return Response(
                {'error': 'Email subject is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not original_email_content or len(original_email_content) < 20:
            return Response(
                {'error': 'Original CDC email content is required (minimum 20 characters).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Duplicate detection (FR-38)
        content_hash = compute_content_hash(original_email_content)
        existing = InternshipImport.objects.filter(content_hash=content_hash).first()
        if existing and not allow_duplicate:
            return Response({
                'duplicate': True,
                'existing_id': existing.id,
                'existing_subject': existing.email_subject,
                'existing_status': existing.import_status,
                'message': 'Duplicate notice detected. This email content has already been imported.'
            }, status=status.HTTP_409_CONFLICT)

        # Call Gemini extraction service (FR-58)
        extraction_status, extracted_data = extract_internship_with_gemini(
            email_subject=email_subject,
            email_content=original_email_content,
            source_link=source_link
        )

        import_record = InternshipImport.objects.create(
            email_subject=email_subject,
            sender_email=sender_email,
            original_email_content=original_email_content,
            source_link=source_link,
            content_hash=content_hash,
            import_status='pending',
            extraction_status=extraction_status,
            extraction_result=extracted_data,
            created_by=request.user
        )

        # Audit review log
        InternshipReviewLog.objects.create(
            internship_import=import_record,
            admin=request.user,
            action='imported',
            remarks=f"Imported with status: {extraction_status}"
        )

        serializer = InternshipImportSerializer(import_record)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class InternshipDraftListView(APIView):
    """
    Lists pending drafts awaiting review (FR-39).
    """
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        drafts = InternshipImport.objects.filter(import_status='pending').order_by('-created_at')
        serializer = InternshipImportSerializer(drafts, many=True)
        return Response(serializer.data)


class InternshipDraftDetailView(APIView):
    """
    Retrieve or edit a specific draft (FR-39).
    """
    permission_classes = [IsAdminUserRole]

    def get(self, request, import_id):
        try:
            draft = InternshipImport.objects.get(pk=import_id)
        except InternshipImport.DoesNotExist:
            return Response({'error': 'Draft not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = InternshipImportSerializer(draft)
        return Response(serializer.data)

    def patch(self, request, import_id):
        try:
            draft = InternshipImport.objects.get(pk=import_id)
        except InternshipImport.DoesNotExist:
            return Response({'error': 'Draft not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Allow updating extracted fields
        updated_extraction = request.data.get('extraction_result', draft.extraction_result)
        if isinstance(updated_extraction, dict):
            draft.extraction_result = updated_extraction

        if 'email_subject' in request.data:
            draft.email_subject = request.data['email_subject']
        if 'source_link' in request.data:
            draft.source_link = request.data['source_link']

        draft.save()

        InternshipReviewLog.objects.create(
            internship_import=draft,
            admin=request.user,
            action='edited',
            remarks="Admin updated draft extraction fields."
        )

        serializer = InternshipImportSerializer(draft)
        return Response(serializer.data)


class InternshipDraftApproveView(APIView):
    """
    Approves draft, creates published Internship record (FR-39, FR-40).
    """
    permission_classes = [IsAdminUserRole]

    def post(self, request, import_id):
        try:
            draft = InternshipImport.objects.get(pk=import_id)
        except InternshipImport.DoesNotExist:
            return Response({'error': 'Draft not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Admin can pass final field overrides or use draft.extraction_result
        fields = request.data.get('fields', draft.extraction_result or {})

        # Enforce validation for non-internship classifications (Scenario 4)
        if draft.extraction_status == 'not_internship':
            is_correction = request.data.get('is_internship_correction', False) or fields.get('is_internship', False)
            if not is_correction:
                return Response(
                    {'error': 'This notice was classified as not an internship. Administrative correction (setting is_internship_correction=True) is required to approve it as an internship.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        company_name = fields.get('company_name', '').strip()
        position = fields.get('position', '').strip()
        description = fields.get('description', '').strip()

        if not company_name or not position or not description:
            return Response(
                {'error': 'Company name, position, and description are required for approval.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        deadline = fields.get('application_deadline') or None
        if deadline == '':
            deadline = None

        today = timezone.now().date()
        parsed_dl = None
        if deadline:
            parsed_dl = parse_date(str(deadline)) if isinstance(deadline, str) else deadline

        initial_status = 'closed' if (parsed_dl and parsed_dl < today) else 'open'

        with transaction.atomic():
            # Create or update Internship
            internship, _ = Internship.objects.update_or_create(
                import_record=draft,
                defaults={
                    'company_name': company_name,
                    'position': position,
                    'description': description,
                    'eligibility': fields.get('eligibility', ''),
                    'required_skills': fields.get('required_skills', []),
                    'location': fields.get('location', ''),
                    'employment_type': fields.get('employment_type', 'On-site') or 'On-site',
                    'stipend': fields.get('stipend', ''),
                    'application_deadline': deadline,
                    'application_url': fields.get('application_url', ''),
                    'application_email': fields.get('application_email', ''),
                    'application_instructions': fields.get('application_instructions', ''),
                    'source_link': draft.source_link or fields.get('source_link', ''),
                    'visibility': 'students',
                    'status': initial_status,
                    'published_at': timezone.now(),
                    'approved_by': request.user,
                    'created_by': draft.created_by or request.user,
                }
            )

            # Update import record
            draft.import_status = 'approved'
            draft.reviewed_by = request.user
            draft.reviewed_at = timezone.now()
            draft.save()

            InternshipReviewLog.objects.create(
                internship_import=draft,
                internship=internship,
                admin=request.user,
                action='approved',
                remarks="Approved and published to student dashboard."
            )

        serializer = InternshipSerializer(internship, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class InternshipDraftRejectView(APIView):
    """
    Rejects draft notice (FR-39).
    """
    permission_classes = [IsAdminUserRole]

    def post(self, request, import_id):
        try:
            draft = InternshipImport.objects.get(pk=import_id)
        except InternshipImport.DoesNotExist:
            return Response({'error': 'Draft not found.'}, status=status.HTTP_404_NOT_FOUND)

        reason = request.data.get('reason', 'Notice rejected by administrator.').strip()
        draft.import_status = 'rejected'
        draft.rejection_reason = reason
        draft.reviewed_by = request.user
        draft.reviewed_at = timezone.now()
        draft.save()

        InternshipReviewLog.objects.create(
            internship_import=draft,
            admin=request.user,
            action='rejected',
            remarks=reason
        )

        serializer = InternshipImportSerializer(draft)
        return Response(serializer.data)


class InternshipAdminManageView(APIView):
    """
    Admin manually creates an internship (FR-40).
    """
    permission_classes = [IsAdminUserRole]

    def post(self, request):
        serializer = InternshipSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            internship = serializer.save(
                created_by=request.user,
                approved_by=request.user,
                published_at=timezone.now(),
                visibility='students'
            )
            InternshipReviewLog.objects.create(
                internship=internship,
                admin=request.user,
                action='approved',
                remarks="Manually created and published by admin."
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InternshipAdminDetailManageView(APIView):
    """
    Admin updates or deletes an existing internship (FR-40).
    """
    permission_classes = [IsAdminUserRole]

    def patch(self, request, internship_id):
        try:
            internship = Internship.objects.get(pk=internship_id)
        except Internship.DoesNotExist:
            return Response({'error': 'Internship not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = InternshipSerializer(internship, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            InternshipReviewLog.objects.create(
                internship=internship,
                admin=request.user,
                action='edited',
                remarks="Admin updated internship details."
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, internship_id):
        try:
            internship = Internship.objects.get(pk=internship_id)
        except Internship.DoesNotExist:
            return Response({'error': 'Internship not found.'}, status=status.HTTP_404_NOT_FOUND)

        internship.delete()
        return Response({'message': 'Internship deleted successfully.'}, status=status.HTTP_200_OK)


class InternshipAdminHistoryView(APIView):
    """
    Audit history of all imports (FR-41).
    """
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        status_filter = request.query_params.get('status')
        imports = InternshipImport.objects.all().order_by('-created_at')
        if status_filter:
            imports = imports.filter(import_status=status_filter)

        serializer = InternshipImportSerializer(imports, many=True)
        return Response(serializer.data)


# ==========================================
# STUDENT INTERNSHIP ENDPOINTS
# ==========================================

class InternshipListView(APIView):
    """
    List, search, and sort published internships for students (FR-31, FR-32, FR-34).
    """
    permission_classes = [IsStudentOrAdmin]

    def get(self, request):
        today = timezone.now().date()
        # Automatically update any open internships whose deadline has passed (FR-34)
        Internship.objects.filter(status='open', application_deadline__lt=today).update(
            status='closed', updated_at=timezone.now()
        )

        queryset = Internship.objects.filter(visibility='students')

        # Status filter: default to open unless requested
        status_filter = request.query_params.get('status', 'open')
        if status_filter == 'open':
            queryset = queryset.filter(status='open')
        elif status_filter == 'closed':
            queryset = queryset.filter(status='closed')

        # Keyword Search (FR-32)
        search_query = request.query_params.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(company_name__icontains=search_query) |
                Q(position__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(location__icontains=search_query)
            )

        # Employment type filter
        emp_type = request.query_params.get('employment_type', '').strip()
        if emp_type:
            queryset = queryset.filter(employment_type__iexact=emp_type)

        # Location filter
        location = request.query_params.get('location', '').strip()
        if location:
            queryset = queryset.filter(location__icontains=location)

        # Sorting (FR-32)
        sort_by = request.query_params.get('sort', 'newest')
        if sort_by == 'deadline':
            queryset = queryset.order_by('application_deadline', '-published_at')
        else:
            queryset = queryset.order_by('-published_at', '-created_at')

        serializer = InternshipSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


class InternshipDetailView(APIView):
    """
    Detailed view of a single internship (FR-31, FR-34).
    """
    permission_classes = [IsStudentOrAdmin]

    def get(self, request, internship_id):
        try:
            internship = Internship.objects.get(pk=internship_id, visibility='students')
        except Internship.DoesNotExist:
            return Response({'error': 'Internship not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Check and update expiry
        internship.check_and_update_expiry()

        serializer = InternshipSerializer(internship, context={'request': request})
        return Response(serializer.data)


class InternshipBookmarkToggleView(APIView):
    """
    Bookmark or remove bookmark on an internship (FR-33).
    """
    permission_classes = [IsStudentOrAdmin]

    def post(self, request, internship_id):
        try:
            internship = Internship.objects.get(pk=internship_id)
        except Internship.DoesNotExist:
            return Response({'error': 'Internship not found.'}, status=status.HTTP_404_NOT_FOUND)

        bookmark, created = InternshipBookmark.objects.get_or_create(
            student=request.user,
            internship=internship
        )
        return Response({
            'bookmarked': True,
            'message': 'Internship bookmarked successfully.'
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, internship_id):
        try:
            internship = Internship.objects.get(pk=internship_id)
        except Internship.DoesNotExist:
            return Response({'error': 'Internship not found.'}, status=status.HTTP_404_NOT_FOUND)

        deleted_count, _ = InternshipBookmark.objects.filter(
            student=request.user,
            internship=internship
        ).delete()

        return Response({
            'bookmarked': False,
            'message': 'Bookmark removed successfully.'
        }, status=status.HTTP_200_OK)


class InternshipBookmarkListView(APIView):
    """
    List all bookmarked internships for the authenticated student (FR-33).
    """
    permission_classes = [IsStudentOrAdmin]

    def get(self, request):
        today = timezone.now().date()
        Internship.objects.filter(status='open', application_deadline__lt=today).update(
            status='closed', updated_at=timezone.now()
        )

        bookmarks = InternshipBookmark.objects.filter(student=request.user).select_related('internship')
        internships = [b.internship for b in bookmarks]

        serializer = InternshipSerializer(internships, many=True, context={'request': request})
        return Response(serializer.data)

