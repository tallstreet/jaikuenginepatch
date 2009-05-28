# -*- coding: utf-8 -*-
"""
Imports urlpatterns from apps, so we can have nice plug-n-play installation. :)
"""
from django.conf.urls.defaults import *
from django.conf import settings

IGNORE_APP_URLSAUTO = getattr(settings, 'IGNORE_APP_URLSAUTO', ())
check_app_imports = getattr(settings, 'check_app_imports', lambda x: None)

urlpatterns = patterns('')

for app in settings.INSTALLED_APPS:
    if app == 'ragendja' or app.startswith('django.') or \
            app in IGNORE_APP_URLSAUTO:
        continue
    try:
        check_app_imports(app)
        urlpatterns += __import__(app + '.urlsauto', {}, {}, ['']).urlpatterns
    except ImportError:
        pass
