import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q


class Product(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        ON_SALE = "on_sale", "В продаже"
        OFF = "off", "Снят с продажи"

    title = models.CharField("Название", max_length=200)
    description = models.TextField("Описание", blank=True)
    photo = models.ImageField("Фото", upload_to="products/", blank=True)
    price = models.PositiveIntegerField("Цена, степов")
    per_user_limit = models.PositiveIntegerField("Лимит на студента", null=True, blank=True, help_text="Пусто — без лимита")
    low_stock_alert = models.PositiveIntegerField("Предупреждать, когда остаток меньше", default=3)
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.DRAFT)
    order = models.PositiveIntegerField("Порядок в каталоге", default=0)

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ["order", "title"]

    def __str__(self):
        return self.title

    def total_stock(self):
        return sum(v.stock for v in self.variants.all())


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField("Вариант", max_length=50, default="—", help_text="Например, размер M. Если вариантов нет — «—»")
    stock = models.PositiveIntegerField("Остаток", default=0)

    class Meta:
        verbose_name = "Вариант товара"
        verbose_name_plural = "Варианты и остатки"

    def __str__(self):
        return self.product.title if self.name in ("", "—") else f"{self.product.title} ({self.name})"


def gen_pickup_code():
    return "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))


class Order(models.Model):
    class Status(models.TextChoices):
        PLACED = "placed", "Оформлен"
        READY = "ready", "Готов к выдаче"
        ISSUED = "issued", "Выдан"
        CANCELLED = "cancelled", "Отменён"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders", verbose_name="Студент")
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Товар")
    prize = models.ForeignKey("draws.DrawPrize", null=True, blank=True, on_delete=models.PROTECT, verbose_name="Приз розыгрыша")
    price = models.PositiveIntegerField("Цена", default=0)
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.PLACED)
    pickup_code = models.CharField("Код получения", max_length=8, unique=True, default=gen_pickup_code)
    created_at = models.DateTimeField("Оформлен", auto_now_add=True)
    issued_at = models.DateTimeField("Выдан", null=True, blank=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="Выдал")

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=Q(variant__isnull=False) | Q(prize__isnull=False), name="order_has_item")]

    def __str__(self):
        return f"Заказ {self.pickup_code}"

    @property
    def item_title(self):
        return str(self.variant) if self.variant_id else f"Приз: {self.prize}"

    @property
    def can_cancel_by_student(self):
        return self.status == self.Status.PLACED and self.variant_id is not None
