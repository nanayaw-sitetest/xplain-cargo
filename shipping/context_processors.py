from .models import SystemControl, CurrencyRate

def global_system_settings(request):
    # Fetch the single SystemControl instance
    control = SystemControl.objects.first()
    
    # Fetch all active currency rates
    rates = CurrencyRate.objects.all()

    return {
        'global_control': control, # Changed from system_control to match your base file
        'global_rates': rates,
    }