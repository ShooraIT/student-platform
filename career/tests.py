from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import DiagTest, Employer, ExternalAchievement, FundItem, Resume, RouteStage, Track
from .services import enroll, issue_fund, return_fund, submit_diagnostic

User = get_user_model()


class CareerPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("career-student", password="test")
        self.client.force_login(self.user)

    def test_initial_career_catalog(self):
        self.assertEqual(Track.objects.filter(is_active=True).count(), 9)
        self.assertEqual(RouteStage.objects.count(), 5)
        self.assertEqual(self.client.get("/career/tracks/").status_code, 200)
        self.assertEqual(self.client.get("/career/").status_code, 200)

    def test_student_can_try_multiple_tracks(self):
        for track in Track.objects.filter(is_active=True):
            enroll(self.user, track)
        self.assertEqual(self.user.track_enrollments.count(), 9)

    def test_student_career_pages_render(self):
        track = Track.objects.get(slug="it-support")
        test = DiagTest.objects.get(title="Профиль интересов 01:17")
        employer = Employer.objects.create(name="Проверочная компания")
        for path in (
            "/career/meetings/", "/career/employers/", "/portfolio/",
            "/portfolio/add/", "/portfolio/resume/", "/portfolio/resume/print/",
            f"/career/tracks/{track.slug}/", f"/career/diagnostic/{test.pk}/",
            f"/career/employers/{employer.pk}/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_staff_career_reports_render(self):
        staff = User.objects.create_user("career-curator", password="test", role=User.Role.ADMIN)
        self.client.force_login(staff)
        self.assertEqual(self.client.get("/career/staff/portfolio/").status_code, 200)
        self.assertEqual(self.client.get("/career/staff/route/").status_code, 200)
        self.assertEqual(self.client.get("/staff/").status_code, 200)
        self.assertEqual(self.client.get("/shop/award/").status_code, 200)

    def test_public_portfolio_requires_explicit_opt_in(self):
        resume = Resume.objects.create(user=self.user)
        self.assertEqual(self.client.get(f"/p/{resume.token}/").status_code, 404)
        resume.public = True
        resume.save(update_fields=["public"])
        self.assertEqual(self.client.get(f"/p/{resume.token}/").status_code, 200)

    def test_external_files_are_not_visible_to_other_students(self):
        achievement = ExternalAchievement.objects.create(user=self.user, title="Сертификат")
        other = User.objects.create_user("other-student", password="test")
        self.client.force_login(other)
        self.assertEqual(self.client.get(f"/career/files/{achievement.pk}/").status_code, 403)

    def test_weighted_diagnostic_saves_scores_and_recommendations(self):
        test = DiagTest.objects.get(title="Профиль интересов 01:17")
        answers = {f"q{q.pk}": str(q.options.first().pk) for q in test.questions.all()}
        result = submit_diagnostic(test, self.user, answers)
        self.assertEqual(len(result.scores), 4)
        self.assertGreaterEqual(result.recommended.count(), 1)
        self.assertLessEqual(result.recommended.count(), 3)

    def test_issue_and_return_updates_pool_stock(self):
        item = FundItem.objects.create(name="Поло тест", kind=FundItem.Kind.LOAN, stock=1)
        issue = issue_fund(item, self.user)
        item.refresh_from_db()
        self.assertEqual(item.stock, 0)
        return_fund(issue)
        item.refresh_from_db()
        self.assertEqual(item.stock, 1)
