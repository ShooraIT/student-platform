from django.contrib import admin, messages

from core.admin_mixins import AuditedAdmin

from . import services
from .models import Order, Product, ProductVariant


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(AuditedAdmin):
    list_display = ["title", "kind", "category", "price", "status", "stock", "per_user_limit", "order", "asset_path"]
    list_editable = ["order"]
    list_filter = ["status", "kind", "category"]
    search_fields = ["title"]
    autocomplete_fields = ["event"]
    filter_horizontal = ["tracks"]
    inlines = [VariantInline]

    @admin.display(description="Остаток")
    def stock(self, obj):
        return obj.total_stock()


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["pickup_code", "user", "item", "price", "status", "created_at", "issued_at"]
    list_filter = ["status", "variant__product"]
    search_fields = ["pickup_code", "user__last_name"]
    readonly_fields = [f.name for f in Order._meta.fields]
    actions = ["make_ready", "cancel_orders"]

    @admin.display(description="Товар")
    def item(self, obj):
        return obj.item_title

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Отметить «Готов к выдаче» (уведомить студентов)")
    def make_ready(self, request, queryset):
        for o in queryset:
            try:
                services.mark_ready(o, request.user)
            except services.ShopError as e:
                messages.warning(request, f"{o}: {e}")

    @admin.action(description="Отменить заказы с возвратом степов")
    def cancel_orders(self, request, queryset):
        for o in queryset:
            try:
                services.cancel(o, request.user, "Отменён администратором")
            except services.ShopError as e:
                messages.warning(request, f"{o}: {e}")
