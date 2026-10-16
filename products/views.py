from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Category, Order, OrderItem, Product


def home(request):
    return render(request, 'home.html', {
        'products': Product.objects.all()[:5],
        'categories': Category.objects.all(),
    })


def all_products(request):
    products = Product.objects.all()
    return render(request, 'all_products.html', {'products': products})


def product_detail(request, product_id):
    return render(request, 'product_detail.html', {
        'product': get_object_or_404(Product, id=product_id),
    })


def _cart_data(request):
    """Return valid cart items and total, pruning bad or deleted entries."""
    raw_cart = request.session.get('cart', {})
    if not isinstance(raw_cart, dict):
        raw_cart = {}
    cart = {}
    for product_id, quantity in raw_cart.items():
        try:
            product_id, quantity = str(int(product_id)), int(quantity)
        except (TypeError, ValueError):
            continue
        if quantity > 0:
            cart[product_id] = quantity

    products = Product.objects.filter(id__in=cart.keys()).select_related('category')
    cart_items, total = [], Decimal('0.00')
    valid_cart = {}
    for product in products:
        quantity = cart[str(product.id)]
        subtotal = product.price * quantity
        cart_items.append({'product': product, 'quantity': quantity, 'subtotal': subtotal})
        total += subtotal
        valid_cart[str(product.id)] = quantity
    if valid_cart != raw_cart:
        request.session['cart'] = valid_cart
    return cart_items, total


@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})
    if not isinstance(cart, dict):
        cart = {}
    key = str(product_id)
    try:
        quantity = int(cart.get(key, 0))
    except (TypeError, ValueError):
        quantity = 0
    if quantity < product.stock:
        cart[key] = quantity + 1
        request.session['cart'] = cart
        messages.success(request, f'{product.name} added to cart.')
    else:
        messages.error(request, f'Sorry, only {product.stock} item(s) available.')
    return redirect('cart')


def cart(request):
    cart_items, total = _cart_data(request)
    return render(request, 'cart.html', {'cart_items': cart_items, 'total': total})


def checkout(request):
    cart_items, total = _cart_data(request)
    if not cart_items:
        messages.error(request, 'Your cart is empty. Add products before checkout.')
        return redirect('cart')

    if request.method == 'POST':
        customer_name = request.POST.get('customer_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        payment_method = request.POST.get('payment_method', 'cod')
        errors = []
        if not customer_name or len(customer_name) > 100:
            errors.append('Enter a valid name (up to 100 characters).')
        if email and len(email) > 254:
            errors.append('Enter a valid email address.')
        if not phone or len(phone) > 15:
            errors.append('Enter a valid phone number (up to 15 characters).')
        if not address:
            errors.append('Enter your delivery address.')
        if not city or len(city) > 100:
            errors.append('Enter a valid city.')
        if not pincode or len(pincode) > 10:
            errors.append('Enter a valid pincode.')
        if payment_method != 'cod':
            errors.append('Online payment is not available yet. Choose Cash on Delivery.')
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'checkout.html', {'cart_items': cart_items, 'total': total})

        try:
            with transaction.atomic():
                product_ids = [item['product'].id for item in cart_items]
                locked_products = {
                    product.id: product
                    for product in Product.objects.select_for_update().filter(id__in=product_ids)
                }
                for item in cart_items:
                    product = locked_products.get(item['product'].id)
                    if product is None or item['quantity'] > product.stock:
                        available = product.stock if product else 0
                        raise ValueError(f"Only {available} item(s) of {item['product'].name} are available.")

                # Recalculate using locked, current prices and stock.
                total = sum((locked_products[item['product'].id].price * item['quantity']
                             for item in cart_items), Decimal('0.00'))
                order = Order.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    customer_name=customer_name,
                    email=email,
                    phone=phone,
                    address=address,
                    city=city,
                    pincode=pincode,
                    total_amount=total,
                    payment_method='cod',
                )
                for item in cart_items:
                    product = locked_products[item['product'].id]
                    OrderItem.objects.create(
                        order=order, product=product, quantity=item['quantity'], price=product.price,
                    )
                    product.stock -= item['quantity']
                    product.save(update_fields=['stock'])
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect('cart')

        request.session['cart'] = {}
        request.session['last_order_id'] = order.id
        return redirect('order_success', order_id=order.id)

    return render(request, 'checkout.html', {'cart_items': cart_items, 'total': total})


@require_POST
def remove_from_cart(request, product_id):
    cart = request.session.get('cart', {})
    if isinstance(cart, dict):
        cart.pop(str(product_id), None)
        request.session['cart'] = cart
    return redirect('cart')


@require_POST
def increase_quantity(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})
    key = str(product_id)
    if isinstance(cart, dict) and key in cart:
        try:
            quantity = int(cart[key])
        except (TypeError, ValueError):
            quantity = 0
        if quantity < product.stock:
            cart[key] = quantity + 1
        else:
            messages.error(request, f'Sorry, only {product.stock} item(s) available.')
        request.session['cart'] = cart
    return redirect('cart')


@require_POST
def decrease_quantity(request, product_id):
    cart = request.session.get('cart', {})
    key = str(product_id)
    if isinstance(cart, dict) and key in cart:
        try:
            quantity = int(cart[key]) - 1
        except (TypeError, ValueError):
            quantity = 0
        if quantity > 0:
            cart[key] = quantity
        else:
            cart.pop(key, None)
        request.session['cart'] = cart
    return redirect('cart')


def register(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        if not username or len(username) > 150:
            messages.error(request, 'Enter a valid username.')
        elif password != confirm_password:
            messages.error(request, 'Passwords do not match.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
        else:
            try:
                validate_password(password)
            except ValidationError as exc:
                for error in exc.messages:
                    messages.error(request, error)
            else:
                try:
                    User.objects.create_user(username=username, email=email, password=password)
                except IntegrityError:
                    messages.error(request, 'Username already exists.')
                else:
                    messages.success(request, 'Account created successfully!')
                    return redirect('login')
    return render(request, 'register.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        user = authenticate(request, username=username, password=request.POST.get('password', ''))
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome, {username}!')
            return redirect('home')
        messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')


def category_products(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    return render(request, 'category_products.html', {
        'category': category, 'products': Product.objects.filter(category=category),
    })


def categories(request):
    return render(request, 'categories.html', {'categories': Category.objects.all()})


def search_products(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.filter(name__icontains=query) if query else Product.objects.none()
    return render(request, 'all_products.html', {'products': products, 'search_query': query})


def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    owns_order = (request.user.is_authenticated and order.user_id == request.user.id)
    guest_session_owns_order = order.user_id is None and request.session.get('last_order_id') == order.id
    if not (owns_order or guest_session_owns_order):
        messages.error(request, 'That order is not available in this session.')
        return redirect('home')
    return render(request, 'order_success.html', {'order': order})


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'my_orders.html', {'orders': orders})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'order_detail.html', {'order': order})


@login_required
@require_POST
def cancel_order(request, order_id):
    with transaction.atomic():
        order = get_object_or_404(Order.objects.select_for_update(), id=order_id, user=request.user)
        if order.status in ('placed', 'processing'):
            for item in order.items.select_related('product').all():
                product = Product.objects.select_for_update().get(id=item.product_id)
                product.stock += item.quantity
                product.save(update_fields=['stock'])
            order.status = 'cancelled'
            order.save(update_fields=['status'])
            messages.success(request, 'Your order has been cancelled.')
        else:
            messages.error(request, 'This order can no longer be cancelled.')
    return redirect('order_detail', order_id=order.id)
