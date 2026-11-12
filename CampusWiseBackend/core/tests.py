import json
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from core.models import (
    User,
    Internship,
    InternshipImport,
    InternshipBookmark,
    InternshipReviewLog,
)
from services.gemini_extraction import (
    compute_content_hash,
    extract_internship_with_gemini,
    heuristic_fallback_extractor,
    sanitize_input_text,
)


class InternshipModuleTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Admin User
        self.admin = User.objects.create_user(
            student_id="admin-001",
            email="admin@diu.edu.bd",
            password="adminpassword123",
            role="admin",
            is_staff=True,
            is_superuser=True
        )

        # Create Student User
        self.student = User.objects.create_user(
            student_id="student-001",
            email="student@diu.edu.bd",
            password="studentpassword123",
            role="student"
        )

        # Create another Student User (for bookmark isolation testing)
        self.other_student = User.objects.create_user(
            student_id="student-002",
            email="student2@diu.edu.bd",
            password="studentpassword123",
            role="student"
        )

    # -------------------------------------------------------------
    # Scenario A & B: Email Import & Extraction Service
    # -------------------------------------------------------------
    def test_email_import_requires_admin(self):
        """Guests and students cannot import CDC emails."""
        import_data = {
            "email_subject": "Internship Opening at DataSoft",
            "original_email_content": "We are hiring software engineering interns for our AI team. Apply at http://datasoft.com"
        }
        # Guest
        resp = self.client.post("/api/internships/admin/import/", import_data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        # Student
        self.client.force_authenticate(user=self.student)
        resp = self.client.post("/api/internships/admin/import/", import_data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_email_import_validation(self):
        """Rejects empty or too-short email content."""
        self.client.force_authenticate(user=self.admin)

        # Empty content
        resp = self.client.post("/api/internships/admin/import/", {"email_subject": "Test", "original_email_content": ""}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # Too short
        resp = self.client.post("/api/internships/admin/import/", {"email_subject": "Test", "original_email_content": "Short"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_successful_admin_email_import(self):
        """Admin can import CDC email, extracting structured fields and preserving original content."""
        self.client.force_authenticate(user=self.admin)
        content = (
            "Career Development Center notice: BrainStation 23 is recruiting Python Backend Interns.\n"
            "Requirements: Python, Django, PostgreSQL.\n"
            "Location: Dhaka (Hybrid).\n"
            "Deadline: 2026-12-25.\n"
            "Apply: https://brainstation-23.com/apply"
        )
        import_data = {
            "email_subject": "BrainStation 23 Python Internship Notice",
            "sender_email": "cdc@diu.edu.bd",
            "original_email_content": content,
            "source_link": "https://diu.ac.bd/cdc/notice-123"
        }

        resp = self.client.post("/api/internships/admin/import/", import_data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", resp.data)
        self.assertEqual(resp.data["import_status"], "pending")
        self.assertEqual(resp.data["original_email_content"], content)

        # Check database record
        draft = InternshipImport.objects.get(pk=resp.data["id"])
        self.assertEqual(draft.email_subject, "BrainStation 23 Python Internship Notice")
        self.assertTrue(InternshipReviewLog.objects.filter(internship_import=draft, action="imported").exists())

    # -------------------------------------------------------------
    # Scenario C: Duplicate Detection (FR-38)
    # -------------------------------------------------------------
    def test_duplicate_notice_detection(self):
        """Prevents importing identical CDC notices unless override flag is used."""
        self.client.force_authenticate(user=self.admin)
        content = "Identical CDC email body content for duplicate detection test 12345."
        data = {
            "email_subject": "Test Notice 1",
            "original_email_content": content
        }

        # First import
        resp1 = self.client.post("/api/internships/admin/import/", data, format="json")
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        # Second import (duplicate)
        resp2 = self.client.post("/api/internships/admin/import/", data, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(resp2.data.get("duplicate"))

        # Override duplicate
        data_override = {**data, "allow_duplicate": True}
        resp3 = self.client.post("/api/internships/admin/import/", data_override, format="json")
        self.assertEqual(resp3.status_code, status.HTTP_201_CREATED)

    # -------------------------------------------------------------
    # Scenario D: Admin Review, Edit, Approval, and Rejection (FR-39)
    # -------------------------------------------------------------
    def test_admin_edit_draft(self):
        """Admin can modify extracted fields in pending draft."""
        draft = InternshipImport.objects.create(
            email_subject="Raw Subject",
            original_email_content="Sample long email content for testing review.",
            content_hash=compute_content_hash("Sample long email content for testing review."),
            extraction_result={"company_name": "Old Corp", "position": "Developer"}
        )
        self.client.force_authenticate(user=self.admin)

        resp = self.client.patch(
            f"/api/internships/admin/drafts/{draft.id}/",
            {"extraction_result": {"company_name": "New Corp", "position": "Senior Intern"}},
            format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        draft.refresh_from_db()
        self.assertEqual(draft.extraction_result["company_name"], "New Corp")

    def test_admin_approve_and_publish_draft(self):
        """Approving a draft creates an active Internship and updates review logs."""
        draft = InternshipImport.objects.create(
            email_subject="Notice",
            original_email_content="Full CDC text goes here for testing approval.",
            content_hash=compute_content_hash("Full CDC text goes here for testing approval."),
            extraction_result={
                "company_name": "Tech Corp",
                "position": "Frontend Intern",
                "description": "Build React user interfaces.",
                "application_deadline": (timezone.now() + timedelta(days=10)).strftime("%Y-%m-%d")
            }
        )
        self.client.force_authenticate(user=self.admin)

        resp = self.client.post(f"/api/internships/admin/drafts/{draft.id}/approve/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        draft.refresh_from_db()
        self.assertEqual(draft.import_status, "approved")

        internship = Internship.objects.get(import_record=draft)
        self.assertEqual(internship.company_name, "Tech Corp")
        self.assertEqual(internship.status, "open")
        self.assertEqual(internship.approved_by, self.admin)
        self.assertTrue(InternshipReviewLog.objects.filter(internship=internship, action="approved").exists())

    def test_admin_reject_draft(self):
        """Rejecting a draft marks it rejected and prevents publication."""
        draft = InternshipImport.objects.create(
            email_subject="Seminar Notice",
            original_email_content="This is just a seminar, not an internship.",
            content_hash=compute_content_hash("This is just a seminar, not an internship."),
            extraction_result={}
        )
        self.client.force_authenticate(user=self.admin)

        resp = self.client.post(
            f"/api/internships/admin/drafts/{draft.id}/reject/",
            {"reason": "Not an internship opportunity"},
            format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        draft.refresh_from_db()
        self.assertEqual(draft.import_status, "rejected")
        self.assertEqual(draft.rejection_reason, "Not an internship opportunity")
        # Ensure no Internship was created
        self.assertFalse(Internship.objects.filter(import_record=draft).exists())

    # -------------------------------------------------------------
    # Scenario E: Student Workflow (Browse, Search, Sort, Bookmark)
    # -------------------------------------------------------------
    def test_student_browse_and_search_internships(self):
        """Student can view, search, and sort open internships."""
        future_date = timezone.now().date() + timedelta(days=14)
        intern1 = Internship.objects.create(
            company_name="Google",
            position="Software Engineer Intern",
            description="Work on cloud technologies.",
            location="Remote",
            employment_type="Remote",
            application_deadline=future_date,
            status="open",
            visibility="students",
            published_at=timezone.now()
        )
        intern2 = Internship.objects.create(
            company_name="Microsoft",
            position="Cybersecurity Intern",
            description="Protect cloud infrastructure.",
            location="Dhaka",
            employment_type="On-site",
            application_deadline=future_date + timedelta(days=5),
            status="open",
            visibility="students",
            published_at=timezone.now()
        )

        self.client.force_authenticate(user=self.student)

        # Browse
        resp = self.client.get("/api/internships/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)

        # Search by company
        resp_search = self.client.get("/api/internships/?search=Google")
        self.assertEqual(len(resp_search.data), 1)
        self.assertEqual(resp_search.data[0]["company_name"], "Google")

        # Sort by deadline
        resp_sort = self.client.get("/api/internships/?sort=deadline")
        self.assertEqual(resp_sort.data[0]["company_name"], "Google")

    def test_student_bookmark_lifecycle(self):
        """Student can bookmark, list saved, and remove bookmark (FR-33)."""
        future_date = timezone.now().date() + timedelta(days=20)
        intern = Internship.objects.create(
            company_name="Pathao",
            position="Backend Intern",
            description="Go and Django services.",
            application_deadline=future_date,
            status="open",
            visibility="students",
            published_at=timezone.now()
        )

        self.client.force_authenticate(user=self.student)

        # 1. Add Bookmark
        resp = self.client.post(f"/api/internships/{intern.id}/bookmark/")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(InternshipBookmark.objects.filter(student=self.student, internship=intern).exists())

        # 2. View in Bookmark list
        resp_list = self.client.get("/api/internships/bookmarks/")
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_list.data), 1)
        self.assertEqual(resp_list.data[0]["id"], intern.id)
        self.assertTrue(resp_list.data[0]["is_bookmarked"])

        # 3. Isolation: other student does NOT see this bookmark
        self.client.force_authenticate(user=self.other_student)
        resp_other = self.client.get("/api/internships/bookmarks/")
        self.assertEqual(len(resp_other.data), 0)

        # 4. Remove Bookmark
        self.client.force_authenticate(user=self.student)
        resp_del = self.client.delete(f"/api/internships/{intern.id}/bookmark/")
        self.assertEqual(resp_del.status_code, status.HTTP_200_OK)
        self.assertFalse(InternshipBookmark.objects.filter(student=self.student, internship=intern).exists())

    # -------------------------------------------------------------
    # Scenario G: Expiration Handling (FR-34)
    # -------------------------------------------------------------
    def test_expired_internship_is_closed_automatically(self):
        """Past deadline internships are automatically marked closed and excluded from open listings."""
        past_date = timezone.now().date() - timedelta(days=2)
        expired_intern = Internship.objects.create(
            company_name="Old Co",
            position="Archived Intern",
            description="Old notice.",
            application_deadline=past_date,
            status="open",
            visibility="students",
            published_at=timezone.now() - timedelta(days=10)
        )

        self.client.force_authenticate(user=self.student)

        # Querying open internships triggers on-the-fly check and excludes expired
        resp = self.client.get("/api/internships/?status=open")
        self.assertEqual(len(resp.data), 0)

        # In database, status was updated to closed
        expired_intern.refresh_from_db()
        self.assertEqual(expired_intern.status, "closed")
        self.assertTrue(expired_intern.is_expired())

        # Direct detail query returns status 'closed'
        detail_resp = self.client.get(f"/api/internships/{expired_intern.id}/")
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data["status"], "closed")
        self.assertTrue(detail_resp.data["is_expired"])


class CDCInternshipValidationScenariosTests(TestCase):
    """
    Validation Test Suite for the 8 Scenarios specified in:
    CAMPUSWISE — INTERNSHIP TEST DATA AND GEMINI VALIDATION
    """

    CDC_FIXTURES = {
        "gp_software": {
            "email_subject": "CDC Notice: Grameenphone Software Engineering Intern",
            "sender_email": "cdc@diu.edu.bd",
            "original_email_content": (
                "Career Development Center (CDC) Notice:\n"
                "Grameenphone is recruiting passionate Software Engineering Interns for their tech division.\n"
                "Eligibility: CSE/SWE undergraduate students with CGPA 3.00+.\n"
                "Required Skills: Python, Django, REST APIs, Git, PostgreSQL.\n"
                "Location: Bashundhara R/A, Dhaka (Hybrid).\n"
                "Stipend: BDT 20,000 per month.\n"
                "Deadline: 31 December 2026.\n"
                "Application link: https://grameenphone.com/careers/intern-se\n"
                "Application email: talent@grameenphone.com\n"
                "Instructions: Submit CV through the career portal before the deadline."
            ),
            "source_link": "https://diu.edu.bd/cdc/notices/gp-se-2026",
        },
        "bash_marketing": {
            "email_subject": "Internship Alert: BASH Digital Marketing Intern",
            "sender_email": "cdc@diu.edu.bd",
            "original_email_content": (
                "CDC Announcement:\n"
                "BASH is looking for a creative Digital Marketing Intern.\n"
                "Eligibility: BBA/CSE students interested in marketing analytics.\n"
                "Required Skills: SEO, Social Media Management, Content Writing, Google Analytics.\n"
                "Location: Banani, Dhaka (On-site).\n"
                "Stipend: BDT 15,000 / month.\n"
                "Deadline: 15 January 2027.\n"
                "Application email: hr@bash.com.bd\n"
                "Instructions: Email CV with subject 'BASH Marketing Intern Application'."
            ),
            "source_link": "https://diu.edu.bd/cdc/notices/bash-marketing-2027",
        },
        "foodpanda_ba": {
            "email_subject": "foodpanda Business Analyst Intern Opportunity",
            "sender_email": "cdc@diu.edu.bd",
            "original_email_content": (
                "CDC Opportunity:\n"
                "foodpanda Bangladesh is hiring a Business Analyst Intern.\n"
                "Eligibility: Final year CSE, Economics, or BBA students.\n"
                "Required Skills: SQL, Excel, Data Visualization, Problem Solving.\n"
                "Location: Gulshan, Dhaka (Hybrid).\n"
                "Stipend: BDT 18,000 per month.\n"
                "Deadline: 28 February 2027.\n"
                "Application URL: https://careers.foodpanda.bd/ba-intern\n"
                "Application email: careers@foodpanda.com.bd\n"
                "Instructions: Apply directly via the online portal."
            ),
            "source_link": "https://diu.edu.bd/cdc/notices/foodpanda-ba",
        },
        "nnc_it_support": {
            "email_subject": "NNC IT Support Intern Vacancy",
            "sender_email": "cdc@diu.edu.bd",
            "original_email_content": (
                "CDC Notice:\n"
                "NNC Technologies is hiring an IT Support Intern for office infrastructure.\n"
                "Eligibility: CSE or CIS students.\n"
                "Required Skills: Hardware troubleshooting, Linux, Windows Server, Networking.\n"
                "Location: Uttara, Dhaka (On-site).\n"
                "Stipend: BDT 12,000 per month.\n"
                "Deadline: 10 December 2026.\n"
                "Application URL: https://nnc.com.bd/careers/it-support\n"
                "Application email: support-careers@nnc.com.bd\n"
                "Instructions: Send your CV to support-careers@nnc.com.bd."
            ),
            "source_link": "https://diu.edu.bd/cdc/notices/nnc-it",
        },
        "gp_expired": {
            "email_subject": "CDC Circular: Grameenphone Network Engineering Intern",
            "sender_email": "cdc@diu.edu.bd",
            "original_email_content": (
                "Grameenphone is recruiting a Network Engineering Intern.\n"
                "Eligibility: EEE / CSE students.\n"
                "Required Skills: CCNA, Routing, Switching, Network Monitoring.\n"
                "Location: Dhaka.\n"
                "Stipend: BDT 20,000.\n"
                "Deadline: 30 October 2026.\n"
                "Application link: https://grameenphone.com/careers/network\n"
                "Instructions: Submit resume before 30 October 2026."
            ),
            "source_link": "https://diu.edu.bd/cdc/notices/gp-network-2026",
        },
        "foodpanda_expired": {
            "email_subject": "foodpanda UI/UX Design Intern Announcement",
            "sender_email": "cdc@diu.edu.bd",
            "original_email_content": (
                "foodpanda is seeking creative UI/UX Design Interns.\n"
                "Eligibility: Open to all departments with design portfolio.\n"
                "Required Skills: Figma, UI Prototyping, Wireframing, User Research.\n"
                "Location: Dhaka (Remote).\n"
                "Stipend: BDT 16,000.\n"
                "Deadline: 1 November 2026.\n"
                "Application link: https://foodpanda.bd/careers/uiux\n"
                "Instructions: Submit design portfolio via application link."
            ),
            "source_link": "https://diu.edu.bd/cdc/notices/foodpanda-uiux-2026",
        },
        "technova_incomplete": {
            "email_subject": "TechNova Junior Web Developer Intern",
            "sender_email": "cdc@diu.edu.bd",
            "original_email_content": (
                "TechNova is looking for a Junior Web Developer Intern to assist the team.\n"
                "Requirements: HTML, CSS, JavaScript, React basics.\n"
                "Interested candidates should email their resume to jobs@technova.io."
            ),
            "source_link": "",
        },
        "abc_non_internship": {
            "email_subject": "Career Opportunity: ABC Technologies Full-Time Software Engineer",
            "sender_email": "cdc@diu.edu.bd",
            "original_email_content": (
                "CDC Job Alert:\n"
                "ABC Technologies is hiring a permanent Full-Time Software Engineer for enterprise financial software.\n"
                "Minimum Experience: 3+ years in backend engineering.\n"
                "Salary: BDT 95,000 - 120,000 per month.\n"
                "Location: Mohakhali DOHS, Dhaka (On-site).\n"
                "Deadline: 20 December 2026.\n"
                "Send CV to: careers@abctechnologies.com\n"
                "Note: This is a permanent full-time position, not an internship."
            ),
            "source_link": "https://diu.edu.bd/cdc/notices/abc-tech-se",
        },
    }

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            student_id="admin-scenarios",
            email="admin-scenarios@diu.edu.bd",
            password="adminpassword123",
            role="admin",
            is_staff=True,
            is_superuser=True
        )

        self.student = User.objects.create_user(
            student_id="student-scenarios",
            email="student-scenarios@diu.edu.bd",
            password="studentpassword123",
            role="student"
        )

    # -------------------------------------------------------------
    # Scenario 1: Active internships
    # -------------------------------------------------------------
    def test_scenario_1_active_internships(self):
        """
        Scenario 1:
        Import Grameenphone, BASH, foodpanda, NNC.
        - Gemini/fallback extracts available info.
        - Records created as drafts in pending status.
        - Admin can edit extracted fields.
        - Records become visible to students only after approval.
        """
        self.client.force_authenticate(user=self.admin)
        keys = ["gp_software", "bash_marketing", "foodpanda_ba", "nnc_it_support"]
        draft_ids = []

        for key in keys:
            fixture = self.CDC_FIXTURES[key]
            resp = self.client.post("/api/internships/admin/import/", fixture, format="json")
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
            self.assertEqual(resp.data["import_status"], "pending")
            self.assertIn("extraction_result", resp.data)
            draft_ids.append(resp.data["id"])

        # Verify drafts exist in database
        self.assertEqual(InternshipImport.objects.filter(id__in=draft_ids).count(), 4)

        # Admin edits one draft (FR-39)
        edit_resp = self.client.patch(
            f"/api/internships/admin/drafts/{draft_ids[0]}/",
            {"email_subject": "Updated GP Software Intern Subject"},
            format="json"
        )
        self.assertEqual(edit_resp.status_code, status.HTTP_200_OK)

        # Before approval: student cannot see any of these in published list
        self.client.force_authenticate(user=self.student)
        student_resp_before = self.client.get("/api/internships/?status=open")
        self.assertEqual(len(student_resp_before.data), 0)

        # Admin approves all 4 drafts
        self.client.force_authenticate(user=self.admin)
        for draft_id in draft_ids:
            approve_resp = self.client.post(
                f"/api/internships/admin/drafts/{draft_id}/approve/",
                {},
                format="json"
            )
            self.assertEqual(approve_resp.status_code, status.HTTP_200_OK)
            self.assertEqual(approve_resp.data["status"], "open")

        # After approval: student sees all 4 published active internships
        self.client.force_authenticate(user=self.student)
        student_resp_after = self.client.get("/api/internships/?status=open")
        self.assertEqual(len(student_resp_after.data), 4)

        # Test search
        search_resp = self.client.get("/api/internships/?search=Grameenphone")
        self.assertEqual(len(search_resp.data), 1)

    # -------------------------------------------------------------
    # Scenario 2: Expired internships
    # -------------------------------------------------------------
    def test_scenario_2_expired_internships(self):
        """
        Scenario 2:
        Import Grameenphone Network Intern (30 Oct 2026) and foodpanda UI/UX (1 Nov 2026).
        - Deadlines evaluated against Asia/Dhaka timezone.
        - Approval must NOT make expired internship active; published records must have CLOSED status.
        - Must NOT appear in active listing.
        """
        self.client.force_authenticate(user=self.admin)
        keys = ["gp_expired", "foodpanda_expired"]
        draft_ids = []

        for key in keys:
            resp = self.client.post("/api/internships/admin/import/", self.CDC_FIXTURES[key], format="json")
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
            draft_ids.append(resp.data["id"])

        # Check deadlines extracted
        gp_draft = InternshipImport.objects.get(pk=draft_ids[0])
        self.assertEqual(gp_draft.extraction_result.get("application_deadline"), "2026-10-30")

        fp_draft = InternshipImport.objects.get(pk=draft_ids[1])
        self.assertEqual(fp_draft.extraction_result.get("application_deadline"), "2026-11-01")

        # Admin approves both expired drafts
        for draft_id in draft_ids:
            approve_resp = self.client.post(
                f"/api/internships/admin/drafts/{draft_id}/approve/",
                {},
                format="json"
            )
            self.assertEqual(approve_resp.status_code, status.HTTP_200_OK)
            # Must be created with status 'closed'
            self.assertEqual(approve_resp.data["status"], "closed")
            self.assertTrue(approve_resp.data["is_expired"])

        # Verify in database: records have status = 'closed'
        gp_intern = Internship.objects.get(import_record=gp_draft)
        self.assertEqual(gp_intern.status, "closed")
        self.assertTrue(gp_intern.is_expired())

        # Student queries active internships (?status=open) -> Expired MUST NOT appear!
        self.client.force_authenticate(user=self.student)
        active_resp = self.client.get("/api/internships/?status=open")
        self.assertEqual(len(active_resp.data), 0)

        # Student queries closed internships (?status=closed) -> Both appear here
        closed_resp = self.client.get("/api/internships/?status=closed")
        self.assertEqual(len(closed_resp.data), 2)

        # Direct detail query confirms closed status and is_expired
        detail_resp = self.client.get(f"/api/internships/{gp_intern.id}/")
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data["status"], "closed")
        self.assertTrue(detail_resp.data["is_expired"])

    # -------------------------------------------------------------
    # Scenario 3: Incomplete email
    # -------------------------------------------------------------
    def test_scenario_3_incomplete_email(self):
        """
        Scenario 3:
        Import TechNova Junior Web Developer Intern.
        - Missing stipend, deadline and duration remain empty (no hallucination).
        - Admin can manually complete missing information.
        """
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post("/api/internships/admin/import/", self.CDC_FIXTURES["technova_incomplete"], format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        draft = InternshipImport.objects.get(pk=resp.data["id"])
        # Verify missing fields were NOT fabricated
        self.assertIsNone(draft.extraction_result.get("application_deadline"))
        self.assertEqual(draft.extraction_result.get("stipend"), "")

        # Admin completes missing information manually during review
        completed_fields = {
            **draft.extraction_result,
            "company_name": "TechNova",
            "position": "Junior Web Developer Intern",
            "description": "Assist team with web development.",
            "stipend": "BDT 10,000 / month",
            "application_deadline": (timezone.now().date() + timedelta(days=20)).strftime("%Y-%m-%d")
        }

        approve_resp = self.client.post(
            f"/api/internships/admin/drafts/{draft.id}/approve/",
            {"fields": completed_fields},
            format="json"
        )
        self.assertEqual(approve_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(approve_resp.data["stipend"], "BDT 10,000 / month")
        self.assertEqual(approve_resp.data["status"], "open")

    # -------------------------------------------------------------
    # Scenario 4: Non-internship email
    # -------------------------------------------------------------
    def test_scenario_4_non_internship_email(self):
        """
        Scenario 4:
        Import ABC Technologies Full-Time Software Engineer.
        - Gemini/fallback classifies it as NOT an internship.
        - Draft cannot be approved without explicit administrative correction.
        - No automatic publication.
        """
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post("/api/internships/admin/import/", self.CDC_FIXTURES["abc_non_internship"], format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["extraction_status"], "not_internship")

        draft = InternshipImport.objects.get(pk=resp.data["id"])
        self.assertEqual(draft.extraction_status, "not_internship")

        # Attempt to approve WITHOUT administrative correction -> Must be REJECTED (400)
        approve_resp = self.client.post(
            f"/api/internships/admin/drafts/{draft.id}/approve/",
            {},
            format="json"
        )
        self.assertEqual(approve_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not an internship", approve_resp.data.get("error", "").lower())

        # Now approve WITH explicit administrative correction
        override_resp = self.client.post(
            f"/api/internships/admin/drafts/{draft.id}/approve/",
            {
                "is_internship_correction": True,
                "fields": {
                    "company_name": "ABC Technologies",
                    "position": "Software Engineering Trainee",
                    "description": "Backend trainee position approved with admin correction.",
                    "application_deadline": (timezone.now().date() + timedelta(days=30)).strftime("%Y-%m-%d")
                }
            },
            format="json"
        )
        self.assertEqual(override_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(override_resp.data["company_name"], "ABC Technologies")

    # -------------------------------------------------------------
    # Scenario 5: Duplicate email detection
    # -------------------------------------------------------------
    def test_scenario_5_duplicate_email_detection(self):
        """
        Scenario 5:
        Import exact same Grameenphone notice twice.
        - System identifies duplicate via SHA-256 content hash.
        - Rejects duplicate import with 409 Conflict.
        - Distinct notice (different role/deadline) is NOT blocked.
        """
        self.client.force_authenticate(user=self.admin)
        fixture = self.CDC_FIXTURES["gp_software"]

        # First import -> Success
        resp1 = self.client.post("/api/internships/admin/import/", fixture, format="json")
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        first_id = resp1.data["id"]

        # Second import of exact same notice -> 409 Conflict
        resp2 = self.client.post("/api/internships/admin/import/", fixture, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(resp2.data.get("duplicate"))
        self.assertEqual(resp2.data.get("existing_id"), first_id)

        # Import different Grameenphone notice (different role and deadline) -> Must succeed!
        distinct_fixture = self.CDC_FIXTURES["gp_expired"]
        resp3 = self.client.post("/api/internships/admin/import/", distinct_fixture, format="json")
        self.assertEqual(resp3.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(resp3.data["id"], first_id)

    # -------------------------------------------------------------
    # Scenario 6: Student and guest access permissions
    # -------------------------------------------------------------
    def test_scenario_6_student_and_guest_permissions(self):
        """
        Scenario 6:
        - Approved active internships visible to authenticated students.
        - Guests cannot retrieve internships (401).
        - Students can bookmark and unbookmark.
        - Students cannot access admin review endpoints (403).
        """
        future_date = timezone.now().date() + timedelta(days=25)
        intern = Internship.objects.create(
            company_name="Access Test Corp",
            position="QA Intern",
            description="Testing enterprise web apps.",
            application_deadline=future_date,
            status="open",
            visibility="students",
            published_at=timezone.now()
        )

        # 1. Guest (unauthenticated) checks
        guest_client = APIClient()
        resp_guest_list = guest_client.get("/api/internships/")
        self.assertEqual(resp_guest_list.status_code, status.HTTP_401_UNAUTHORIZED)

        resp_guest_detail = guest_client.get(f"/api/internships/{intern.id}/")
        self.assertEqual(resp_guest_detail.status_code, status.HTTP_401_UNAUTHORIZED)

        resp_guest_bookmark = guest_client.post(f"/api/internships/{intern.id}/bookmark/")
        self.assertEqual(resp_guest_bookmark.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Student permission boundaries
        self.client.force_authenticate(user=self.student)

        # Student CAN view active internships
        resp_student_list = self.client.get("/api/internships/")
        self.assertEqual(resp_student_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_student_list.data), 1)

        # Student CANNOT access admin review queues
        resp_forbidden_drafts = self.client.get("/api/internships/admin/drafts/")
        self.assertEqual(resp_forbidden_drafts.status_code, status.HTTP_403_FORBIDDEN)

        resp_forbidden_import = self.client.post(
            "/api/internships/admin/import/",
            {"email_subject": "Hacker Import", "original_email_content": "Unauthorized text content."},
            format="json"
        )
        self.assertEqual(resp_forbidden_import.status_code, status.HTTP_403_FORBIDDEN)

        # Student bookmarks and unbookmarks
        bm_add = self.client.post(f"/api/internships/{intern.id}/bookmark/")
        self.assertEqual(bm_add.status_code, status.HTTP_201_CREATED)

        bm_list = self.client.get("/api/internships/bookmarks/")
        self.assertEqual(len(bm_list.data), 1)
        self.assertTrue(bm_list.data[0]["is_bookmarked"])

        bm_del = self.client.delete(f"/api/internships/{intern.id}/bookmark/")
        self.assertEqual(bm_del.status_code, status.HTTP_200_OK)

        bm_list_after = self.client.get("/api/internships/bookmarks/")
        self.assertEqual(len(bm_list_after.data), 0)

    # -------------------------------------------------------------
    # Scenario 7: Extraction reliability and edge cases
    # -------------------------------------------------------------
    def test_scenario_7_extraction_reliability(self):
        """
        Scenario 7:
        Test extraction resilience:
        - Missing fields.
        - Invalid Gemini response format.
        - Gemini API exception.
        - Malformed email with XSS tags.
        - Extremely long email content.
        - Diverse date formats.
        """
        # A. Date format parsing resilience
        test_dates = [
            ("Deadline: 30 October 2026", "2026-10-30"),
            ("Deadline: 1 November 2026", "2026-11-01"),
            ("Application Deadline: 31 December 2026", "2026-12-31"),
            ("Apply before: 15 January 2027", "2027-01-15"),
            ("Due date: 2026-12-10", "2026-12-10"),
            ("Deadline: 30th Oct 2026", "2026-10-30"),
            ("Deadline: 1st Nov 2026", "2026-11-01"),
        ]
        for text_snippet, expected_iso in test_dates:
            data = heuristic_fallback_extractor("Intern Notice", text_snippet)
            self.assertEqual(data["application_deadline"], expected_iso, f"Failed parsing: {text_snippet}")

        # B. Malformed HTML / XSS sanitization
        malicious_input = "<script>alert('xss');</script><b>Valid text</b><img src=x onerror=alert(1)>"
        sanitized = sanitize_input_text(malicious_input)
        self.assertNotIn("<script>", sanitized)
        self.assertNotIn("onerror", sanitized)

        # C. Extremely long content (15,000 words)
        long_body = "We are seeking talented interns. " * 3000
        long_hash = compute_content_hash(long_body)
        self.assertEqual(len(long_hash), 64)
        long_extracted = heuristic_fallback_extractor("Long Notice", long_body)
        self.assertTrue(long_extracted["is_internship"])
        self.assertLessEqual(len(long_extracted["description"]), 1000)

        # D. Simulated Gemini API Exception Recovery
        with patch("google.genai.Client", side_effect=RuntimeError("Connection timeout to Gemini")):
            with patch.dict("os.environ", {"GEMINI_API_KEY": "dummy_key_for_test"}):
                status_res, result = extract_internship_with_gemini(
                    "Test Intern Notice",
                    "We are hiring interns at ABC. Deadline: 2026-12-31"
                )
                self.assertEqual(status_res, "partial")
                self.assertTrue(result["is_internship"])
                self.assertTrue(any("Gemini API error" in n for n in result["extraction_notes"]))

        # E. Simulated Gemini returning Invalid / Non-JSON output
        mock_response = MagicMock()
        mock_response.text = "Sorry, I cannot return JSON right now."
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("google.genai.Client", return_value=mock_client):
            with patch.dict("os.environ", {"GEMINI_API_KEY": "dummy_key_for_test"}):
                status_res, result = extract_internship_with_gemini(
                    "Test Intern Notice",
                    "We are hiring interns at ABC. Deadline: 2026-12-31"
                )
                self.assertEqual(status_res, "partial")
                self.assertTrue(result["is_internship"])
                self.assertTrue(any("Gemini API error" in n for n in result["extraction_notes"]))
