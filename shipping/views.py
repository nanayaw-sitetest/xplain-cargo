from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from decimal import Decimal
from django.contrib.auth.decorators import login_required # New: Security decorator
from .models import Shipment, SystemControl, CurrencyRate, ViolationLog, ContactInquiry # Added ContactInquiry
import random # For the mock API
import requests # Make sure to run 'pip install requests'
from django.utils import timezone

def get_client_ip(request):
    """Helper to extract the IP address of the user"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def home(request):
    return render(request, 'shipping/home.html')

def track_preview(request):
    """
    NEW: AJAX endpoint for the home page dropdown.
    Returns basic shipment info without requiring login.
    UPDATED: Added financial statement and destination city logic.
    """
    tracking_id = request.GET.get('tracking_id', '').strip().upper()
    if not tracking_id:
        return JsonResponse({'error': 'No ID provided'}, status=400)
    
    try:
        # UPDATED: Using iexact for case-insensitive matching to ensure it finds the record
        shipment = Shipment.objects.get(tracking_number__iexact=tracking_id)
        
        # LOGIC: If user is logged in, link goes to track page. 
        # If not, link goes to login page with a 'next' redirect back to track.
        if request.user.is_authenticated:
            target_url = f"/track/?tracking_id={shipment.tracking_number}"
        else:
            target_url = f"/login/?next=/track/?tracking_id={shipment.tracking_number}"

        # FALLBACK LOGIC for N/A issues
        display_origin = shipment.current_location or "Origin Warehouse"
        # Prioritize destination_city as the primary destination field
        display_destination = shipment.destination_city or "Global Transit"

        # Financial Statement Calculation
        formatted_total = f"{shipment.get_currency_symbol}{shipment.get_total_cost}"

        data = {
            'found': True,
            'exists': True,
            'tracking_id': shipment.tracking_number,
            'tracking_number': shipment.tracking_number,
            'status': shipment.get_status_display(),
            'origin': display_origin,
            'destination': display_destination,
            'financial_statement': formatted_total, # New field for the modal
            'is_authenticated': request.user.is_authenticated,
            'target_url': target_url
        }
        return JsonResponse(data)
    except Shipment.DoesNotExist:
        return JsonResponse({'found': False, 'exists': False}, status=200)

@login_required
def dashboard_view(request):
    # Fetch shipments belonging to the logged-in user
    user_shipments = Shipment.objects.filter(user=request.user).order_by('-created_at')
    
    # Calculate Total EUR Revenue
    # UPDATED: Using total_fare database field for accurate dashboard reporting
    total_eur = sum(
        (shipment.total_fare for shipment in user_shipments if shipment.currency_code == 'EUR'), 
        Decimal('0.00')
    )
    
    # Calculate Total GHS Revenue
    # UPDATED: Using total_fare database field for accurate dashboard reporting
    total_ghs = sum(
        (shipment.total_fare for shipment in user_shipments if shipment.currency_code == 'GHS'), 
        Decimal('0.00')
    )
    
    # UPDATED: Pagination Logic for Shipments
    paginator = Paginator(user_shipments, 10) # 10 lists per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj, # Pass the paginated object to template
        'shipments': page_obj.object_list, # Keeps compatibility with your existing template variable name
        'total_shipments': user_shipments.count(),
        'active_shipments': user_shipments.exclude(status='DELIVERED').count(),
        'total_eur': total_eur,
        'total_ghs': total_ghs,
    }
    return render(request, 'shipping/dashboard.html', context)

# NEW: Bulk Deletion Logic to resolve NoReverseMatch
@login_required
def bulk_delete_shipments(request):
    if request.method == 'POST':
        shipment_ids = request.POST.getlist('shipment_ids')
        if shipment_ids:
            # Security check: Ensure user only deletes their own shipments
            Shipment.objects.filter(id__in=shipment_ids, user=request.user).delete()
    return redirect('dashboard')

# NEW: Individual Deletion Logic
@login_required
def delete_shipment(request, shipment_id):
    shipment = get_object_or_404(Shipment, id=shipment_id, user=request.user)
    shipment.delete()
    return redirect('dashboard')

@login_required
def shipment_list_view(request):
    """
    NEW: View for the dedicated Shipment Ledger page.
    Renders the shipments.html template.
    """
    if request.method == 'POST':
        action = request.POST.get('action')

        # SECURITY: Filter by user=request.user ensures users only touch their own data
        if action == 'delete_shipment':
            shipment_id = request.POST.get('shipment_id')
            try:
                Shipment.objects.filter(id=shipment_id, user=request.user).delete()
                messages.success(request, "Shipment manifest removed from your ledger.")
            except Exception:
                messages.error(request, "Action failed: Record not found or access denied.")

        elif action == 'bulk_delete_shipments':
            shipment_ids = request.POST.getlist('shipment_ids')
            if shipment_ids:
                deleted_count = Shipment.objects.filter(id__in=shipment_ids, user=request.user).delete()[0]
                messages.success(request, f"Successfully purged {deleted_count} shipment records.")
            else:
                messages.warning(request, "No shipments were selected for deletion.")

        return redirect('my_shipments')

    user_shipments = Shipment.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'shipments': user_shipments,
        'total_shipments': user_shipments.count(),
    }
    return render(request, 'shipping/shipments.html', context)

# --- SHIPMENT DETAIL TERMINAL ---
@login_required
def shipment_detail_view(request, shipment_id):
    """
    NEW: Renders the high-end detailed view for a specific shipment manifest.
    Used by the Admin Dashboard and User Ledger.
    """
    # Fetch the shipment or return 404. 
    # Logic: Staff can see all, regular users only see their own.
    if request.user.is_staff:
        shipment = get_object_or_404(Shipment, id=shipment_id)
    else:
        shipment = get_object_or_404(Shipment, id=shipment_id, user=request.user)

    context = {
        'shipment': shipment,
    }
    return render(request, 'shipping/shipment_detail.html', context)

@login_required
def request_shipment(request):
    # Determine the route based on the URL parameter (e.g., ?route=GH_DE)
    selected_route = request.GET.get('route', 'DE_GH')
    
    # FETCH GLOBAL RATES from SystemControl
    control = SystemControl.objects.first()
    
    # NEW: Fetch the GHS exchange rate for the calculator estimation
    # Corrected: We look for the 'GHS' currency record to get its rate relative to EUR
    exchange_rate = CurrencyRate.objects.filter(currency_code='GHS').first()

    if request.method == 'POST':
        sender_name = request.POST.get('sender_name')
        # FIXED: Captured sender_phone which was missing in your previous version
        sender_phone = request.POST.get('sender_phone')
        receiver_name = request.POST.get('receiver_name')
        receiver_phone = request.POST.get('receiver_phone')
        transport_mode = request.POST.get('transport_mode')
        description = request.POST.get('description')
        
        # Capture numeric data for calculation
        # FIXED: Updated 'weight' to 'weight_kg' to match your HTML name attribute
        weight = Decimal(request.POST.get('weight_kg') or '0.00')
        distance = Decimal(request.POST.get('distance_km') or '0.00')
        
        # UPDATED: Capture hours from the request page for local deliveries
        hours = Decimal(request.POST.get('travel_hours') or '0.00')
        
        # NEW: Capture Destination City instead of raw address
        dest_city = request.POST.get('destination_city')

        # COORDINATE CAPTURE: Capturing the high-precision map data
        o_lat = request.POST.get('origin_lat')
        o_lng = request.POST.get('origin_lng')
        d_lat = request.POST.get('destination_lat')
        d_lng = request.POST.get('destination_lng')

        # Logic to set currency and base price based on route and Admin rates
        current_currency = 'EUR'
        base_price = Decimal('0.00')
        final_total_fare = Decimal('0.00')
        
        if selected_route == 'GH_GH':
            current_currency = 'GHS'
            # Logic: Multiplies distance (captured as distance_km) by the GHS rate
            base_price = control.ghs_price_per_km if control else Decimal('0.00')
            final_total_fare = distance * base_price
            transport_mode = 'LAND'
            
        elif selected_route == 'DE_DE':
            current_currency = 'EUR'
            # Logic: Multiplies distance by the EUR rate
            base_price = control.eur_price_per_km if control else Decimal('0.00')
            final_total_fare = distance * base_price
            transport_mode = 'LAND'

        elif selected_route == 'DE_GH': 
            current_currency = 'EUR'
            # Logic: Multiplies weight by the EUR KG rate
            base_price = control.eur_price_per_kg if control else Decimal('0.00')
            final_total_fare = weight * base_price

        elif selected_route == 'GH_DE': 
            current_currency = 'EUR'
            # Logic: Multiplies weight by the EUR KG rate
            base_price = control.eur_price_per_kg if control else Decimal('0.00')
            final_total_fare = weight * base_price

        # Create the shipment manifest with the calculated fare and coordinates
        new_shipment = Shipment.objects.create(
            user=request.user,
            sender_name=sender_name,
            # FIXED: Now passing the captured sender_phone to the database
            sender_phone=sender_phone,
            receiver_name=receiver_name,
            receiver_phone=receiver_phone,
            transport_mode=selected_route, 
            description=description,
            destination_city=dest_city,
            origin_lat=Decimal(o_lat) if o_lat else None,
            origin_lng=Decimal(o_lng) if o_lng else None,
            destination_lat=Decimal(d_lat) if d_lat else None,
            destination_lng=Decimal(d_lng) if d_lng else None,
            distance_km=distance,
            weight_kg=weight,
            travel_hours=hours,
            price_per_unit=base_price, 
            total_fare=final_total_fare,
            currency_code=current_currency,
            status='PENDING',
            current_location="Origin Warehouse"
        )
        
        return redirect('shipment_success', tracking_number=new_shipment.tracking_number)

    return render(request, 'shipping/request_shipment.html', {
        'selected_route': selected_route,
        'control': control,
        'exchange_rate': exchange_rate  # Added to context for the HTML calculator
    })

def shipment_success(request, tracking_number):
    """
    Renders the confetti success page after a shipment is created.
    """
    return render(request, 'shipping/success.html', {'tracking_number': tracking_number})

def track_shipment(request):
    """
    Public tracking view. 
    Handles the search and displays the shipment progress.
    """
    tracking_id = request.GET.get('tracking_id')
    shipment = None
    error_message = None

    if tracking_id:
        try:
            shipment = Shipment.objects.get(tracking_number=tracking_id.strip().upper())
        except Shipment.DoesNotExist:
            error_message = "Tracking ID not found. Please verify the code and try again."

    context = {
        'shipment': shipment,
        'error_message': error_message,
        'query': tracking_id,
        'estimated_hours': shipment.travel_hours if shipment else "0"
    }
    return render(request, 'shipping/track.html', context)

def signup_view(request):
    if request.method == 'POST':
        fullname = request.POST.get('fullname')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if User.objects.filter(username=email).exists():
            messages.error(request, "A user with this email already exists.")
            return render(request, 'shipping/signup.html')
        
        user = User.objects.create_user(username=email, email=email, password=password)
        user.first_name = fullname
        user.save()
        
        messages.success(request, "Account created successfully! Please log in to continue.")
        return redirect('login')
        
    return render(request, 'shipping/signup.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('username') 
        password = request.POST.get('password')
        
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            login(request, user)
            
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
                
            return redirect('dashboard') 
        else:
            ViolationLog.objects.create(
                user_attempted=email,
                ip_address=get_client_ip(request),
                violation_type='FAILED_LOGIN',
                user_agent=request.META.get('HTTP_USER_AGENT', 'Unknown')
            )
            messages.error(request, "Invalid email or password.")
            
    return render(request, 'shipping/login.html')

def logout_view(request):
    logout(request)
    return redirect('home')

# --- FRONTEND ADMIN DASHBOARD ---

@login_required
def admin_dashboard_view(request):
    if not request.user.is_staff:
        messages.error(request, "Security Clearance Required.")
        return redirect('admin_login')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_shipment':
            shipment_id = request.POST.get('shipment_id')
            try:
                shipment = Shipment.objects.get(id=shipment_id)
                shipment.current_location = request.POST.get(f'current_location_{shipment_id}')
                shipment.status = request.POST.get(f'status_{shipment_id}')
                
                # UPDATED: Capture the Estimated Arrival from the admin form
                # Logic: If the value is empty or the string "None", we set it to Python None (NULL in DB)
                eta_val = request.POST.get(f'estimated_arrival_{shipment_id}')
                if eta_val and eta_val.strip() != "" and eta_val != "None":
                    shipment.estimated_arrival = eta_val
                else:
                    shipment.estimated_arrival = None
                
                shipment.save()
                messages.success(request, f"Shipment {shipment.tracking_number} synchronized.")
            except Shipment.DoesNotExist:
                messages.error(request, "Shipment record not found.")

        # NEW: Cancel Shipment Logic
        elif action == 'cancel_shipment':
            shipment_id = request.POST.get('shipment_id')
            try:
                shipment = Shipment.objects.get(id=shipment_id)
                shipment.status = 'CANCELLED'
                shipment.current_location = "ORDER CANCELLED"
                shipment.save()
                messages.success(request, f"Shipment {shipment.tracking_number} has been officially cancelled.")
            except Shipment.DoesNotExist:
                messages.error(request, "Target shipment not found.")

        # NEW: Individual Shipment Deletion
        elif action == 'delete_shipment':
            shipment_id = request.POST.get('shipment_id')
            try:
                Shipment.objects.filter(id=shipment_id).delete()
                messages.success(request, "Shipment record purged from system.")
            except Exception:
                messages.error(request, "Error: Record could not be removed.")

        # NEW: Bulk Shipment Deletion
        elif action == 'bulk_delete_shipments':
            shipment_ids = request.POST.getlist('shipment_ids')
            if shipment_ids:
                count = Shipment.objects.filter(id__in=shipment_ids).count()
                Shipment.objects.filter(id__in=shipment_ids).delete()
                messages.success(request, f"System Purge Complete: {count} records removed.")
            else:
                messages.warning(request, "No shipments selected for purge.")

        elif action == 'delete_violation':
            violation_id = request.POST.get('violation_id')
            try:
                ViolationLog.objects.filter(id=violation_id).delete()
                messages.success(request, f"Violation Log #{violation_id} purged successfully.")
            except Exception:
                messages.error(request, "Record not found or already deleted.")

        # NEW: Delete Contact Inquiry
        elif action == 'delete_inquiry':
            inquiry_id = request.POST.get('inquiry_id')
            try:
                ContactInquiry.objects.filter(id=inquiry_id).delete()
                messages.success(request, "Inquiry purged from terminal.")
            except Exception:
                messages.error(request, "Failed to remove inquiry.")

        elif request.POST.get('update_banner'):
            control, created = SystemControl.objects.get_or_create(id=1)
            control.banner_message = request.POST.get('banner_text')
            control.show_banner = 'show_banner' in request.POST
            control.banner_color = request.POST.get('banner_color')
            
            # FIXED: Corrected names to match admin_dashboard.html
            eur_kg = request.POST.get('eur_price_per_kg')
            eur_km = request.POST.get('eur_price_per_km')
            ghs_kg = request.POST.get('ghs_price_per_kg')
            ghs_km = request.POST.get('ghs_price_per_km')

            if eur_kg: control.eur_price_per_kg = eur_kg
            if eur_km: control.eur_price_per_km = eur_km
            if ghs_kg: control.ghs_price_per_kg = ghs_kg
            if ghs_km: control.ghs_price_per_km = ghs_km
            
            control.save()

            # NEW: Sync all shipment ETAs when the global "Push" button is clicked
            all_shipments = Shipment.objects.all()
            for s in all_shipments:
                # Capture the specific ETA value for each shipment from the table inputs
                shipment_eta = request.POST.get(f'estimated_arrival_{s.id}')
                # Fix for the validation error during global push
                if shipment_eta and shipment_eta.strip() != "" and shipment_eta != "None":
                    s.estimated_arrival = shipment_eta
                else:
                    s.estimated_arrival = None
                s.save()

            messages.success(request, "Global Pricing, Announcements, and Shipment ETAs synchronized.")

        elif request.POST.get('update_rates'):
            rates_to_update = CurrencyRate.objects.all()
            for rate in rates_to_update:
                new_val = request.POST.get(f'rate_{rate.currency_code}')
                if new_val:
                    rate.rate_to_ghs = new_val
                    rate.save()
            messages.success(request, "FX Markets updated successfully.")
            
        return redirect('admin_dashboard')

    # UPDATED: Pagination Logic for Shipments
    all_shipment_list = Shipment.objects.all().order_by('-created_at')
    paginator = Paginator(all_shipment_list, 10) # 10 lists per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    violations = ViolationLog.objects.filter(resolved=False).order_by('-timestamp')[:15]
    inquiries = ContactInquiry.objects.all().order_by('-timestamp')[:15] # NEW: Fetch inquiries
    control = SystemControl.objects.first()
    rates = CurrencyRate.objects.all()
    
    context = {
        'page_obj': page_obj, # Pass the paginated object to template
        'recent_shipments': page_obj.object_list, # Keeps compatibility with your existing template variable name
        'violations': violations,
        'inquiries': inquiries, # NEW
        'control': control,
        'rates': rates,
    }
    return render(request, 'shipping/admin_dashboard.html', context)

def admin_login_view(request):
    if request.method == 'POST':
        email = request.POST.get('username')
        try:
            user_obj = User.objects.get(email=email)
            actual_username = user_obj.username
        except User.DoesNotExist:
            actual_username = email

        user = authenticate(request, username=actual_username, password=request.POST.get('password'))
        
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Access Denied: Restricted to Command Staff only.")
            ViolationLog.objects.create(
                user_attempted=email,
                ip_address=get_client_ip(request),
                violation_type='UNAUTHORIZED_ADMIN_ATTEMPT',
                user_agent=request.META.get('HTTP_USER_AGENT', 'Unknown')
            )
            
    return render(request, 'shipping/admin_login.html')

@login_required
def wolf_control_view(request):
    if not request.user.is_staff:
        messages.error(request, "Security Clearance Required.")
        return redirect('admin_login')

    control, created = SystemControl.objects.get_or_create(pk=1)
    rates = CurrencyRate.objects.all()
    recent_shipments = Shipment.objects.all().order_by('-created_at')[:10]
    violations = ViolationLog.objects.filter(resolved=False).order_by('-timestamp')[:15]
    inquiries = ContactInquiry.objects.all().order_by('-timestamp')[:15] # NEW: Fetch inquiries

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_shipment':
            shipment_id = request.POST.get('shipment_id')
            new_status = request.POST.get(f'status_{shipment_id}')
            new_location = request.POST.get(f'current_location_{shipment_id}')
            
            try:
                shipment = Shipment.objects.get(id=shipment_id)
                if new_status: shipment.status = new_status
                if new_location: shipment.current_location = new_location
                shipment.save()
                messages.success(request, f"Shipment {shipment.tracking_number} synced successfully.")
            except Shipment.DoesNotExist:
                messages.error(request, "Target Shipment not found.")

        elif action == 'delete_violation':
            violation_id = request.POST.get('violation_id')
            ViolationLog.objects.filter(id=violation_id).delete()
            messages.success(request, "Security breach log purged.")

        # NEW: Delete Contact Inquiry logic for Wolf Control
        elif action == 'delete_inquiry':
            inquiry_id = request.POST.get('inquiry_id')
            ContactInquiry.objects.filter(id=inquiry_id).delete()
            messages.success(request, "Inquiry purged.")

        elif 'update_banner' in request.POST:
            control.banner_message = request.POST.get('banner_text')
            control.show_banner = 'show_banner' in request.POST
            control.banner_color = request.POST.get('banner_color')
            control.use_auto_rates = 'use_auto_rates' in request.POST
            
            eur_kg = request.POST.get('eur_kg')
            eur_km = request.POST.get('eur_km')
            ghs_kg = request.POST.get('ghs_kg')
            ghs_km = request.POST.get('ghs_km')

            if eur_kg: control.eur_price_per_kg = eur_kg
            if eur_km: control.eur_price_per_km = eur_km
            if ghs_kg: control.ghs_price_per_kg = ghs_kg
            if ghs_km: control.ghs_price_per_km = ghs_km
            
            control.save()
            messages.success(request, "Global System Settings Updated!")

        elif 'update_rates' in request.POST:
            if control.use_auto_rates:
                try:
                    response = requests.get('https://api.frankfurter.app/latest?from=EUR&to=GHS,USD,GBP', timeout=5)
                    data = response.json()
                    if response.status_code == 200:
                        fetched_rates = data.get('rates', {})
                        for rate in rates:
                            code = rate.currency_code.upper()
                            if code in fetched_rates:
                                rate.rate_to_ghs = fetched_rates[code]
                                rate.last_updated = timezone.now()
                                rate.save()
                        messages.success(request, f"Live Sync Complete. Markets updated via Frankfurter API.")
                    else:
                        messages.error(request, "Market API returned an error.")
                except requests.RequestException:
                    messages.error(request, "Connection Timeout: Could not reach Global Market API.")
            else:
                for rate in rates:
                    new_val = request.POST.get(f'rate_{rate.currency_code}')
                    if new_val:
                        rate.rate_to_ghs = new_val
                        rate.last_updated = timezone.now()
                        rate.save()
                messages.success(request, "Manual Rates Updated!")
            
        return redirect('wolf_control')

    context = {
        'control': control, 
        'rates': rates, 
        'recent_shipments': recent_shipments, 
        'violations': violations,
        'inquiries': inquiries, # NEW
    }
    return render(request, 'shipping/admin_dashboard.html', context)

# --- GLOBAL SUPPORT TERMINAL ---
def contact_view(request):
    """
    Renders the Support Terminal and dispatches form data to the admin email.
    """
    if request.method == 'POST':
        # Extract manifest data from the form
        name = request.POST.get('contact_name')
        sender_email = request.POST.get('email')
        subject_type = request.POST.get('subject')
        phone = request.POST.get('phone')
        user_message = request.POST.get('message')

        # Construct the internal notification email
        email_subject = f"LOGISTICS INQUIRY: {subject_type} from {name}"
        email_body = f"""
        X-PLAIN GLOBAL SUPPORT MANIFEST
        -------------------------------
        SENDER: {name}
        EMAIL: {sender_email}
        PHONE: {phone}
        TYPE: {subject_type}
        
        MESSAGE:
        {user_message}
        -------------------------------
        System Timestamp: {timezone.now()}
        """

        try:
            # Send the email to your personal address
            send_mail(
                email_subject,
                email_body,
                settings.DEFAULT_FROM_EMAIL,  # Must be configured in settings.py
                ['nanayeezy@gmail.com'],      # Your target recipient
                fail_silently=False,
            )
            messages.success(request, f"Manifest Dispatched! Stand by, {name}. Our team has been notified.")
        except Exception as e:
            # Fallback if email server fails
            messages.error(request, "Communication uplink failed. Please try again or use WhatsApp.")
        
        return redirect('contact')
        
    return render(request, 'shipping/contact.html')
def about_view(request):
    """
    Renders the About Us terminal featuring the corporate vision and mission.
    """
    return render(request, 'shipping/about.html')