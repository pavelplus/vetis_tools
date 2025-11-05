from django.contrib import admin

from .models import *


@admin.register(ApiRequestsHistoryRecord)
class ApiRequestsHistoryRecordAdmin(admin.ModelAdmin):
    list_display = ['datetime', 'soap_action', 'response_status_code', 'comment']
    list_filter = ['datetime', 'soap_action']


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

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ['level', 'packing_type', 'quantity', 'product_marks']

class PackageInline(admin.TabularInline):
    model = Package
    fields = ['level', 'packing_type', 'quantity', 'product_marks']
    extra = 0

class StockEntryVetDocumentInline(admin.TabularInline):
    model = StockEntryVetDocument
    fields = ['uuid']
    extra = 0

@admin.register(StockEntry)
class StockEntryAdmin(admin.ModelAdmin):
    list_display = ['product_item_name', 'product_type', 'enterprise', 'volume']
    inlines = [PackageInline, StockEntryVetDocumentInline]
    search_fields = ['entry_number']

# @admin.register(StockEntryMain)
# class StockEntryMainAdmin(admin.ModelAdmin):
#     list_display = ['product_item_name', 'vetd_type', 'volume']

@admin.register(PackingType)
class PackingTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'global_id']