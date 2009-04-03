from django.http import HttpResponseServerError
from ragendja.template import render_to_string

def server_error(request, *args, **kwargs):
    return HttpResponseServerError(render_to_string(request, '500.html'))

def maintenance(request, *args, **kwargs):
    return HttpResponseServerError(render_to_string(request,
        'maintenance.html'))
