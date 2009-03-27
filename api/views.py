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

import datetime
import logging
import StringIO

from django import http
from django import template
from django.conf import settings
from django.core import serializers
from django.template import loader

import simplejson

from google.appengine.ext import db

from api import xmlrpc
from common import api
from common import decorator
from common import exception
from common import im
from common import legacy
from common import messages
from common import oauth_util
from common import sms
from common import user
from common import util
from common import validate
from common import views as common_views
from common.protocol import xmpp
from common.protocol import sms as sms_protocol


_XML_RPC_DISPATCHER = xmlrpc.XmlRpcDispatcher(api.PublicApi.methods)

@decorator.login_required
def api_keys(request):

  # special case this because we want to redirect to the edit page
  if 'oauth_generate_consumer' in request.POST:
    action = 'oauth_generate_consumer'
    (called, rv) = common_views.call_api_from_request(request, action)
    return util.RedirectFlash(rv.url(), messages.flash(action))

  handled = common_views.handle_view_action(
      request,
      {}
  )
  if handled:
    return handled

  # Get list of consumer tokenss for this actor
  consumer_tokens = api.oauth_get_actor_consumers(request.user,
                                                  request.user.nick)

  # TODO(termie): Get list of access tokens this actor has given others
  access_tokens = []

  # for templates
  full_page = 'Keys'
  page = 'keys'
  area = 'api'

  c = template.RequestContext(request, locals())
  t = loader.get_template('api/templates/keys.html')
  return http.HttpResponse(t.render(c))


@decorator.login_required
def api_key(request, consumer_key):
  handled = common_views.handle_view_action(
      request,
      {
        'oauth_consumer_delete': '/api/keys',
        'oauth_consumer_update': request.path,
      }
  )
  if handled:
    return handled

  consumer_token_ref = api.oauth_get_consumer(request.user, consumer_key)

  # for templates
  full_page = 'Keys / %s' % consumer_key
  page = 'key'
  area = 'api'
  OAUTH_WEB = 'web'
  OAUTH_DESKTOP = 'desktop'
  OAUTH_MOBILE = 'mobile'

  c = template.RequestContext(request, locals())
  t = loader.get_template('api/templates/key.html')
  return http.HttpResponse(t.render(c))

@decorator.login_required
def api_key_legacy(request):
  if not settings.API_ALLOW_LEGACY_AUTH:
    raise http.Http404()
  key = legacy.generate_personal_key(request.user)

  return http.HttpResponse(key)

def api_doc(request, doc):
  content_template = loader.get_template('api/templates/built_%s.html' % doc)
  content = content_template.render(template.Context())

  # for templates
  full_page = 'Documentation'
  page = 'docs'
  area = 'api'

  c = template.RequestContext(request, locals())
  t = loader.get_template('api/templates/doc.html')
  return http.HttpResponse(t.render(c))


def api_docs(request):

  # get the list of api methods for the index
  methods = api.PublicApi.methods.keys()
  api_methods = {}
  for m in methods:
    parts = m.split('_')
    category = parts[0]
    api_methods.setdefault(category, [])
    api_methods[category].append(m)
  api_methods = api_methods.items()
  api_methods.sort()

  # for templates
  full_page = 'Documentation'
  page = 'docs'
  area = 'api'

  c = template.RequestContext(request, locals())
  t = loader.get_template('api/templates/docs.html')
  return http.HttpResponse(t.render(c))

@decorator.login_required
def api_tokens(request):
  """Show the user the set of tokens currently enabled, and allow them to
  disable/delete them.
  """
  handled = common_views.handle_view_action(
      request,
      {
        'oauth_revoke_access_token': '/api/tokens',
      }
  )
  if handled:
    return handled

  consumer_tokens = api.oauth_get_actor_tokens(request.user,
                                               request.user.nick)

  # for templates
  full_page = 'Tokens'
  page = 'tokens'
  area = 'api'

  c = template.RequestContext(request, locals())
  t = loader.get_template('api/templates/tokens.html')
  return http.HttpResponse(t.render(c))


# OAuth stuff
def api_request_token(request):
  """
  checks that the request is well formed
  makes sure the consumer is valid
  makes a new request token
  returns the request token & secret
  """
  token = oauth_util.handle_fetch_request_token(request)
  return http.HttpResponse(token.to_string())


@decorator.login_required
def api_authorize(request):
  """
  checks on the request token provided or ask the user enter one
  allows the user to authorize this
  if consumer style is web and a callback is provided redirect to it
    otherwise suggest that the user notify their application that authorization
    has completed
  """
  oauth_token = request.REQUEST.get('oauth_token', None)
  if not oauth_token:
    # please enter token page
    pass

  oauth_token_ref = api.oauth_get_request_token(api.ROOT, oauth_token)
  if not oauth_token_ref:
    raise Exception("bad token")

  oauth_consumer_ref = api.oauth_get_consumer(api.ROOT,
                                              oauth_token_ref.consumer)
  if not oauth_consumer_ref:
    raise Exception("bad consumer")
  if "active" != oauth_consumer_ref.status:
    raise Exception("inactive consumer")
  
  perms = request.REQUEST.get('perms', 'read')
  if request.POST:
    # we posted to this page to authorize
    # TODO verify nonce
    validate.nonce(request, "authorize_token")

    api.oauth_authorize_request_token(api.ROOT, oauth_token_ref.key_,
                                      actor=request.user.nick, perms=perms)

    oauth_callback = request.POST.get("oauth_callback", None)
    if oauth_callback and oauth_consumer_ref.type == "web":
      return http.HttpResponseRedirect(oauth_callback)

    c = template.RequestContext(request, locals())
    t = loader.get_template('api/templates/authorized.html')
    return http.HttpResponse(t.render(c))
  
  perms_pretty = {'read': 'view',
                  'write': 'view and update',
                  'delete': 'view, update and delete'}[perms]

  c = template.RequestContext(request, locals())
  t = loader.get_template('api/templates/authorize.html')
  return http.HttpResponse(t.render(c))


def api_access_token(request):
  """
  checks that the request is well formed
  checks that the request token provided has been authorized
  if it has generate a new access token and return it
  """
  token = oauth_util.handle_fetch_access_token(request)
  return http.HttpResponse(token.to_string())


# Interface
def api_call(request, format="json"):
  """ the public api

  attempts to validate a request as a valid oauth request then
  builds the appropriate api_user object and tries to dispatch
  to the provided method
  """
  servertime = api.utcnow()
  try:
    kwargs = oauth_util.get_method_kwargs(request)
    json_params = kwargs.pop('json_params', None)
    if json_params:
      parsed = simplejson.loads(json_params)
      # Turn the keys from unicode to str so that they can be used as method
      # parameters.
      kwargs.update(
          dict([(str(k), v) for k, v in parsed.iteritems()]))
    method = kwargs.pop('method', '').replace('.', '_')
    if method == 'presence_send':
      method = 'post'

    if not method:
      raise exception.ApiException(exception.NO_METHOD, "No method specified")


    # Allows us to turn off authentication for testing purposes
    if not settings.API_DISABLE_VERIFICATION:
      api_user = request.user
    else:
      api_user = api.ROOT

    method_ref = api.PublicApi.get_method(method, api_user)
    if not method_ref:
      raise exception.ApiException(exception.INVALID_METHOD,
                         'Invalid method: %s' % method)

    if not api_user:
      raise exception.ApiException(0x00, 'Invalid API user')

    if getattr(api_user, 'legacy', None) and method == 'post':
      kwargs['nick'] = api_user.nick

    rv = method_ref(api_user, **kwargs)
    if rv is None:
      raise exception.ApiException(0x00, 'method %s returned None'%(method))
    return render_api_response(rv, format, servertime=servertime)
  except oauth_util.OAuthError, e:
    exc = exception.ApiException(exception.OAUTH_ERROR, e.message)
    return render_api_response(exc, format)
  except exception.ApiException, e:
    return render_api_response(e, format)
  except TypeError, e:
    exc = exception.ApiException(exception.INVALID_ARGUMENTS, str(e))
    return render_api_response(exc, format)
  except:
    exception.handle_exception(request)
    return render_api_response(request.errors[0], format)

  # some error happened
  return render_api_response(request.errors[0], format)

def api_xmlrpc(request):
  return _XML_RPC_DISPATCHER.dispatch(request)


@decorator.debug_only
def api_loaddata(request):
  """ this is a debug and testing api used to fill a test site with
  initial data from fixtures, it should not be accessible on a non-debug
  instance
  """
  format = request.POST.get('format', 'json')
  fixture = request.POST.get('fixture', '[]')
  fixture_ref = StringIO.StringIO(fixture)

  def _loaddata():
    try:
      count = 0
      models = set()
      objects = serializers.deserialize(format, fixture_ref)
      for obj in objects:
        count += 1
        models.add(obj.object.__class__)
        real_obj = obj.object

        real_obj.put()
      return count
    except Exception, e:
     raise

  #count = db.run_in_transaction(_loaddata)
  count = _loaddata()

  return http.HttpResponse("Loaded %s items from fixture" % count)


@decorator.debug_only
def api_cleardata(request):
  """ this is a debug api for testing, specifically it clears data from the
  datastore, it should only be accessible from a debug instance
  """
  kind = request.GET.get('kind', 'InboxEntry')
  c = 0
  from google.appengine.api import datastore
  from google.appengine.runtime.apiproxy_errors import DeadlineExceededError
  try:
    q = datastore.Query(kind)
    for o in q.Run():
      c += 1
      logging.debug(o)
      datastore.Delete(o.key())
  except Exception, e:
    logging.error("Deadline Errorr %s" % e)

  return http.HttpResponse("kind=%s&count=%s" % (kind, c))


def api_vendor_sms_receive(request, vendor_secret=None):
  """ a one off implementation for receiving sms from IPX """
  if vendor_secret != settings.SMS_VENDOR_SECRET:
    raise exception.ApiException(0x00, "Invalid secret")

  sms_message = sms_protocol.SmsMessage.from_request(request)
  sms_service = sms.SmsService(sms_protocol.SmsConnection())
  sms_service.init_handlers()
  rv = sms_service.handle_message(sms_message.sender, 
                                  sms_message.target, 
                                  sms_message.message)
  return http.HttpResponse(rv)

def api_vendor_xmpp_receive(request):
  """Receive any XMPP message, at the moment it expects the message to
     already be parsed."""
  if not settings.IM_ENABLED:
    raise http.Http404()
  xmpp_message = xmpp.XmppMessage.from_request(request)
  if (settings.IM_TEST_ONLY and 
      xmpp_message.sender.base() not in settings.IM_TEST_JIDS):

    raise http.Http404()

  im_service = im.ImService(xmpp.XmppConnection())
  im_service.init_handlers()
  rv = im_service.handle_message(xmpp_message.sender,
                                 xmpp_message.target,
                                 xmpp_message.message)
  return http.HttpResponse(rv)

def api_vendor_queue_process(request):
  """ process a queue item, redirect to self if there were more """
  secret = request.REQUEST.get('secret')
  if secret != settings.QUEUE_VENDOR_SECRET:
    raise exception.ApiException(0x00, "Invalid secret")
  
  try:
    rv = api.task_process_any(api.ROOT)
    if rv:
      return http.HttpResponseRedirect(request.get_full_path())
  except exception.ApiNoTasks:
    pass
  return http.HttpResponse('')


def _model_to_dict(rv):
  # TODO(mikie): This must be replaced with a to_dict() on the model object so
  # that we can remove/add fields and change representations if needed.
  o = {}
  if not rv:
    return o
  if isinstance(rv, list):
    o = []
    for item in rv:
      o.append(_model_to_dict(item))
    return o
  for prop in rv.properties().keys():
    value = getattr(rv, prop)
    if (isinstance(value, datetime.datetime)):
      value = str(value)
    o[prop] = value

  return o


def render_api_response(rv, format="json", servertime=None):
  if isinstance(rv, exception.ApiException):
    o = {"status": "error"}
    o.update(rv.to_dict())
  elif isinstance(rv, exception.ValidationError):
    o = {"status": "error", "msg": str(rv)}
  else:
    o = {"status": "ok"}
    # TODO make this into something real
    rv = {"rv": rv.to_api()}
    o.update(rv)
    if servertime:
      o['servertime'] = str(servertime)

  return http.HttpResponse(simplejson.dumps(o))
