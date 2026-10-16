from decimal import Decimal

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Cart, CartItem, Category, Order, Product, Review


class APIAuthTests(APITestCase):
    def test_register_and_get_jwt_tokens(self):
        response = self.client.post(reverse('api-register'), {
            'username': 'new-customer',
            'email': 'customer@example.com',
            'password': 'A-secure-test-password-938!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='new-customer').exists())

        response = self.client.post(reverse('api-token'), {
            'username': 'new-customer',
            'password': 'A-secure-test-password-938!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_cart_requires_authentication(self):
        response = self.client.get(reverse('api-cart'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_rotation_and_logout_revocation(self):
        User.objects.create_user(username='jwt-user', password='JWT-secure-password-982!')
        tokens = self.client.post(reverse('api-token'), {
            'username': 'jwt-user', 'password': 'JWT-secure-password-982!',
        }, format='json').data
        refreshed = self.client.post(reverse('api-token-refresh'), {
            'refresh': tokens['refresh'],
        }, format='json')
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.assertNotEqual(refreshed.data['refresh'], tokens['refresh'])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refreshed.data['access']}")
        logout = self.client.post(reverse('api-logout'), {'refresh': refreshed.data['refresh']}, format='json')
        self.assertEqual(logout.status_code, status.HTTP_205_RESET_CONTENT)
        replay = self.client.post(reverse('api-token-refresh'), {
            'refresh': refreshed.data['refresh'],
        }, format='json')
        self.assertEqual(replay.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_allows_new_password(self):
        User.objects.create_user(username='password-user', password='Old-secure-password-982!')
        tokens = self.client.post(reverse('api-token'), {
            'username': 'password-user', 'password': 'Old-secure-password-982!',
        }, format='json').data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        changed = self.client.post(reverse('api-change-password'), {
            'current_password': 'Old-secure-password-982!',
            'new_password': 'New-secure-password-982!Different',
        }, format='json')
        self.assertEqual(changed.status_code, status.HTTP_200_OK)
        login = self.client.post(reverse('api-token'), {
            'username': 'password-user', 'password': 'New-secure-password-982!Different',
        }, format='json')
        self.assertEqual(login.status_code, status.HTTP_200_OK)


class CatalogAPITests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Books')
        self.product = Product.objects.create(
            category=self.category,
            name='Django for Beginners',
            description='A practical Django guide.',
            price=Decimal('25.00'),
            stock=5,
        )
        self.customer = User.objects.create_user(username='customer', password='Customer-pass-923!')
        self.admin = User.objects.create_superuser(username='manager', email='manager@example.com', password='Manager-pass-923!')

    def test_catalog_search_and_filter_are_public(self):
        response = self.client.get('/api/v1/products/?search=Beginners&price__gte=20')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['name'], self.product.name)

    def test_only_staff_can_create_catalog_products(self):
        payload = {
            'name': 'New title', 'description': 'Description', 'price': '10.00',
            'stock': 3, 'category': self.category.pk,
        }
        self.client.force_authenticate(self.customer)
        denied = self.client.post('/api/v1/products/', payload, format='json')
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        allowed = self.client.post('/api/v1/products/', payload, format='json')
        self.assertEqual(allowed.status_code, status.HTTP_201_CREATED)


class CartAndOrderAPITests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Accessories')
        self.product = Product.objects.create(
            category=self.category,
            name='Canvas bag',
            description='Reusable canvas bag.',
            price=Decimal('12.50'),
            stock=8,
        )
        self.customer = User.objects.create_user(username='buyer', password='Buyer-pass-923!')
        self.other_customer = User.objects.create_user(username='other-buyer', password='Other-pass-923!')
        self.admin = User.objects.create_superuser(username='ops', email='ops@example.com', password='Ops-pass-923!')
        self.client.force_authenticate(self.customer)

    def test_cart_is_scoped_to_signed_in_customer(self):
        response = self.client.post('/api/v1/cart/items/', {
            'product_id': self.product.pk, 'quantity': 2,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        cart_response = self.client.get('/api/v1/cart/')
        self.assertEqual(cart_response.data['total'], Decimal('25.00'))

        self.client.force_authenticate(self.other_customer)
        other_cart = self.client.get('/api/v1/cart/')
        self.assertEqual(other_cart.data['items'], [])

    def test_order_uses_server_prices_and_updates_stock(self):
        CartItem.objects.create(
            cart=Cart.objects.create(user=self.customer), product=self.product, quantity=2,
        )
        response = self.client.post('/api/v1/orders/', {
            'customer_name': 'Test Customer',
            'email': 'buyer@example.com',
            'phone': '9876543210',
            'address': '1 Test Road',
            'city': 'Bengaluru',
            'pincode': '560001',
            'payment_method': 'cod',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['total_amount'], '25.00')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 6)
        self.assertFalse(CartItem.objects.filter(cart__user=self.customer).exists())

        order_id = response.data['id']
        self.client.force_authenticate(self.other_customer)
        self.assertEqual(self.client.get(f'/api/v1/orders/{order_id}/').status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_status_transitions_and_cancellation_restore_stock_once(self):
        order = Order.objects.create(
            user=self.customer, customer_name='Test Customer', email='buyer@example.com',
            phone='9876543210', address='1 Test Road', city='Bengaluru', pincode='560001',
            total_amount=Decimal('25.00'),
        )
        from .models import OrderItem
        OrderItem.objects.create(order=order, product=self.product, quantity=2, price=self.product.price)
        self.product.stock = 6
        self.product.save(update_fields=['stock'])

        self.client.force_authenticate(self.admin)
        response = self.client.patch(f'/api/v1/orders/{order.pk}/', {'status': 'processing'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.patch(f'/api/v1/orders/{order.pk}/', {'status': 'cancelled'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)
        response = self.client.patch(f'/api/v1/orders/{order.pk}/', {'status': 'cancelled'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)


class ReviewAPITests(APITestCase):
    def setUp(self):
        category = Category.objects.create(name='Home')
        self.product = Product.objects.create(
            category=category, name='Mug', description='Ceramic mug',
            price=Decimal('5.00'), stock=4,
        )
        self.customer = User.objects.create_user(username='reviewer', password='Review-pass-923!')
        self.other_customer = User.objects.create_user(username='reader', password='Reader-pass-923!')

    def test_review_is_unique_per_customer_and_owner_controls_edits(self):
        self.client.force_authenticate(self.customer)
        created = self.client.post('/api/v1/reviews/', {
            'product': self.product.pk, 'rating': 5, 'comment': 'Great mug.',
        }, format='json')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

        duplicate = self.client.post('/api/v1/reviews/', {
            'product': self.product.pk, 'rating': 4, 'comment': 'Another review.',
        }, format='json')
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.force_authenticate(self.other_customer)
        denied = self.client.patch(f"/api/v1/reviews/{created.data['id']}/", {'rating': 1}, format='json')
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Review.objects.count(), 1)
