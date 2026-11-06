from django.contrib import admin, messages

from . import services
from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "amount", "kind", "reason", "author"]
    list_filter = ["kind", "created_at"]
    search_fields = ["user__last_name", "user__first_name", "reason"]
    date_hierarchy = "created_at"
    actions = ["reverse_selected"]

    def has_add_permission(self, request):
        return False  # начисления — через экран «Начислить степы»

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Сторнировать (отменить) выбранные начисления")
    def reverse_selected(self, request, queryset):
        ok = 0
        for tx in queryset:
            try:
                services.reverse(tx, request.user)
                ok += 1
            except services.WalletError as e:
                messages.warning(request, f"{tx}: {e}")
        if ok:
            messages.success(request, f"Отменено операций: {ok}")
