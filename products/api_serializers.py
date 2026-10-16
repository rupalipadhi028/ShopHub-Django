from django.contrib.auth import password_validation
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from .models import Cart, CartItem, Category, Order, OrderItem, Product, Review


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password')
        read_only_fields = ('id',)

    def validate_password(self, value):
        try:
            password_validation.validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value):
        try:
            password_validation.validate_password(value, self.context['request'].user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value

    def validate_current_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'image')


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'name', 'description', 'price', 'stock', 'image', 'category', 'category_name')


class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Review
        fields = ('id', 'product', 'user', 'user_name', 'rating', 'comment', 'created_at', 'updated_at')
        read_only_fields = ('id', 'user_name', 'created_at', 'updated_at')
        validators = [UniqueTogetherValidator(queryset=Review.objects.all(), fields=('user', 'product'))]


class CartItemWriteSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(source='product', queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1, max_value=99)

    class Meta:
        model = CartItem
        fields = ('id', 'product_id', 'quantity')
        read_only_fields = ('id',)

    def validate(self, attrs):
        product = attrs.get('product', getattr(self.instance, 'product', None))
        quantity = attrs.get('quantity', getattr(self.instance, 'quantity', 1))
        if product and quantity > product.stock:
            raise serializers.ValidationError({'quantity': f'Only {product.stock} item(s) are available.'})
        return attrs


class CartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    name = serializers.CharField(source='product.name', read_only=True)
    unit_price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ('id', 'product_id', 'name', 'quantity', 'unit_price', 'subtotal')

    def get_subtotal(self, obj) -> Decimal:
        return obj.product.price * obj.quantity


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ('id', 'items', 'total', 'updated_at')

    def get_total(self, obj) -> Decimal:
        return sum((item.product.price * item.quantity for item in obj.items.select_related('product')), 0)


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_name', 'quantity', 'price', 'subtotal')

    def get_subtotal(self, obj) -> Decimal:
        return obj.price * obj.quantity


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'customer_name', 'email', 'phone', 'address', 'city', 'pincode',
            'items', 'total_amount', 'status', 'payment_method', 'payment_status', 'created_at',
        )
        read_only_fields = fields


class PlaceOrderSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=100)
    email = serializers.EmailField(required=False, allow_blank=True, default='')
    phone = serializers.CharField(max_length=15)
    address = serializers.CharField()
    city = serializers.CharField(max_length=100)
    pincode = serializers.CharField(max_length=10)
    payment_method = serializers.ChoiceField(choices=('cod',))


class OrderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ('status',)
from decimal import Decimal

