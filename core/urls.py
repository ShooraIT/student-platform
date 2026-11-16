from django.urls import path

from accounts import views as account_views

from . import views

app_name = "core"
urlpatterns = [
    path("", views.home, name="home"),
    path("profile/", account_views.profile, name="profile"),
    path("profile/rating-visibility/", account_views.toggle_rating, name="toggle_rating"),
    path("staff/", views.staff_dashboard, name="staff"),
    path("staff/students/<int:student_id>/", views.staff_student_profile, name="staff_student_profile"),
    path("staff/import/", views.import_students, name="import_students"),
    path("staff/credit/", views.manual_credit, name="manual_credit"),
    path("staff/reports/", views.reports, name="reports"),
    path("healthz", views.healthz),
]
