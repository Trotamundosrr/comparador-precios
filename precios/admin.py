from django.contrib import admin

from .models import Category, Price, Product, Promotion, Reservation, Store, Synonym
@admin.register(Synonym)
class SynonymAdmin(admin.ModelAdmin):
    list_display = ("terms",)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "zone", "owner", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("zone", "is_active")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "unit", "category")
    search_fields = ("name", "brand", "barcode")
    list_filter = ("category",)


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ("product", "store", "amount", "available", "updated_at")
    list_filter = ("store", "available")
    search_fields = ("product__name",)


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ("title", "store", "product", "promo_price", "valid_until")
    list_filter = ("store",)

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("code", "store", "product_name", "quantity", "customer_name",
                    "customer_phone", "status", "created_at")
    list_filter = ("store", "status")
    list_editable = ("status",)
    search_fields = ("code", "customer_name", "customer_phone", "product_name")
    readonly_fields = ("code", "created_at")    