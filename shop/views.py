from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.decorators import staff_required

from . import services
from .models import Order, Product, ProductVariant

User = get_user_model()


@login_required
def catalog(request):
    products = services.products_for_user(request.user).filter(status=Product.Status.ON_SALE).exclude(kind=Product.Kind.REWARD).prefetch_related("variants", "tracks")
    category = request.GET.get("category", "")
    if category in {choice[0] for choice in Product.Category.choices}:
        products = products.filter(category=category)
    return render(request, "shop/catalog.html", {"products": products, "selected_category": category})


@login_required
def product_detail(request, pk):
    products = services.products_for_user(request.user).exclude(kind=Product.Kind.REWARD).prefetch_related("variants", "tracks")
    product = get_object_or_404(products, pk=pk, status=Product.Status.ON_SALE)
    return render(request, "shop/product.html", {"product": product})


@login_required
@require_POST
def buy(request, pk):
    if request.user.is_staff_role:
        messages.error(request, "Покупки доступны только студентам")
        return redirect("shop:product", pk=pk)
    try:
        order = services.purchase(request.user, int(request.POST.get("variant", 0)))
        messages.success(request, f"Заказ оформлен! Код получения: {order.pickup_code}")
        return redirect("shop:order", pk=order.pk)
    except services.ShopError as e:
        messages.error(request, str(e))
    except (ValueError, ProductVariant.DoesNotExist):
        messages.error(request, "Выберите вариант товара")
    return redirect("shop:product", pk=pk)


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, "shop/order.html", {"order": order})


@login_required
@require_POST
def order_cancel(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    try:
        services.cancel(order, request.user)
        messages.success(request, "Заказ отменён, степы возвращены")
    except services.ShopError as e:
        messages.error(request, str(e))
    return redirect("core:profile")


@staff_required
def issue(request):
    order = None
    if request.method == "POST":
        try:
            order = services.issue(request.POST.get("code", ""), request.user)
            messages.success(request, f"Выдано: {order.item_title} — {order.user.full_name}")
        except services.ShopError as e:
            messages.error(request, str(e))
    code = request.GET.get("code", "").strip().upper()
    found = Order.objects.filter(pickup_code=code).select_related("user", "user__group").first() if code else None
    pending = Order.objects.filter(status__in=[Order.Status.PLACED, Order.Status.READY]).select_related("user", "variant__product")[:50]
    return render(request, "shop/issue.html", {"found": found, "code": code, "pending": pending, "issued": order})


@staff_required
def award(request):
    variants = ProductVariant.objects.filter(product__kind=Product.Kind.REWARD).select_related("product")
    students = User.objects.filter(role=User.Role.STUDENT, expelled=False).select_related("group").order_by("last_name", "first_name")
    if request.method == "POST":
        try:
            variant = variants.get(pk=request.POST.get("variant"))
            student = students.get(pk=request.POST.get("user"))
            services.award(student, variant, request.user, request.POST.get("reason", "Награда"))
            messages.success(request, f"Награда выдана: {student.full_name}")
            return redirect("shop:award")
        except (ProductVariant.DoesNotExist, User.DoesNotExist, ValueError, TypeError):
            messages.error(request, "Выберите студента и товар-награду")
        except services.ShopError as exc:
            messages.error(request, str(exc))
    return render(request, "shop/award.html", {"variants": variants, "students": students})
