from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from core.models import AuditLog, SiteSettings
from notifications.services import notify, notify_many
from wallet import services as wallet

from .models import Order, Product, ProductVariant

User = get_user_model()


class ShopError(Exception):
    pass


def products_for_user(user, queryset=None):
    """Show track-tagged goods only when they match the student's group specialty."""
    queryset = Product.objects.all() if queryset is None else queryset
    if not user.is_student:
        return queryset
    specialty = (getattr(user.group, "specialty", "") if user.group_id else "").strip().lower()
    code = specialty.split()[0].strip(" ,;") if specialty else ""
    if not code:
        return queryset.filter(tracks__isnull=True).distinct()

    from career.models import Track

    allowed_ids = [
        track.pk for track in Track.objects.filter(is_active=True)
        if code in {value.strip().lower() for value in track.specialties.split(",") if value.strip()}
    ]
    return queryset.filter(Q(tracks__isnull=True) | Q(tracks__in=allowed_ids)).distinct()


def purchase(user, variant_id):
    with transaction.atomic():
        variant = ProductVariant.objects.select_for_update().select_related("product").get(pk=variant_id)
        product = variant.product
        if product.status != product.Status.ON_SALE or product.kind == product.Kind.REWARD:
            raise ShopError("Товар не продаётся")
        if not products_for_user(user).filter(pk=product.pk).exists():
            raise ShopError("Товар недоступен для направления вашей группы")
        if product.kind == product.Kind.EXPERIENCE:
            _check_experience(product, user)
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
        if product.kind == product.Kind.EXPERIENCE and product.event_id:
            _register_experience(product.event, user)
    if variant.stock < product.low_stock_alert:
        admins = User.objects.filter(role__in=[User.Role.ADMIN, User.Role.SUPERADMIN], is_active=True)
        notify_many(admins, f"Заканчивается товар «{variant}»: осталось {variant.stock}", "/admin/shop/product/", "stock")
    from achievements.services import check_achievements

    check_achievements(user)
    return order


def _check_experience(product, user):
    from events.models import Registration

    ev = product.event
    if ev is None:
        raise ShopError("Для товара с профессиональным опытом выберите мероприятие")
    if not ev.registration_open:
        raise ShopError("Запись на это мероприятие закрыта")
    if Registration.objects.filter(event=ev, user=user).exclude(status=Registration.Status.CANCELLED).exists():
        raise ShopError("Вы уже записаны на это мероприятие")


def _register_experience(event, user):
    """Место куплено за степы — записываем без учёта общего лимита мест (места продаёт магазин)."""
    from events.models import Registration

    reg, created = Registration.objects.get_or_create(event=event, user=user, defaults={"status": Registration.Status.REGISTERED})
    if not created and reg.status not in Registration.ACTIVE:
        reg.status = Registration.Status.REGISTERED
        reg.save(update_fields=["status"])


def award(user, variant, by, reason="Награда"):
    """Выдать товар-награду (рюкзак, патч) бесплатно: заказ сразу готов к выдаче."""
    with transaction.atomic():
        variant = ProductVariant.objects.select_for_update().select_related("product").get(pk=variant.pk)
        if variant.product.kind != variant.product.Kind.REWARD:
            raise ShopError("Этот товар не является наградой")
        if variant.stock < 1:
            raise ShopError("Нет на складе")
        order = Order.objects.create(user=user, variant=variant, price=0, status=Order.Status.READY)
        variant.stock -= 1
        variant.save(update_fields=["stock"])
    AuditLog.log(by, "Выдача награды", order, item=str(variant), student=str(user), reason=reason)
    notify(user, f"Вам вручена награда: {variant}. {reason}. Код получения: {order.pickup_code}", f"/shop/orders/{order.pk}/", "order")
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
            if order.price:
                wallet.refund(order.user, order.price, f"{reason}: {order.variant}", ("order", order.pk))
            product = order.variant.product
            if product.kind == product.Kind.EXPERIENCE and product.event_id:
                from events.models import Registration

                Registration.objects.filter(event_id=product.event_id, user=order.user, status=Registration.Status.REGISTERED).update(
                    status=Registration.Status.CANCELLED)
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
    for o in Order.objects.filter(status__in=[Order.Status.PLACED, Order.Status.READY], created_at__lt=cutoff, price__gt=0).exclude(variant__product__kind="experience"):
        cancel(o, system_user, f"Не забран за {days} дней")
        n += 1
    return n
