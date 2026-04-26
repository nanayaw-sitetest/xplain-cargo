"""
WSGI config for xplain_cargo project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('xplain_cargo.settings.local', 'xplain_cargo.settings')

application = get_wsgi_application()
