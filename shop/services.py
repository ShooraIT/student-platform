from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from core.models import AuditLog, SiteSettings
from notifications.services import notify, notify_many
from wallet import services as wallet

from .models import Order, ProductVariant

User = get_user_model()


class ShopError(Exception):
    pass


def purchase(user, variant_id):
    with transaction.atomic():
        variant = ProductVariant.objects.select_for_update().select_related("product").get(pk=variant_id)
        product = variant.product
        if product.status != product.Status.ON_SALE:
            raise ShopError("Товар не продаётся")
        if variant.stock < 1:
            raise ShopError("Товар закончился")
        if product.per_user_limit is not None:
            bought = Order.objects.filter(user=user, variant__product=product).exclude(status=Order.Status.CANCELLED).count()
            if bought >= product.per_user_limit:
                raise ShopError(f"Лимит: не больше {product.per_user_limit} шт. на человека")
        order = Order.objects.create(user=user, variant=variant, price=product.price)
        try:
            wallet.charge(user, product.price, f"Покупка: {variant}", ("order", order.pk))
        except wallet.WalletError as e:
            raise ShopError(str(e))
        variant.stock -= 1
        variant.save(update_fields=["stock"])
    if variant.stock < product.low_stock_alert:
        admins = User.objects.filter(role__in=[User.Role.ADMIN, User.Role.SUPERADMIN], is_active=True)
        notify_many(admins, f"Заканчивается товар «{variant}»: осталось {variant.stock}", "/admin/shop/product/", "stock")
    from achievements.services import check_achievements

    check_achievements(user)
    return order


def cancel(order, by, reason="Отмена заказа"):
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status in (Order.Status.ISSUED, Order.Status.CANCELLED):
            raise ShopError("Заказ нельзя отменить")
        if by == order.user and not order.can_cancel_by_student:
            raise ShopError("Заказ уже готов к выдаче — отменить его может только администратор")
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
        if order.variant_id:
            ProductVariant.objects.filter(pk=order.variant_id).update(stock=F("stock") + 1)
            wallet.refund(order.user, order.price, f"{reason}: {order.variant}", ("order", order.pk))
    if by != order.user:
        AuditLog.log(by, "Отмена заказа", order, reason=reason)
        notify(order.user, f"Заказ {order.pickup_code} отменён" + (", степы возвращены" if order.price else ""), "/profile/", "order")
    return order


def mark_ready(order, by):
    if order.status != Order.Status.PLACED:
        raise ShopError("Заказ не в статусе «Оформлен»")
    order.status = Order.Status.READY
    order.save(update_fields=["status"])
    notify(order.user, f"Заказ {order.pickup_code} готов к выдаче: {order.item_title}", "/profile/", "order")


def issue(code, by):
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pickup_code=code.strip().upper()).first()
        if not order:
            raise ShopError("Заказ с таким кодом не найден")
        if order.status == Order.Status.ISSUED:
            raise ShopError(f"Заказ уже выдан {timezone.localtime(order.issued_at):%d.%m.%Y %H:%M}")
        if order.status == Order.Status.CANCELLED:
            raise ShopError("Заказ отменён")
        order.status = Order.Status.ISSUED
        order.issued_at = timezone.now()
        order.issued_by = by
        order.save()
    AuditLog.log(by, "Выдача заказа", order, item=order.item_title, student=str(order.user))
    return order


def expire_old_orders(system_user=None):
    days = SiteSettings.get().order_expire_days
    cutoff = timezone.now() - timedelta(days=days)
    n = 0
    for o in Order.objects.filter(status__in=[Order.Status.PLACED, Order.Status.READY], created_at__lt=cutoff, variant__isnull=False):
        cancel(o, system_user, f"Не забран за {days} дней")
        n += 1
    return n
