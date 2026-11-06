from django.urls import path

from . import views

app_name = "events"
urlpatterns = [
    path("", views.calendar_view, name="calendar"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/register/", views.register, name="register"),
    path("<int:pk>/cancel/", views.cancel, name="cancel"),
    path("<int:pk>/code/", views.checkin_code, name="checkin_code"),
    path("<int:pk>/qr/", views.checkin_qr, name="checkin_qr"),
    path("<int:pk>/event.ics", views.ics, name="ics"),
    path("<int:pk>/staff/checkin/", views.staff_checkin, name="staff_checkin"),
    path("<int:pk>/staff/qr.json", views.staff_qr, name="staff_qr"),
    path("<int:pk>/staff/attendees/", views.staff_attendees, name="staff_attendees"),
]
