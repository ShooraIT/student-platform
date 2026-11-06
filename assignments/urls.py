from django.urls import path

from . import views

app_name = "assignments"
urlpatterns = [
    path("", views.task_list, name="list"),
    path("<int:pk>/", views.task_detail, name="detail"),
    path("<int:pk>/submit/", views.submit, name="submit"),
    path("review/", views.review_queue, name="review"),
]
