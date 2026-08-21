from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from urllib3 import request

from .models import Category, Product, Order, OrderItem


# Home page
def home(request):
    products = Product.objects.all()[:5]  # Display only the first 5 products
    categories = Category.objects.all()

    return render(request, 'home.html', {
        'products': products,
        'categories':categories
    })
def all_products(request):
    products = Product.objects.all()

    return render(request, 'all_products.html', {
        'products': products
    })


# Product detail
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    return render(request, 'product_detail.html', {
        'product': product
    })

# Add product to cart
def add_to_cart(request, product_id):

    product = get_object_or_404(Product, id=product_id)

    cart = request.session.get('cart', {})

    product_id = str(product_id)

    current_quantity = cart.get(product_id, 0)

    if current_quantity < product.stock:

        cart[product_id] = current_quantity + 1

        request.session['cart'] = cart

        messages.success(
            request,
            f'{product.name} added to cart.'
        )

    else:

        messages.error(
            request,
            f'Sorry, only {product.stock} item(s) available.'
        )

    return redirect('cart')
# Cart page
def cart(request):
    cart = request.session.get('cart', {})

    products = Product.objects.filter(
        id__in=cart.keys()
    )

    cart_items = []
    total = 0

    for product in products:
        quantity = cart[str(product.id)]
        subtotal = product.price * quantity

        cart_items.append({
            'product': product,
            'quantity': quantity,
            'subtotal': subtotal
        })

        total += subtotal

    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'total': total
    })
def checkout(request):

    cart = request.session.get('cart', {})

    products = Product.objects.filter(
        id__in=cart.keys()
    )

    cart_items = []
    total = 0

    for product in products:

        quantity = cart[str(product.id)]

        subtotal = product.price * quantity

        cart_items.append({
            'product': product,
            'quantity': quantity,
            'subtotal': subtotal
        })

        total += subtotal

    if request.method == 'POST':
     # Final stock check before creating the order
        for item in cart_items:

            product = item['product']
            quantity = item['quantity']

            if quantity > product.stock:

                messages.error(
                    request,
                    f'Sorry, only {product.stock} item(s) of {product.name} are available.'
                )

                return redirect('cart')

        # Check stock before creating order
        

        customer_name = request.POST.get('customer_name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        city = request.POST.get('city')
        pincode = request.POST.get('pincode')
        payment_method = request.POST.get('payment_method')

        # Create order
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            customer_name=customer_name,
            phone=phone,
            address=address,
            city=city,
            pincode=pincode,
            total_amount=total,
            payment_method=payment_method
        )

        # Create order items and reduce stock
        for item in cart_items:

            product = item['product']
            quantity = item['quantity']

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=product.price
            )

            # Reduce stock
            product.stock -= quantity
            product.save()

        # Clear cart
        request.session['cart'] = {}

        return redirect(
            'order_success',
            order_id=order.id
        )

    return render(request, 'checkout.html', {
        'cart_items': cart_items,
        'total': total
    })



# Remove product from cart
def remove_from_cart(request, product_id):
    cart = request.session.get('cart', {})

    product_id = str(product_id)

    if product_id in cart:
        del cart[product_id]

    request.session['cart'] = cart

    return redirect('cart')


# Increase quantity
def increase_quantity(request, product_id):

    product = get_object_or_404(
        Product,
        id=product_id
    )

    cart = request.session.get('cart', {})

    product_id = str(product_id)

    if product_id in cart:

        if cart[product_id] < product.stock:

            cart[product_id] += 1

        else:

            messages.error(
                request,
                f'Sorry, only {product.stock} item(s) available.'
            )

    request.session['cart'] = cart

    return redirect('cart')

# Decrease quantity
def decrease_quantity(request, product_id):
    cart = request.session.get('cart', {})

    product_id = str(product_id)

    if product_id in cart:
        cart[product_id] -= 1

        if cart[product_id] <= 0:
            del cart[product_id]

    request.session['cart'] = cart

    return redirect('cart')


# Register
def register(request):

    if request.method == 'POST':

        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('register')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        user.save()

        messages.success(
            request,
            'Account created successfully!'
        )

        return redirect('login')

    return render(request, 'register.html')


# Login
def login_view(request):

    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(request, user)

            messages.success(
                request,
                f'Welcome, {username}!'
            )

            return redirect('home')

        else:

            messages.error(
                request,
                'Invalid username or password.'
            )

    return render(request, 'login.html')


# Logout
def logout_view(request):

    logout(request)

    messages.success(
        request,
        'You have been logged out.'
    )

    return redirect('home')
#category view
def category_products(request, category_id):

    category = get_object_or_404(Category, id=category_id)

    products = Product.objects.filter(category=category)

    return render(request, 'category_products.html', {
        'category': category,
        'products': products
    })
def categories(request):
    categories = Category.objects.all()

    return render(request, 'categories.html', {
        'categories': categories
    })
    
def search_products(request):
    query = request.GET.get('q', '')

    products = Product.objects.filter(
        name__icontains=query
    )

    return render(request, 'all_products.html', {
        'products': products,
        'search_query': query
        
    })
def order_success(request, order_id):

    order = get_object_or_404(
        Order,
        id=order_id
    )

    return render(
        request,
        'order_success.html',
        {
            'order': order
        }
    )
def my_orders(request):

    if not request.user.is_authenticated:
        return redirect('login')

    orders = Order.objects.filter(
        user=request.user
    ).order_by('-created_at')

    return render(
        request,
        'my_orders.html',
        {
            'orders': orders
        }
    )
def order_detail(request, order_id):

    if not request.user.is_authenticated:
        return redirect('login')

    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user
    )

    return render(
        request,
        'order_detail.html',
        {
            'order': order
        }
    )
@login_required
def cancel_order(request, order_id):

    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user
    )

    if order.status in ['placed', 'processing']:

        for item in order.items.all():

            product = item.product

            product.stock += item.quantity
            product.save()

        order.status = 'cancelled'
        order.save()

    return redirect('order_detail', order_id=order.id)
# Create your views here.
