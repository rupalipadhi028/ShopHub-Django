from django.contrib.auth import update_session_auth_hash
from django.db import transaction
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.serializers import TokenBlacklistSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .api_permissions import IsAdminOrReadOnly, IsOwnerOrReadOnly
from .api_serializers import (
    CartItemSerializer, CartItemWriteSerializer, CartSerializer, CategorySerializer,
    OrderSerializer, OrderStatusSerializer, PasswordChangeSerializer, PlaceOrderSerializer,
    ProductSerializer, RegisterSerializer, ReviewSerializer,
)
from .models import Cart, CartItem, Category, Order, OrderItem, Product, Review


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'


class LogoutView(generics.GenericAPIView):
    serializer_class = TokenBlacklistSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_205_RESET_CONTENT)


class PasswordChangeView(generics.GenericAPIView):
    serializer_class = PasswordChangeSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password'])
        update_session_auth_hash(request, request.user)
        return Response({'detail': 'Password changed successfully.'})


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {'category': ['exact'], 'price': ['gte', 'lte'], 'stock': ['gt']}
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'stock']
    ordering = ['id']


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['name']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ['name']


class CartView(generics.GenericAPIView):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(self.get_serializer(cart).data)

    def delete(self, request):
        cart = Cart.objects.filter(user=request.user).first()
        if cart:
            cart.items.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemViewSet(viewsets.ModelViewSet):
    queryset = CartItem.objects.none()
    permission_classes = [IsAuthenticated]
    filter_backends = []
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return CartItem.objects.filter(cart__user=self.request.user).select_related('product')

    def get_serializer_class(self):
        return CartItemWriteSerializer if self.action in ('create', 'update', 'partial_update') else CartItemSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data['product']
        increment = serializer.validated_data['quantity']
        with transaction.atomic():
            cart, _ = Cart.objects.select_for_update().get_or_create(user=request.user)
            product = Product.objects.select_for_update().get(pk=product.pk)
            item = CartItem.objects.filter(cart=cart, product=product).first()
            new_quantity = (item.quantity if item else 0) + increment
            if new_quantity > product.stock:
                return Response({'quantity': f'Only {product.stock} item(s) are available.'}, status=status.HTTP_400_BAD_REQUEST)
            if item:
                item.quantity = new_quantity
                item.save(update_fields=['quantity'])
            else:
                item = CartItem.objects.create(cart=cart, product=product, quantity=new_quantity)
        output = CartItemSerializer(item)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        with transaction.atomic():
            cart = Cart.objects.select_for_update().get(user=self.request.user)
            product = Product.objects.select_for_update().get(pk=serializer.instance.product_id)
            quantity = serializer.validated_data.get('quantity', serializer.instance.quantity)
            if quantity > product.stock:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'quantity': f'Only {product.stock} item(s) are available.'})
            serializer.save(cart=cart, product=product)


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.select_related('product', 'user').all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['product', 'rating']
    ordering_fields = ['created_at', 'rating']

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.none()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = []
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        queryset = Order.objects.prefetch_related('items__product').order_by('-created_at')
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)

    def get_permissions(self):
        if self.action in ('partial_update', 'update'):
            return [IsAdminUser()]
        return [permission() for permission in self.permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return PlaceOrderSerializer
        if self.action in ('partial_update', 'update'):
            return OrderStatusSerializer
        return OrderSerializer

    def create(self, request, *args, **kwargs):
        serializer = PlaceOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            cart = Cart.objects.select_for_update().filter(user=request.user).first()
            if cart is None:
                return Response({'detail': 'Your cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)
            cart_items = list(cart.items.select_related('product').order_by('product_id'))
            if not cart_items:
                return Response({'detail': 'Your cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)
            locked_products = {
                product.id: product
                for product in Product.objects.select_for_update().filter(
                    id__in=[item.product_id for item in cart_items]
                ).order_by('id')
            }
            for item in cart_items:
                product = locked_products.get(item.product_id)
                if product is None or item.quantity > product.stock:
                    available = product.stock if product else 0
                    return Response(
                        {'detail': f'Only {available} item(s) of {item.product.name} are available.'},
                        status=status.HTTP_409_CONFLICT,
                    )
            total = sum((locked_products[item.product_id].price * item.quantity for item in cart_items), 0)
            order = Order.objects.create(
                user=request.user,
                total_amount=total,
                **serializer.validated_data,
            )
            for item in cart_items:
                product = locked_products[item.product_id]
                OrderItem.objects.create(order=order, product=product, quantity=item.quantity, price=product.price)
                product.stock -= item.quantity
                product.save(update_fields=['stock'])
            cart.items.all().delete()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        with transaction.atomic():
            order = get_object_or_404(Order.objects.select_for_update(), pk=self.kwargs['pk'])
            serializer = OrderStatusSerializer(order, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            new_status = serializer.validated_data['status']
            allowed_transitions = {
                'placed': {'processing', 'cancelled'},
                'processing': {'shipped', 'cancelled'},
                'shipped': {'delivered'},
                'delivered': set(),
                'cancelled': set(),
            }
            if new_status not in allowed_transitions.get(order.status, set()):
                return Response({'status': 'Invalid order status transition.'}, status=status.HTTP_400_BAD_REQUEST)
            if new_status == 'cancelled':
                for item in order.items.all().order_by('product_id'):
                    product = Product.objects.select_for_update().get(pk=item.product_id)
                    product.stock += item.quantity
                    product.save(update_fields=['stock'])
            serializer.save()
        return Response(OrderSerializer(order).data)
