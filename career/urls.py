from django.urls import path

from . import views

app_name = "career"
urlpatterns = [
    path("", views.my_path, name="path"),
    path("tracks/", views.tracks, name="tracks"),
    path("tracks/<slug:slug>/", views.track_detail, name="track"),
    path("tracks/<slug:slug>/<str:action>/", views.track_action, name="track_action"),
    path("diagnostic/<int:pk>/", views.diagnostic, name="diagnostic"),
    path("diagnostic/result/<int:pk>/", views.diag_result, name="diag_result"),
    path("meetings/", views.meetings, name="meetings"),
    path("meetings/<int:pk>/<str:action>/", views.meeting_action, name="meeting_action"),
    path("mentor/", views.mentor_home, name="mentor"),
    path("mentor/<int:pk>/close/", views.mentor_close, name="mentor_close"),
    path("mentor/<int:pk>/cancel/", views.mentor_cancel, name="mentor_cancel"),
    path("employers/", views.employers, name="employers"),
    path("employers/<int:pk>/", views.employer_detail, name="employer"),
    path("staff/portfolio/", views.staff_external, name="staff_external"),
    path("staff/route/", views.staff_route, name="staff_route"),
    path("staff/students/<int:user_id>/resume/", views.staff_resume, name="staff_resume"),
    path("files/<int:pk>/", views.external_file, name="external_file"),
]
