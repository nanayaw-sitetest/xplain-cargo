from .base import *
import os

# 1. TURN OFF DEBUG
DEBUG = False

# 2. TARGET THE PYTHONANYWHERE DOMAIN
# Replace 'yourusername' with your actual PythonAnywhere username
ALLOWED_HOSTS = ['yourusername.pythonanywhere.com']

# 3. CSRF & SECURITY
# Essential so your login forms and "Sync" buttons work on their domain
CSRF_TRUSTED_ORIGINS = ['https://yourusername.pythonanywhere.com']

# 4. HSTS & SSL (Fixes the security.W004 warning)
# Since PythonAnywhere provides HTTPS by default on their subdomains, 
# we can safely turn these on to show the client the "Lock" icon.
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# 5. STATIC FILES (For WhiteNoise)
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'