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

import cgi
import logging
import urlparse

from django import http
from django import template
from django.conf import settings
from django.template import loader

from common import api
from common import exception
from common import messages
from common import util
from common import validate


def common_confirm(request):
  message = request.REQUEST['message']
  redirect_to = request.REQUEST['redirect_to']

  try:
    validate.nonce(request, message + redirect_to)

    parts = urlparse.urlparse(redirect_to)
    action_url = parts[2]
    query_dict = cgi.parse_qs(parts[4], keep_blank_values=True)
    query_dict = dict([(k, v[0]) for k, v in query_dict.iteritems()])

  except:
    message = None
    exception.handle_exception(request)


  c = template.RequestContext(request, locals())
  t = loader.get_template('common/templates/confirm.html')
  return http.HttpResponse(t.render(c))


def common_logme(request):
  logging.info("REQUEST: %s", request)
  raise http.Http404()

def common_404(request, template_name='404.html'):
  # You need to create a 404.html template.
  t = loader.get_template(template_name)
  return http.HttpResponseNotFound(
      t.render(template.RequestContext(request, {'request_path': request.path})))


def common_500(request, template_name='500.html'):
  logging.error("An error occurred: %s", str(request))
  # You need to create a 500.html template.
  t = loader.get_template(template_name)
#  return http.HttpResponseServerError(
#      t.render(template.RequestContext(request, {})))
  return http.HttpResponse(t.render(template.RequestContext(request, {})))


def common_error(request):
  message = request.REQUEST['error']

  try:
    validate.error_nonce(request, message)
  except:
    exception.handle_exception(request)
    message = "An error has occurred"

  c = template.RequestContext(request, locals())
  t = loader.get_template('common/templates/error_generic.html')
  return http.HttpResponse(t.render(c))


def common_noslash(request, path=""):
  return http.HttpResponseRedirect("/" + path)


def common_photo_upload(request, success="/", nick=None):
  if not nick:
    nick = request.user.nick
  if request.FILES:
    try:
      # we're going to handle a file upload, wee
      validate.nonce(request, 'change_photo')
      img = request.FILES.get('imgfile')

      if not img:
        raise exception.ValidationError('imgfile must be set')
      validate.avatar_photo_size(img)

      img_url = api.avatar_upload(request.user,
                                  nick,
                                  img.read())
      api.avatar_set_actor(request.user, nick, img_url)
      return util.RedirectFlash(success, "Avatar uploaded")
    except:
      exception.handle_exception(request)

  elif 'avatar' in request.POST:
    try:
      validate.nonce(request, 'change_photo')
      avatar_path = request.POST.get('avatar')
      if not avatar_path:
        raise exception.ValidationError('avatar must be set')

      rv = api.avatar_set_actor(request.user, nick, avatar_path)
      if not rv:
        raise exception.ValidationError('failed to set avatar')
      return util.RedirectFlash(success, "Avatar changed")
    except:
      exception.handle_exception(request)

  if 'delete' in request.REQUEST:
    try:
      validate.nonce(request, 'delete_photo')
      validate.confirm_dangerous(request, 'Delete your photo?')
      rv = api.avatar_clear_actor(request.user, nick)
      return util.RedirectFlash(success, "Avatar deleted")
    except:
      exception.handle_exception(request)


def call_api_from_request(request, api_call):
  """Call an API function 'api_call' if it's present in the request parameters.

  The first parameter to the API call is always the logged-in user.

  The rest of the parameters may come in two forms:
    api_call_name=first_param& ... rest of params
    or
    api_call_name=& ... rest of params

    rest_of_params is always turned into Python keyword arguments.

    If the api_call_name has a value, that is turned into Python positional
    params.
  RETURNS:
    (False, None) if it isn't or the call throws an exception,
    (True, return value from call) otherwise.
  """
  # TODO(termie): make this only accept POST once we update javascript
  #               to turn the links into POSTs
  for request_dict in (request.POST, request.GET):
    if api_call in request_dict:
      call = getattr(api, api_call)
      try:
        validate.nonce(request, api_call)
        confirm_msg = messages.confirmation(api_call)
        if not confirm_msg is None:
          validate.confirm_dangerous(
              request, messages.confirmation(api_call))
        kwparams = util.query_dict_to_keywords(request_dict)
        if '' in kwparams:
          del kwparams['']
        first_param = kwparams.pop(api_call, '')
        params = list()
        if len(first_param):
          params = (first_param,)
        validate.nonce(request, api_call)
        kwparams.pop('_nonce')
        kwparams.pop('confirm', None)
        kwparams.pop('redirect_to', None)
        return (True, call(request.user, *params, **kwparams))
      except:
        exception.handle_exception(request)
  return (False, None)


def handle_view_action(request, actions):
  """Call an API function based on the request parameters if there is a match
  to the keys in 'actions'. Redirect to the corresponding value in 'actions'
  after the call.
  """
  for action in actions.keys():
    called, ret = call_api_from_request(request, action)
    if called:
      redirect = actions[action]
      return util.RedirectFlash(redirect, messages.flash(action))
  return None


def common_design_update(request, nick):
  view = api.actor_get(api.ROOT, nick)
  if request.POST:
    try:
      validate.nonce(request, 'update_design')

      color = request.POST.get('bg_color')
      repeat = request.POST.get('bg_repeat', 'no-repeat')
      if not repeat:
        repeat = ''

      img = request.FILES.get('bg_image')
      img_url = None
      if img:
        img_url = api.background_upload(request.user,
                                        nick,
                                        img.read())
      api.background_set_actor(request.user,
                               nick,
                               img_url,
                               color,
                               repeat)
      return util.RedirectFlash(view.url() + '/settings/design',
                                'design updated')
    except:
      exception.handle_exception(request)

  if request.GET and 'restore' in request.GET:
      api.background_clear_actor(request.user, nick)
      return util.RedirectFlash(view.url() + '/settings/design',
                                'design updated')

  return None
