from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    
    # NEW: AJAX Tracking Preview for the Home Page Dropdown
    path('api/track-preview/', views.track_preview, name='track_preview'),
    
    # Public Tracking Terminal (Standalone Page) - Receives ?tracking_id= from Home
    path('track/', views.track_shipment, name='track'),
    
    # Auth & Identity
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # User Terminal - The High-End Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # MY SHIPMENTS LEDGER - Updated name to 'my_shipments' to fix the error
    path('shipments/', views.shipment_list_view, name='my_shipments'),

    # SHIPMENT DETAIL TERMINAL - Added to fix NoReverseMatch error at /admin-dashboard/
    path('shipment/<int:shipment_id>/', views.shipment_detail_view, name='shipment_detail'),

    # Request Shipment Route - For booking new cargo manifests
    path('request-shipment/', views.request_shipment, name='request_shipment'),

    # SUCCESS PAGE - Redirect target after successful manifest initialization
    path('shipment-success/<str:tracking_number>/', views.shipment_success, name='shipment_success'),

    # --- MANIFEST DELETION CONTROLS ---
    # Individual Delete Terminal
    path('delete-shipment/<int:shipment_id>/', views.delete_shipment, name='delete_shipment'),
    # Bulk Deletion Command
    path('bulk-delete/', views.bulk_delete_shipments, name='bulk_delete_shipments'),

    # --- WOLF CONTROL COMMAND ---
    # Staff-only terminal for Currency and Global Sticky Banner
    path('wolf-control/', views.wolf_control_view, name='wolf_control'),

    # --- FRONTEND ADMIN DASHBOARD ---
    # Staff-only Command Center
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),

    # --- ADMIN AUTHENTICATION TERMINAL ---
    path('wolf-terminal/login/', views.admin_login_view, name='admin_login'),

    # --- GLOBAL SUPPORT TERMINAL ---
    # The breathtaking Contact Us route
    path('contact/', views.contact_view, name='contact'),

    # --- ABOUT US TERMINAL ---
    # Vision and Mission architecture
    path('about/', views.about_view, name='about'),
]