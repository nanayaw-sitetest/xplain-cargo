from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from decimal import Decimal
import random
import string

class Shipment(models.Model):
    # Updated Transport Options to reflect your new routes
    TRANSPORT_CHOICES = [
        ('GH_DE', 'Ghana to Germany'),
        ('DE_GH', 'Germany to Ghana'),
        ('GH_GH', 'Within Ghana (Local)'),
        ('DE_DE', 'Within Germany (Local)'),
    ]
    
    # Shipment Milestones
    STATUS_CHOICES = [
        ('PENDING', 'Request Received'),
        ('RECEIVED', 'Received in Warehouse'),
        ('SORTING', 'Sorting & Packaging'),
        ('DEPARTED', 'Departed Origin'),
        ('IN_TRANSIT', 'In Transit'),
        ('ARRIVED_DEST', 'Arrived at Destination'),
        ('CLEARING', 'Customs Clearing'),
        ('READY', 'Ready for Collection'),
        ('DELIVERED', 'Delivered to Recipient'),
        ('CANCELLED', 'Order Cancelled'),
    ]

    # Core Shipping Info
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shipments', null=True, blank=True)
    tracking_number = models.CharField(max_length=20, unique=True, editable=False)
    sender_name = models.CharField(max_length=150)
    sender_phone = models.CharField(max_length=20, blank=True, null=True)
    receiver_name = models.CharField(max_length=150)
    receiver_phone = models.CharField(max_length=20)

    # NEW: High-Precision Coordinate Fields for "Extreme Accuracy" Mapping
    origin_lat = models.DecimalField(max_digits=22, decimal_places=16, null=True, blank=True)
    origin_lng = models.DecimalField(max_digits=22, decimal_places=16, null=True, blank=True)
    destination_lat = models.DecimalField(max_digits=22, decimal_places=16, null=True, blank=True)
    destination_lng = models.DecimalField(max_digits=22, decimal_places=16, null=True, blank=True)
    
    # Logistics Details
    transport_mode = models.CharField(max_length=10, choices=TRANSPORT_CHOICES, default='DE_GH')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Manual Location Update for the Admin
    current_location = models.CharField(max_length=255, default="Origin Warehouse", help_text="Where is the cargo right now?")
    
    # Real-Time Destination Field
    origin_address = models.TextField(blank=True, null=True)
    destination_city = models.CharField(max_length=100, blank=True, null=True, help_text="Final city for local routes")
    
    # Distance/Time-Based Fields
    distance_km = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Calculated road distance in KM")
    
    # UPDATED: Field to store the hours pulled from the request shipment page
    travel_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Duration of travel for local deliveries")
    
    weight_kg = models.DecimalField(max_digits=10, decimal_places=2, help_text="Weight in Kilograms", null=True, blank=True)
    description = models.TextField(blank=True, help_text="What's in the box?")

    # Pricing Logic Fields
    # The base price per KG (International) or per KM/Hour (Local)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Price per KG or per KM/Hour")
    
    # UPDATED: Added total_fare to store the final calculated price in the DB
    total_fare = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Locked-in final price")
    
    currency_code = models.CharField(max_length=3, default='EUR', help_text="EUR, USD, GBP, or GHS")
    
    # Dates
    departure_date = models.DateField(null=True, blank=True)
    # UPDATED: Changed to DateTimeField to allow Admin to set specific time of arrival
    estimated_arrival = models.DateTimeField(null=True, blank=True, help_text="Admin-controlled arrival time")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Generate Tracking Number
        if not self.tracking_number:
            # Generate XP-000-000 style unique ID
            while True:
                random_digits = ''.join(random.choices(string.digits, k=6))
                new_id = f"XP-{random_digits[:3]}-{random_digits[3:]}"
                if not Shipment.objects.filter(tracking_number=new_id).exists():
                    self.tracking_number = new_id
                    break
        
        # DATA INTEGRITY SHIELD: Prevent "None" display in dashboard
        if not self.sender_phone:
            self.sender_phone = "Contact Not Provided"
        
        if not self.receiver_phone:
            self.receiver_phone = "Contact Not Provided"

        # STATUS INTEGRITY CHECK: Ensure the status is valid before saving
        valid_statuses = [choice[0] for choice in self.STATUS_CHOICES]
        
        # CLEANUP: Strip whitespace and handle potential None values
        if self.status:
            self.status = str(self.status).strip().upper()

        if self.status not in valid_statuses:
             if self.pk:
                 original = Shipment.objects.get(pk=self.pk)
                 self.status = original.status
             else:
                 self.status = 'PENDING'
             
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tracking_number} | {self.sender_name} -> {self.receiver_name}"

    @property
    def estimated_hours(self):
        """Returns travel_hours as a string for the template JavaScript call"""
        return str(self.travel_hours)

    @property
    def is_land_only(self):
        """Helper to determine if the route is strictly localized land transport"""
        return self.transport_mode in ['GH_GH', 'DE_DE']

    # FIX: Added receiver_city property to resolve template lookup error
    @property
    def receiver_city(self):
        """Returns destination_city as a fallback for receiver_city in templates"""
        return self.destination_city or "Unknown Destination"

    # NEW: Added sender_city to match the template requirements
    @property
    def sender_city(self):
        """Returns the city part of the origin address for the template"""
        if self.origin_address:
            return self.origin_address.split(',')[0]
        return "Origin Hub"

    @property
    def get_progress_percentage(self):
        """Calculates percentage based on your STATUS_CHOICES"""
        progress_map = {
            'PENDING': 5,
            'RECEIVED': 15,
            'SORTING': 30,
            'DEPARTED': 45,
            'IN_TRANSIT': 60,
            'ARRIVED_DEST': 75,
            'CLEARING': 85,
            'READY': 95,
            'DELIVERED': 100,
            'CANCELLED': 0,
        }
        return progress_map.get(self.status, 0)

    @property
    def get_total_cost(self):
        """
        Calculates total cost. 
        Prioritizes the stored total_fare. Fallback to calculation if total_fare is 0.
        """
        if self.total_fare and self.total_fare > 0:
            return self.total_fare.quantize(Decimal('0.01'))

        is_local = self.transport_mode in ['GH_GH', 'DE_DE']
        unit_amount = self.distance_km if is_local else (self.weight_kg or Decimal('0.00'))

        if not unit_amount or not self.price_per_unit:
            return Decimal('0.00')

        raw_total = unit_amount * self.price_per_unit
        return raw_total.quantize(Decimal('0.01'))

    @property
    def get_ghs_estimation(self):
        """
        Calculates the GHS equivalent for international shipments.
        Uses the 'CurrencyRate' model to fetch the current EUR -> GHS rate.
        """
        # Only calculate for international routes where the currency is EUR
        if self.currency_code == 'EUR' and self.transport_mode in ['DE_GH', 'GH_DE']:
            # Fetch the GHS rate from the CurrencyRate table
            rate_obj = CurrencyRate.objects.filter(currency_code='GHS').first()
            if rate_obj and rate_obj.rate_to_ghs:
                # Multiply the total_fare by the exchange rate
                estimation = self.get_total_cost * rate_obj.rate_to_ghs
                return estimation.quantize(Decimal('0.01'))
        
        return Decimal('0.00')

    @property
    def get_subunits_total(self):
        """
        Calculates the total cost in the smallest unit.
        Returns Cents if currency is EUR, or Pesewas if currency is GHS.
        """
        return int(self.get_total_cost * 100)

    @property
    def get_subunit_name(self):
        """Returns 'Cents' or 'Pesewas' based on currency"""
        if self.currency_code == 'EUR': return 'Cents'
        if self.currency_code == 'GHS': return 'Pesewas'
        return 'Subunits'

    @property
    def get_currency_symbol(self):
        """Returns the appropriate symbol for the dashboard display"""
        symbols = {
            'EUR': '€',
            'GHS': '₵',
            'USD': '$',
            'GBP': '£',
        }
        return symbols.get(self.currency_code, self.currency_code)

    class Meta:
        ordering = ['-created_at']


# --- SYSTEM GLOBAL MODELS ---

class CurrencyRate(models.Model):
    """Stores multiple currency rates (Base is EUR)"""
    currency_code = models.CharField(max_length=3, unique=True, help_text="e.g. USD, GHS, GBP")
    rate_to_ghs = models.DecimalField(max_digits=10, decimal_places=4, help_text="How many of this currency equals 1 EUR?")
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"1 EUR = {self.rate_to_ghs} {self.currency_code}"

class SystemControl(models.Model):
    """The master switch for the site-wide banner and currency mode"""
    banner_message = models.TextField(blank=True, help_text="The sticky message displayed to all users.")
    show_banner = models.BooleanField(default=False)
    
    # Global Logistics Pricing Config
    eur_price_per_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="EUR price for international routes per KG")
    eur_price_per_km = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="EUR price for local land routes per KM")
    
    # GHS Rates
    ghs_price_per_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="GHS price for international routes per KG")
    ghs_price_per_km = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="GHS price for local land routes per KM")

    # Styling for the banner
    BANNER_STYLES = [('bg-blue-600', 'Info Blue'), ('bg-red-600', 'Alert Red'), ('bg-emerald-600', 'Success Green')]
    banner_color = models.CharField(max_length=20, choices=BANNER_STYLES, default='bg-blue-600')

    def save(self, *args, **kwargs):
        """Ensures only one instance of SystemControl exists"""
        if not self.pk and SystemControl.objects.exists():
            raise ValidationError("There can only be one SystemControl instance.")
        return super(SystemControl, self).save(*args, **kwargs)

    class Meta:
        verbose_name = "System Wide Control"
        verbose_name_plural = "System Wide Control"

class ViolationLog(models.Model):
    """MAXIMUM PARANOIA: Logs unauthorized access and failed login attempts"""
    VIOLATION_TYPES = [
        ('UNAUTHORIZED_ACCESS', 'Access Denied (Non-Staff)'),
        ('UNAUTHORIZED_ADMIN_ATTEMPT', 'Unauthorized Admin Terminal Attempt'),
        ('FAILED_LOGIN', 'Failed Login Attempt'),
        ('BRUTE_FORCE_SIGNUP', 'Suspicious Signup Activity'),
    ]
    
    user_attempted = models.CharField(max_length=150, blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    violation_type = models.CharField(max_length=50, choices=VIOLATION_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    user_agent = models.TextField(blank=True, null=True)
    resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.violation_type} | {self.ip_address} | {self.timestamp}"

    class Meta:
        ordering = ['-timestamp']

# --- NEW: GLOBAL SUPPORT MODELS ---

class ContactInquiry(models.Model):
    """Captures 'Breathtaking' interactions from the Contact Us terminal"""
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True) # NEW: Added to capture phone field
    subject = models.CharField(max_length=255, blank=True, null=True)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"Inquiry from {self.name} - {self.timestamp.date()}"

    class Meta:
        verbose_name = "Contact Inquiry"
        verbose_name_plural = "Contact Inquiries"
        ordering = ['-timestamp']