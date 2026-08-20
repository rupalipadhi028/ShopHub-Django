from django.urls import path
from.import views
urlpatterns=[
    path('',views.home,name='home'),
     path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),

    path("logout/", views.logout_view, name="logout"),
     path('product/<int:product_id>/', views.product_detail, name='product_detail'),
     path(
        'cart/add/<int:product_id>/',
        views.add_to_cart,
        name='add_to_cart'
    ),
     path(
        'cart/',
        views.cart,
        name='cart'
    ),
     path(
        'cart/remove/<int:product_id>/',
        views.remove_from_cart,
        name='remove_from_cart'
    ),
     path(
        'cart/increase/<int:product_id>/',
        views.increase_quantity,
        name='increase_quantity'
    ),
     path(
    'cart/decrease/<int:product_id>/',
    views.decrease_quantity,
    name='decrease_quantity'
),
      path('register/', views.register, name='register'),
       path(
        'login/',
        views.login_view,
        name='login'
    ),

    path(
        'logout/',
        views.logout_view,
        name='logout'
    ),
    path(
        'category/<int:category_id>/',
        views.category_products,
        name='category_products'
    ),
    path('products/', views.all_products, name='products'),
    path('categories/', views.categories, name='categories'),
    path("search/", views.search_products, name="search"),
    path(
        'checkout/',
        views.checkout,
        name='checkout'
    ),
    path(
    "order-success/<int:order_id>/",
    views.order_success,
    name="order_success"
),
    path(
    "my-orders/",
    views.my_orders,
    name="my_orders"
),
    path(
    "order/<int:order_id>/",
    views.order_detail,
    name="order_detail"
),
    path(
    'order/<int:order_id>/cancel/',
    views.cancel_order,
    name='cancel_order'
),
]
