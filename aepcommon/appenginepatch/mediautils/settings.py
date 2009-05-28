from ragendja.settings_post import *
if not on_production_server and MEDIA_URL.startswith('/'):
    if ADMIN_MEDIA_PREFIX.startswith(MEDIA_URL):
        ADMIN_MEDIA_PREFIX = '/generated_media' + ADMIN_MEDIA_PREFIX
    MEDIA_URL = '/generated_media' + MEDIA_URL
    MIDDLEWARE_CLASSES = (
        'mediautils.middleware.MediaMiddleware',
    ) + MIDDLEWARE_CLASSES
