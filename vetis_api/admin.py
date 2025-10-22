from django.contrib import admin

from .models import (
    BusinessEntity,
    VetisCredentials,
    Enterprise,
    ProductItem,
    ApiRequestsHistoryRecord,
    Product,
    SubProduct,
    Unit,
    StockEntry,
    PackingType
    )


@admin.register(ApiRequestsHistoryRecord)
class ApiRequestsHistoryRecordAdmin(admin.ModelAdmin):
    list_display = ['datetime', 'soap_action', 'response_status_code', 'comment'] 


@admin.register(VetisCredentials)
class VetisCredentialsAdmin(admin.ModelAdmin):
    list_display = ['name', 'login', 'is_productive']


@admin.register(BusinessEntity)
class BusinessEntityAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'inn']


@admin.register(Enterprise)
class EnterpriseAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'number_list']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'product_type']


@admin.register(SubProduct)
class SubProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'product']


@admin.register(ProductItem)
class ProductItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'producer']


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ['name']


@admin.register(StockEntry)
class StockEntryAdmin(admin.ModelAdmin):
    list_display = ['product_item_name', 'product_type', 'enterprise', 'volume']


@admin.register(PackingType)
class PackingTypeAdmin(admin.ModelAdmin):
    list_display = ['name']