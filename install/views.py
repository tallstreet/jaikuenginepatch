# Copyright 2009 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging

from django import http
from django import template
from django.conf import settings
from django.template import loader

from google.appengine.api import users

from common import api
from common import exception
from common import util
from common import validate

def install_rootuser(request):
  # requires an admin
  user = users.get_current_user()
  if not user:
    return http.HttpResponseRedirect(users.create_login_url('/install'))
  else:
    if not users.is_current_user_admin():
      return http.HttpResponseRedirect('/')
  
  try:
    root_user = api.actor_get(api.ROOT, settings.ROOT_NICK)
  except:
    root_user = None

  if request.POST:
    try:
      logging.warning('Making root user: %s', settings.ROOT_NICK)
      validate.nonce(request, 'create_root')
      root_user = api.user_create_root(api.ROOT)
      return util.RedirectFlash('/install', 'Root user created')
    except:
      exception.handle_exception(request)

  redirect_to = '/'

  c = template.RequestContext(request, locals())    
  t = loader.get_template('install/templates/rootuser.html')
  return http.HttpResponse(t.render(c))
  


