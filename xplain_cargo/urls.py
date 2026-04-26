from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

# Redirect function to catch the default Django accounts path
def redirect_to_login(request):
    return redirect('admin_login')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Intercept the hardcoded Django default and send it to your custom login
    path('accounts/login/', redirect_to_login),

    path('', include('shipping.urls')), # This links our shipping app to the home page
]