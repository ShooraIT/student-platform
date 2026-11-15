from django.test import TestCase

from .models import StudyGroup, User


class CourseAccessTests(TestCase):
    def setUp(self):
        self.first = User.objects.create_user("first", password="test")
        self.senior_group = StudyGroup.objects.create(name="2А", course=2)
        self.senior = User.objects.create_user("senior", password="test", group=self.senior_group)
        self.mentor = User.objects.create_user("mentor", password="test", group=self.senior_group, is_mentor=True)

    def test_first_year_access(self):
        self.assertTrue(self.first.can_access("tasks"))
        self.assertTrue(self.first.can_access("career"))
        self.assertTrue(self.first.can_access("shop"))
        self.assertTrue(self.first.can_access("rating"))

    def test_senior_access(self):
        for section in ("events", "portfolio", "notifications", "employers"):
            self.assertTrue(self.senior.can_access(section), section)
        for section in ("tasks", "surveys", "career", "shop", "rating", "profile"):
            self.assertFalse(self.senior.can_access(section), section)

    def test_mentor_adds_only_mentor_area_and_shop(self):
        self.assertTrue(self.mentor.can_access("mentor"))
        self.assertTrue(self.mentor.can_access("shop"))
        self.assertFalse(self.mentor.can_access("tasks"))
        self.assertFalse(self.mentor.can_access("career"))

    def test_course_routes_are_enforced(self):
        self.client.force_login(self.senior)
        self.assertEqual(self.client.get("/career/").status_code, 302)
        self.assertEqual(self.client.get("/tasks/").status_code, 302)
        self.assertEqual(self.client.get("/rating/").status_code, 302)
        self.assertEqual(self.client.get("/profile/").status_code, 302)
        self.assertEqual(self.client.get("/portfolio/").status_code, 200)
        self.client.force_login(self.mentor)
        self.assertEqual(self.client.get("/career/mentor/").status_code, 200)
        self.assertEqual(self.client.get("/career/meetings/").status_code, 200)
