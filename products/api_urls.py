from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .api_views import (
    CartItemViewSet, CartView, CategoryViewSet, LoginView, LogoutView,
    OrderViewSet, PasswordChangeView, ProductViewSet, RegisterView, ReviewViewSet,
)

router = DefaultRouter()
router.register('products', ProductViewSet, basename='api-product')
router.register('categories', CategoryViewSet, basename='api-category')
router.register('cart/items', CartItemViewSet, basename='api-cart-item')
router.register('orders', OrderViewSet, basename='api-order')
router.register('reviews', ReviewViewSet, basename='api-review')

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='api-register'),
    path('auth/token/', LoginView.as_view(), name='api-token'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='api-token-refresh'),
    path('auth/logout/', LogoutView.as_view(), name='api-logout'),
    path('auth/change-password/', PasswordChangeView.as_view(), name='api-change-password'),
    path('cart/', CartView.as_view(), name='api-cart'),
    path('', include(router.urls)),
]
