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

from django.conf import settings as django_settings
from google.appengine.api import users

from common import component
from common import util

def settings(request):

  d = dict([(k, getattr(django_settings, k)) 
            for k in django_settings.get_all_members()])
  return dict(**d)

def components(request):
  return {'component': component}

def flash(request):
  if 'flash' not in request.REQUEST:
    return {}
  
  flash = request.REQUEST['flash']
  nonce = util.create_nonce(None, flash)
  if nonce != request.REQUEST.get('_flash', ''):
    return {}
  return {'flash': flash}

def gaia(request):
  try:
    gaia_user = users.GetCurrentUser()
    gaia_login = users.CreateLoginURL(request.META['PATH_INFO'])
    gaia_logout = users.CreateLogoutURL('/logout')
  except:
    gaia_user = None
    gaia_login = "gaia_login"
    gaia_logout = "gaia_logout"
  return locals()
