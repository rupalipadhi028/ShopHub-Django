from django.contrib import admin
from .models import Product, Category, Order, OrderItem


admin.site.register(Product)
admin.site.register(Category)
admin.site.register(OrderItem)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'customer_name',
        'email',
        'total_amount',
        'status',
        'created_at',
    )

    list_filter = (
        'status',
        'created_at',
    )

    search_fields = (
        'customer_name',
        'email',
    )

# Register your models here.
