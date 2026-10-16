# Shop Hub

A full-stack e-commerce web application built with Django, extended with a secure REST API (JWT authentication, role-based permissions, interactive Swagger docs).



## Screenshots
![Storefront](screenshots/home.png)
![Swagger docs](screenshots/swagger.png)
![JWT login](screenshots/register.png)

## Features

### Storefront (Django templates)
- Browse products and categories, search, product detail pages
- User registration and login
- Cart, checkout and order tracking, with order cancellation

### REST API (`/api/v1/`)
- **JWT authentication:** register, login, token refresh, logout (refresh-token blacklist), change password
- **Role-based permissions:** anyone can read products, only admins can create, edit or delete them
- **Products:** filtering (category, price range, in stock), search, ordering, pagination
- **Cart:** per-user cart with stock validation
- **Orders:** placed from the cart in one database transaction with row locking, so two buyers can't oversell the same stock
- **Order status workflow:** placed → processing → shipped → delivered (admin only); cancelling restores stock
- **Reviews:** one review per user per product, editable only by the owner
- **Rate limiting** on register and login
- **Auto-generated OpenAPI/Swagger documentation**
- **10 automated tests** covering auth, permissions, cart, orders and reviews

## Tech Stack
Python, Django 5.2.18, Django REST Framework, SimpleJWT, django-filter, drf-spectacular, MySQL, HTML/CSS/JavaScript

## API Endpoints

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/register/` | Create an account | No |
| POST | `/api/v1/auth/token/` | Log in, get access and refresh tokens | No |
| POST | `/api/v1/auth/token/refresh/` | Get a new access token | Refresh token |
| POST | `/api/v1/auth/logout/` | Blacklist refresh token | Yes |
| GET | `/api/v1/products/` | List products (search, filter, paginate) | No |
| POST/PUT/DELETE | `/api/v1/products/{id}/` | Manage products | Admin |
| GET | `/api/v1/cart/` | View your cart | Yes |
| POST | `/api/v1/orders/` | Place an order from your cart | Yes |
| GET | `/api/v1/orders/` | Your order history | Yes |
| PATCH | `/api/v1/orders/{id}/` | Update order status | Admin |

Full interactive list: `/api/docs/`

## Getting Started

```bash
git clone [https://github.com/rupalipadhi028/ShopHub-Django.git]
cd ShopHub
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Create a `.env` file (or edit `settings.py`) with your database settings and `SECRET_KEY`, then:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- Website: http://127.0.0.1:8000/
- Swagger docs: http://127.0.0.1:8000/api/docs/

## Try the API
1. `POST /api/v1/auth/register/` to create a user
2. `POST /api/v1/auth/token/` and copy the `access` token
3. Click **Authorize** in Swagger and paste the token
4. Call `GET /api/v1/products/`, add an item to the cart, then place an order

## Running Tests
```bash
python manage.py test products
```

## What I Learned
- Designing a REST API with JWT authentication and custom permissions
- Preventing overselling with `transaction.atomic()` and `select_for_update()`
- Writing API tests with DRF's `APITestCase`
- Documenting an API with OpenAPI/Swagger

## Future Improvements
- React frontend consuming the API
- Online payments
- Deployment with CI/CD

## Author
Rupali Padhi | [https://www.linkedin.com/in/rupali-padhi-5422b5316] | [https://github.com/rupalipadhi028] | Padhirupali511@gmail.com