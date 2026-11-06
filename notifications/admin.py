from django.contrib import admin

from .models import Broadcast, Notification, PushSubscription


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "text", "kind", "is_read", "push"]
    list_filter = ["kind", "is_read", "push"]
    search_fields = ["user__last_name", "text"]


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "user_agent", "created_at"]
    search_fields = ["user__last_name"]
    readonly_fields = ["user", "endpoint", "p256dh", "auth", "user_agent", "created_at"]

    def has_add_permission(self, request):
        return False


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = ["created_at", "author", "text", "audience", "recipients"]
    readonly_fields = ["created_at", "author", "text", "url", "audience", "recipients"]

    def has_add_permission(self, request):
        return False
