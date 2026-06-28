# pyrefly: ignore [missing-import]
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from .models import Submission
from .forms import ProfileUpdateForm
from .services import classify_submission, points_for_category


class SubmissionPointsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media = TemporaryDirectory()
        cls._override = override_settings(MEDIA_ROOT=cls._media.name)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        cls._media.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            username="recycler",
            email="recycler@example.com",
            password="test-pass-123",
        )

    def image_file(self, name="waste.jpg"):
        return SimpleUploadedFile(
            name,
            b"small-image-content",
            content_type="image/jpeg",
        )

    def test_pending_submission_starts_with_zero_points(self):
        submission = Submission.objects.create(user=self.user, image=self.image_file())

        self.user.profile.refresh_from_db()
        self.assertEqual(submission.status, Submission.STATUS_PENDING)
        self.assertEqual(submission.points, 0)
        self.assertEqual(self.user.profile.total_points, 0)

    def test_only_approved_points_count_toward_user_total(self):
        approved = Submission.objects.create(
            user=self.user,
            image=self.image_file("approved.jpg"),
            status=Submission.STATUS_APPROVED,
            waste_type="Plastic",
            waste_category=Submission.CATEGORY_DRY,
            points=40,
        )
        rejected = Submission.objects.create(
            user=self.user,
            image=self.image_file("rejected.jpg"),
            status=Submission.STATUS_REJECTED,
            waste_type="Paper",
            waste_category=Submission.CATEGORY_DRY,
            points=25,
        )

        rejected.refresh_from_db()
        self.user.profile.refresh_from_db()

        self.assertEqual(approved.points, 40)
        self.assertEqual(rejected.points, 0)
        self.assertEqual(self.user.profile.total_points, 40)

    def test_total_updates_when_approved_submission_changes(self):
        submission = Submission.objects.create(
            user=self.user,
            image=self.image_file(),
            status=Submission.STATUS_APPROVED,
            points=30,
        )
        submission.status = Submission.STATUS_REJECTED
        submission.save()

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.total_points, 0)

    def test_point_total_adjusts_when_approved_points_are_edited(self):
        submission = Submission.objects.create(
            user=self.user,
            image=self.image_file(),
            status=Submission.STATUS_APPROVED,
            waste_type="E-waste",
            waste_category=Submission.CATEGORY_SPECIAL,
            points=20,
        )
        submission.points = 18
        submission.save()

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.total_points, 18)

    def test_category_points_follow_dynamic_scoring_rules(self):
        self.assertEqual(points_for_category(Submission.CATEGORY_WET), 5)
        self.assertEqual(points_for_category(Submission.CATEGORY_DRY), 10)
        self.assertEqual(points_for_category(Submission.CATEGORY_SANITARY), 15)
        self.assertEqual(points_for_category(Submission.CATEGORY_SPECIAL), 20)
        self.assertEqual(points_for_category(Submission.CATEGORY_INVALID), 0)

    @patch("core.services.predict_waste")
    def test_classify_submission_approves_valid_ml_prediction(self, mocked_predict):
        mocked_predict.return_value = {
            "category": Submission.CATEGORY_DRY,
            "confidence": 0.92,
        }
        submission = Submission.objects.create(user=self.user, image=self.image_file())

        classify_submission(submission)

        submission.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(submission.status, Submission.STATUS_APPROVED)
        self.assertEqual(submission.waste_category, Submission.CATEGORY_DRY)
        self.assertEqual(submission.waste_type, Submission.CATEGORY_DRY)
        self.assertEqual(submission.prediction_confidence, 0.92)
        self.assertEqual(submission.points, 10)
        self.assertEqual(self.user.profile.total_points, 10)

    @patch("core.services.predict_waste")
    def test_classify_submission_assigns_special_waste_points(self, mocked_predict):
        mocked_predict.return_value = {
            "category": Submission.CATEGORY_SPECIAL,
            "confidence": 0.91,
        }
        submission = Submission.objects.create(user=self.user, image=self.image_file())

        classify_submission(submission)

        submission.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(submission.status, Submission.STATUS_APPROVED)
        self.assertEqual(submission.points, 20)
        self.assertEqual(self.user.profile.total_points, 20)

    @patch("core.services.predict_waste")
    def test_classify_submission_rejects_low_confidence_prediction(self, mocked_predict):
        mocked_predict.return_value = {
            "category": Submission.CATEGORY_WET,
            "confidence": 0.42,
        }
        submission = Submission.objects.create(user=self.user, image=self.image_file())

        classify_submission(submission)

        submission.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(submission.status, Submission.STATUS_REJECTED)
        self.assertEqual(submission.points, 0)
        self.assertIn("confidently", submission.rejection_reason)
        self.assertEqual(self.user.profile.total_points, 0)

    @patch("core.services.predict_waste")
    def test_classify_submission_rejects_invalid_prediction(self, mocked_predict):
        mocked_predict.return_value = {
            "category": Submission.CATEGORY_INVALID,
            "confidence": 0.99,
        }
        submission = Submission.objects.create(user=self.user, image=self.image_file())

        classify_submission(submission)

        submission.refresh_from_db()
        self.assertEqual(submission.status, Submission.STATUS_REJECTED)
        self.assertEqual(submission.waste_category, Submission.CATEGORY_INVALID)
        self.assertEqual(submission.points, 0)

    def test_submission_timestamp_renders_in_ist(self):
        timestamp = timezone.datetime(
            2026,
            5,
            7,
            14,
            5,
            tzinfo=ZoneInfo("UTC"),
        )
        rendered = Template(
            '{% load tz %}{{ value|localtime|date:"d M Y, g:i A" }}'
        ).render(Context({"value": timestamp}))

        self.assertEqual(rendered, "07 May 2026, 7:35 PM")

    def test_profile_form_rejects_invalid_mobile_number(self):
        form = ProfileUpdateForm(
            data={
                "full_name": "Hari Prasad",
                "email": "hari@example.com",
                "mobile_number": "12345abcde",
                "door_number": "",
                "area_locality": "",
                "area_type": "",
                "district": "",
                "ward_number": "",
                "pincode": "",
                "preferred_waste_category": "",
            },
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("mobile_number", form.errors)

    def test_profile_completion_tracks_saved_fields(self):
        self.user.first_name = "Hari"
        self.user.last_name = "Prasad"
        self.user.email = "hari@example.com"
        self.user.save()
        profile = self.user.profile
        profile.mobile_number = "9876543210"
        profile.door_number = "12A"
        profile.area_locality = "Green Nagar"
        profile.area_type = profile.AREA_URBAN
        profile.district = "Chennai"
        profile.ward_number = "14"
        profile.pincode = "600001"
        profile.preferred_waste_category = Submission.CATEGORY_SPECIAL
        profile.save()

        self.assertEqual(profile.completion_percentage, 100)

    def test_eco_id_qr_download_returns_png(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("eco_id_qr_download"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")

    def test_profile_update_does_not_change_email(self):
        self.user.email = "fixed@example.com"
        self.user.save(update_fields=["email"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("profile"),
            data={
                "update_profile": "1",
                "full_name": "Updated Citizen",
                "email": "changed@example.com",
                "mobile_number": "9876543210",
                "door_number": "10",
                "area_locality": "Eco Street",
                "area_type": "Urban",
                "district": "Chennai",
                "ward_number": "4",
                "pincode": "600001",
            },
        )

        self.user.refresh_from_db()
        self.assertRedirects(response, reverse("profile"))
        self.assertEqual(self.user.email, "fixed@example.com")

    def test_completion_card_hides_when_profile_is_complete(self):
        self.user.first_name = "Hari"
        self.user.last_name = "Prasad"
        self.user.email = "hari@example.com"
        self.user.save()
        profile = self.user.profile
        profile.mobile_number = "9876543210"
        profile.door_number = "12A"
        profile.area_locality = "Green Nagar"
        profile.area_type = profile.AREA_URBAN
        profile.district = "Chennai"
        profile.ward_number = "14"
        profile.pincode = "600001"
        profile.preferred_waste_category = Submission.CATEGORY_SPECIAL
        profile.save()
        self.client.force_login(self.user)

        response = self.client.get(reverse("profile"))

        self.assertNotContains(response, "Profile Completion")

    def test_rewards_dashboard_uses_shared_badge_progression_and_stats(self):
        now = timezone.now()
        Submission.objects.create(
            user=self.user,
            image=self.image_file("dry.jpg"),
            status=Submission.STATUS_APPROVED,
            waste_type=Submission.CATEGORY_DRY,
            waste_category=Submission.CATEGORY_DRY,
            points=10,
            timestamp=now,
        )
        Submission.objects.create(
            user=self.user,
            image=self.image_file("special.jpg"),
            status=Submission.STATUS_APPROVED,
            waste_type=Submission.CATEGORY_SPECIAL,
            waste_category=Submission.CATEGORY_SPECIAL,
            points=20,
            timestamp=now,
        )
        profile = self.user.profile
        profile.total_points = 150
        profile.save(update_fields=["total_points"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("rewards"))

        self.assertContains(response, "Eco Rewards Dashboard")
        self.assertContains(response, "Recycler Badge")
        self.assertEqual(response.context["badge"], "Recycler")
        self.assertEqual(response.context["current_badge"]["name"], "Recycler")
        self.assertEqual(response.context["next_badge"]["name"], "Eco Champion")
        self.assertEqual(response.context["weekly_points"], 30)
        self.assertEqual(response.context["monthly_points"], 30)
        self.assertEqual(response.context["impact"]["recyclable_items"], 1)
        self.assertEqual(response.context["impact"]["hazardous_items"], 1)

    @patch("core.services.predict_waste")
    def test_duplicate_submission_protection(self, mocked_predict):
        mocked_predict.return_value = {
            "category": Submission.CATEGORY_DRY,
            "confidence": 0.95,
        }
        
        # 1. First submission (normal)
        sub1 = Submission.objects.create(user=self.user, image=self.image_file("duplicate_test.jpg"))
        classify_submission(sub1)
        sub1.refresh_from_db()
        self.assertEqual(sub1.status, Submission.STATUS_APPROVED)
        self.assertEqual(sub1.points, 10)
        self.assertEqual(sub1.waste_category, Submission.CATEGORY_DRY)
        
        # 2. Second submission with the same image content by the same user within 24 hours
        sub2 = Submission.objects.create(user=self.user, image=self.image_file("duplicate_test.jpg"))
        classify_submission(sub2)
        sub2.refresh_from_db()
        
        self.assertEqual(sub2.status, Submission.STATUS_DUPLICATE)
        self.assertEqual(sub2.points, 0)
        self.assertEqual(sub2.waste_category, Submission.CATEGORY_DRY)
        self.assertIn("already submitted within the last 24 hours", sub2.rejection_reason)

        # 3. Third submission with the same image content but by a different user
        other_user = User.objects.create_user(
            username="other_recycler",
            email="other@example.com",
            password="test-pass-123",
        )
        sub3 = Submission.objects.create(user=other_user, image=self.image_file("duplicate_test.jpg"))
        classify_submission(sub3)
        sub3.refresh_from_db()
        self.assertEqual(sub3.status, Submission.STATUS_APPROVED)
        self.assertEqual(sub3.points, 10)

        # 4. Fourth submission with same image by same user but time-shifted to 25 hours ago
        Submission.objects.all().delete()
        sub4 = Submission.objects.create(user=self.user, image=self.image_file("duplicate_test.jpg"))
        sub4.timestamp = timezone.now() - timezone.timedelta(hours=25)
        sub4.save()
        
        # Let's create a new submission which checks for duplicate against sub4
        sub5 = Submission.objects.create(user=self.user, image=self.image_file("duplicate_test.jpg"))
        classify_submission(sub5)
        sub5.refresh_from_db()
        self.assertEqual(sub5.status, Submission.STATUS_APPROVED)
        self.assertEqual(sub5.points, 10)
