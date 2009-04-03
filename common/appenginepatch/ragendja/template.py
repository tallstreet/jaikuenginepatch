# -*- coding: utf-8 -*-
"""
This is a set of utilities for faster development with Django templates.

render_to_response() and render_to_string() use RequestContext internally.

The app_prefixed_loader is a template loader that loads directly from the app's
'templates' folder when you specify an app prefix ('app/template.html').

It's possible to register global template libraries by adding this to your
settings:
GLOBALTAGS = (
    'myapp.templatetags.cooltags',
)

The JSONResponse() function automatically converts a given Python object into
JSON and returns it as an HttpResponse.
"""
from django.conf import settings
from django.http import HttpResponse
from django.template import RequestContext, add_to_builtins, loader, \
    TemplateDoesNotExist
from ragendja.apputils import get_app_dirs
import os

# The following defines a template loader that loads templates from a specific
# app based on the prefix of the template path:
# get_template("app/template.html") => app/templates/template.html
# This keeps the code DRY and prevents name clashes.
def app_prefixed_loader(template_name, template_dirs=None):
    packed = template_name.split('/', 1)
    if len(packed) == 2 and packed[0] in app_template_dirs:
        path = os.path.join(app_template_dirs[packed[0]], packed[1])
        try:
            return (open(path).read().decode(settings.FILE_CHARSET), path)
        except IOError:
            pass
    raise TemplateDoesNotExist, template_name
app_prefixed_loader.is_usable = True

def render_to_string(request, template_name, data=None):
    return loader.render_to_string(template_name, data,
        context_instance=RequestContext(request))

def render_to_response(request, template_name, data=None, mimetype=None):
    if mimetype is None:
        mimetype = settings.DEFAULT_CONTENT_TYPE
    if mimetype == 'application/xhtml+xml':
        # Internet Explorer only understands XHTML if it's served as text/html
        if request.META.get('HTTP_ACCEPT').find(mimetype) == -1:
            mimetype = 'text/html'
        # Since XHTML is served with two different MIME types, depending on the
        # browser, we need to tell proxies to serve different versions.
        from django.utils.cache import patch_vary_headers
        patch_vary_headers(response, ['User-Agent'])

    return HttpResponse(render_to_string(request, template_name, data),
        content_type='%s; charset=%s' % (mimetype, settings.DEFAULT_CHARSET))

def JSONResponse(pyobj):
    from ragendja.json import JSONResponse as real_class
    global JSONResponse
    JSONResponse = real_class
    return JSONResponse(pyobj)

def TextResponse(string=''):
    return HttpResponse(string,
        content_type='text/plain; charset=%s' % settings.DEFAULT_CHARSET)

# Load app modules after all definitions, so imports won't break.

# Register global template libraries.
for lib in getattr(settings, 'GLOBALTAGS', ()):
    add_to_builtins(lib)

# This is needed by app_prefixed_loader.
app_template_dirs = get_app_dirs('templates')
