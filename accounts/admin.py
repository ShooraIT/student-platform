from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponse

from core.models import AuditLog

from . import importer
from .models import StudyGroup, UnmatchedMeshLogin, User


@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "course", "specialty_name", "is_active", "students_count"]
    list_filter = ["is_active", "course"]
    search_fields = ["name", "specialty", "specialty_name"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "is_active__exact" not in request.GET:
            queryset = queryset.filter(is_active=True)
        return queryset

    def save_model(self, request, obj, form, change):
        obj.is_active = obj.course == 1
        super().save_model(request, obj, form, change)

    @admin.display(description="Студентов")
    def students_count(self, obj):
        return obj.students.filter(expelled=False).count()


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["full_name", "username", "group", "role", "balance", "mesh_linked", "expelled"]
    list_filter = ["role", "is_mentor", "expelled", "group__course", "group"]
    filter_horizontal = ["mentor_tracks", "groups"]
    search_fields = ["last_name", "first_name", "username", "email"]
    readonly_fields = ["balance", "last_login", "date_joined"]
    actions = ["reset_passwords"]
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Данные", {"fields": ("last_name", "first_name", "middle_name", "group", "email", "birth_date", "mesh_id")}),
        ("Платформа", {"fields": ("role", "balance", "must_change_password", "hide_from_rating", "expelled", "is_active")}),
        ("Наставничество", {"fields": ("is_mentor", "mentor_tracks")}),
        ("Служебное", {"classes": ["collapse"], "fields": ("is_staff", "is_superuser", "groups", "last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"fields": ("username", "password1", "password2", "last_name", "first_name", "role", "group")}),
    )

    @admin.display(boolean=True, description="МЭШ")
    def mesh_linked(self, obj):
        return bool(obj.mesh_id)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            ro += ["role", "is_staff", "is_superuser", "groups"]
        return ro

    @admin.action(description="Сбросить пароль и скачать новые доступы")
    def reset_passwords(self, request, queryset):
        creds = [(u, importer.reset_password(u)) for u in queryset.filter(role=User.Role.STUDENT)]
        AuditLog.log(request.user, "Сброс паролей", f"{len(creds)} студентов")
        wb = importer.credentials_workbook(creds)
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="new_passwords.xlsx"'
        wb.save(resp)
        return resp


@admin.register(UnmatchedMeshLogin)
class UnmatchedMeshLoginAdmin(admin.ModelAdmin):
    list_display = ["last_name", "first_name", "middle_name", "email", "birth_date", "created_at"]
    readonly_fields = ["mesh_id", "last_name", "first_name", "middle_name", "email", "birth_date", "raw", "candidates", "created_at"]
    fields = readonly_fields + ["linked_user"]
    autocomplete_fields = ["linked_user"]

    def save_model(self, request, obj, form, change):
        if obj.linked_user:
            u = obj.linked_user
            if u.mesh_id and u.mesh_id != obj.mesh_id:
                messages.error(request, "Этот студент уже привязан к другой учётной записи МЭШ")
                return
            u.mesh_id = obj.mesh_id
            u.save(update_fields=["mesh_id"])
            AuditLog.log(request.user, "Привязка МЭШ", u, mesh_id=obj.mesh_id)
            obj.delete()
            messages.success(request, f"{u} привязан. Теперь студент может войти через МЭШ")
            return
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        return False
