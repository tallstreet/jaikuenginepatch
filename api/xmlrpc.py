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

import sys
import xmlrpclib

from SimpleXMLRPCServer import SimpleXMLRPCDispatcher

from django.conf import settings
from django import http
from oauth import oauth
from common import api
from common import legacy
from common import exception
from common import oauth_util


def _xmlrpc_url():
  if settings.SUBDOMAINS_ENABLED:
    return "http://api.%s/xmlrpc" % settings.HOSTED_DOMAIN
  else:
    return "http://%s/api/xmlrpc" % settings.DOMAIN

URL = _xmlrpc_url()

class XmlRpcDispatcher(object):

  _PERSONAL_KEY = 'personal_key'
  _API_USER_NICK_KEY = 'user'
  # for when the client makes a non-post xmlrpc request
  _ONLY_POST_ALLOWED = xmlrpclib.dumps(xmlrpclib.Fault(
      exception.INVALID_ARGUMENTS,
      'XML-RPC message must be an HTTP-POST request'))

  @staticmethod
  def _get_api_user(params):
    if (settings.API_ALLOW_LEGACY_AUTH
        and params.has_key(XmlRpcDispatcher._PERSONAL_KEY)
        and params.has_key(XmlRpcDispatcher._API_USER_NICK_KEY)):
      return legacy.authenticate_user_personal_key(
          params[XmlRpcDispatcher._API_USER_NICK_KEY],
          params[XmlRpcDispatcher._PERSONAL_KEY])

    oauth_request = oauth.OAuthRequest(http_method='POST',
                                       http_url=URL,
                                       parameters=params)
    oauth_util.verify_oauth_request(oauth_request)
    return oauth_util.get_api_user_from_oauth_request(oauth_request)

  @staticmethod
  def _wrap_api_call(function):
    def _wrapped(params):
      try:
        api_user = XmlRpcDispatcher._get_api_user(params)
        if not api_user:
          raise xmlrpclib.Fault(0x00, 'Invalid API user')
        method_args = oauth_util.get_non_oauth_params(params)
        if XmlRpcDispatcher._PERSONAL_KEY in method_args:
          del method_args[XmlRpcDispatcher._PERSONAL_KEY]
        if XmlRpcDispatcher._API_USER_NICK_KEY in method_args:
          del method_args[XmlRpcDispatcher._API_USER_NICK_KEY]
        return function(api_user, **method_args).to_api()
      except oauth_util.OAuthError, e:
        raise xmlrpclib.Fault(exception.OAUTH_ERROR, e.message)
      except TypeError, e:
        raise xmlrpclib.Fault(exception.INVALID_ARGUMENTS, str(e))
    return _wrapped

  def __init__(self, public_api_methods):
    if sys.version_info[:3] >= (2,5,):
      self._dispatcher = SimpleXMLRPCDispatcher(allow_none=True,
                                                encoding=None)
    else:
      self._dispatcher = SimpleXMLRPCDispatcher()
    for name, method in public_api_methods.iteritems():
      self._dispatcher.register_function(
          name=name,
          function=XmlRpcDispatcher._wrap_api_call(method))

  def dispatch(self, request):
    return http.HttpResponse(content=self._dispatch(request),
                             mimetype='text/xml')

  def _dispatch(self, request):
    if request.method != 'POST':
      return XmlRpcDispatcher._ONLY_POST_ALLOWED
    # SimpleXMLRPCDispatcher in python 2.4 does not allow None in response.
    # That prevents us from calling _marshall_dispatch directly.
    try:
      params, method = xmlrpclib.loads(request.raw_post_data)
      rv = self._dispatcher._dispatch(method, params)
      return xmlrpclib.dumps((rv,),
                             methodresponse=True,
                             allow_none=True)
    except xmlrpclib.Fault, fault:
      return xmlrpclib.dumps(fault)
    except:
      return xmlrpclib.dumps(xmlrpclib.Fault(
          0x00, '%s:%s' % (sys.exc_type, sys.exc_value)))
