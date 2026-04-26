from django.contrib import admin
from .models import Shipment, CurrencyRate, SystemControl, ViolationLog

@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    # Added 'destination_city' and 'current_location' to the main ledger view
    list_display = ('tracking_number', 'sender_name', 'receiver_name', 'destination_city', 'status', 'transport_mode', 'current_location', 'updated_at')
    
    # Keep your search fields sharp
    search_fields = ('tracking_number', 'sender_name', 'receiver_name', 'destination_city')
    
    # Filter by status and transport mode to keep the ledger organized
    list_filter = ('status', 'transport_mode')
    
    # Protect the tracking number and update timestamps from manual editing
    readonly_fields = ('tracking_number', 'created_at', 'updated_at')

    # Grouping fields for a cleaner look when you are editing a shipment
    fieldsets = (
        ('Identity & Route', {
            'fields': ('tracking_number', 'user', 'transport_mode', 'destination_city')
        }),
        ('Sender & Receiver', {
            'fields': ('sender_name', 'receiver_name', 'receiver_phone')
        }),
        ('Logistics & Pricing', {
            'fields': ('status', 'current_location', 'description', 'weight_kg', 'travel_hours', 'price_per_unit', 'total_fare', 'currency_code')
        }),
        ('Timeline', {
            'fields': ('departure_date', 'estimated_arrival', 'created_at', 'updated_at')
        }),
    )

# Registering the System Global Models so you can edit rates and banners
@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ('currency_code', 'rate_to_ghs', 'last_updated')

@admin.register(SystemControl)
class SystemControlAdmin(admin.ModelAdmin):
    # FIXED: Removed 'use_auto_rates' as it does not exist in the SystemControl model
    list_display = ('banner_message', 'show_banner', 'eur_price_per_kg', 'eur_price_per_km', 'ghs_price_per_kg', 'ghs_price_per_km')
    
    # Grouping the pricing fields together in the detail view
    fieldsets = (
        ('Announcement System', {
            'fields': ('banner_message', 'show_banner', 'banner_color')
        }),
        ('Global Logistics Pricing (EUR)', {
            'fields': ('eur_price_per_kg', 'eur_price_per_km')
        }),
        ('Global Logistics Pricing (GHS)', {
            'fields': ('ghs_price_per_kg', 'ghs_price_per_km')
        }),
    )

# --- NEW: VIOLATION MONITORING TERMINAL ---
@admin.register(ViolationLog)
class ViolationLogAdmin(admin.ModelAdmin):
    list_display = ('violation_type', 'user_attempted', 'ip_address', 'timestamp', 'resolved')
    list_filter = ('violation_type', 'resolved', 'timestamp')
    search_fields = ('user_attempted', 'ip_address', 'user_agent')
    
    # Hardened: Logs cannot be edited, only viewed or deleted
    readonly_fields = ('violation_type', 'user_attempted', 'ip_address', 'user_agent', 'timestamp')
    
    # Allows you to quickly mark threats as 'Resolved' from the list view
    list_editable = ('resolved',)

    def has_add_permission(self, request):
        # Prevent manual creation of violation logs
        return False