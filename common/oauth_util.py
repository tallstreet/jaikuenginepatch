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
import cgi

from django.conf import settings

from google.appengine.api import urlfetch

from oauth import oauth
from oauth.oauth import OAuthError
from oauth.oauth import OAuthConsumer
from oauth.oauth import OAuthClient
from oauth.oauth import OAuthToken
from oauth.oauth import OAuthRequest

from common import api
from common.private_key import LocalOAuthSignatureMethod_RSA_SHA1
from common import util
from common import exception



ROOT_CONSUMER = oauth.OAuthConsumer(settings.ROOT_CONSUMER_KEY,
                                    settings.ROOT_CONSUMER_SECRET)

ROOT_TOKEN = oauth.OAuthToken(settings.ROOT_TOKEN_KEY,
                              settings.ROOT_TOKEN_SECRET)


def is_root(consumer, token):
  return (consumer.key == ROOT_CONSUMER.key 
          or (token and token.key == ROOT_TOKEN.key))


class JeOAuthSignatureMethod_PLAINTEXT(oauth.OAuthSignatureMethod_PLAINTEXT):
  def check_signature(self, oauth_request, consumer, token, signature):
    if is_root(consumer, token) and not settings.API_ALLOW_ROOT_PLAINTEXT:
      raise oauth.OAuthError("Invalid consumer")
    return super(JeOAuthSignatureMethod_PLAINTEXT, self).check_signature(
        oauth_request, consumer, token, signature
        )

class JeOAuthSignatureMethod_HMAC_SHA1(oauth.OAuthSignatureMethod_HMAC_SHA1):
  def check_signature(self, oauth_request, consumer, token, signature):
    if is_root(consumer, token) and not settings.API_ALLOW_ROOT_HMAC_SHA1:
      raise oauth.OAuthError("Invalid consumer")
    return super(JeOAuthSignatureMethod_HMAC_SHA1, self).check_signature(
        oauth_request, consumer, token, signature
        )


RSA_SHA1 = LocalOAuthSignatureMethod_RSA_SHA1()
PLAINTEXT = JeOAuthSignatureMethod_PLAINTEXT()
HMAC_SHA1 = JeOAuthSignatureMethod_HMAC_SHA1()

def build_oauth_server():
  sig_methods = {}
  if settings.API_ALLOW_RSA_SHA1:
    sig_methods['RSA-SHA1'] = RSA_SHA1
  if settings.API_ALLOW_HMAC_SHA1:
    sig_methods['HMAC-SHA1'] = HMAC_SHA1
  if settings.API_ALLOW_PLAINTEXT:
    sig_methods['PLAINTEXT'] = PLAINTEXT

  return oauth.OAuthServer(JeOAuthDataStore(), sig_methods)
  
def oauth_request_from_django_request(request):
  url = request.build_absolute_uri()
  url = url.split("?")[0]
  params = util.query_dict_to_keywords(request.REQUEST)
  
  post_data = request.method == "post" and request.raw_post_data or ""
  headers = {}
  if 'HTTP_AUTHORIZATION' in request.META:
    headers['Authorization'] = request.META['HTTP_AUTHORIZATION']

  # TODO(termie): fix the oauth library to not use this call sig
  oauth_request = oauth.OAuthRequest.from_request(
      request.method, 
      url,
      headers=headers,
      query_string=post_data, 
      parameters=params)
  
  return oauth_request

def handle_fetch_request_token(request):
  oauth_request = oauth_request_from_django_request(request)
  oauth_server = build_oauth_server()
  token = oauth_server.fetch_request_token(oauth_request)
  return token

def handle_fetch_access_token(request):
  oauth_request = oauth_request_from_django_request(request)
  oauth_server = build_oauth_server()
  token = oauth_server.fetch_access_token(oauth_request)
  return token

def verify_request(request):
  oauth_request = oauth_request_from_django_request(request)
  verify_oauth_request(oauth_request)

def verify_oauth_request(oauth_request):
  oauth_server = build_oauth_server()
  oauth_server.verify_request(oauth_request)

  # TODO mark that verification has occurred
  # request.oauth_verified = True

def get_api_user(request):
  # XXX WARNING: this function expects that the validity of the request
  #              has already been validated and will provide root access
  #              to the api based on a simple match
  
  # TODO ensure verification has occurred
  # assert request.oauth_verified
  oauth_request = oauth_request_from_django_request(request)
  return get_api_user_from_oauth_request(oauth_request)

def get_api_user_from_oauth_request(oauth_request):
  oauth_token = oauth_request.get_parameter('oauth_token')
  oauth_consumer = oauth_request.get_parameter('oauth_consumer_key')
  
  if oauth_token == ROOT_TOKEN.key:
    return api.ROOT
  
  token_ref = api.oauth_get_access_token(api.ROOT, oauth_token)
  if not token_ref:
    return None
  
  actor_ref = api.actor_get(api.ROOT, token_ref.actor)
  actor_ref.access_level = token_ref.perms
  return actor_ref

def get_method_kwargs(request):
  args = util.query_dict_to_keywords(request.REQUEST)
  return get_non_oauth_params(args)

def get_oauth_params(parameters):
  """Returns oauth parameters from a dictionary of (name, value) parameters
  """
  return dict([(k, v)
               for k, v in parameters.iteritems()
               if k.startswith('oauth')])

def get_non_oauth_params(parameters):
  """Returns non-oauth parameters from a dictionary of (name, value) parameters
  """
  return dict([(k, v)
               for k, v in parameters.iteritems()
               if not k.startswith('oauth')])


def fetch_request_token(request, consumer, url, parameters=None, 
                        sig_method=None):
  parameters = parameters and parameters or {}
  sig_method = sig_method and sig_method or LocalOAuthSignatureMethod_RSA_SHA1()
 
  logging.info('* Obtain a request token ...')
  oauth_request = OAuthRequest.from_consumer_and_token(
      consumer, http_url=url, parameters=parameters
      )
  oauth_request.sign_request(sig_method, consumer, None)

  return _fetch_token(oauth_request)

def fetch_access_token(request, consumer, request_token, url, parameters=None, 
                        sig_method=None):
  parameters = parameters and parameters or {}
  sig_method = sig_method and sig_method or LocalOAuthSignatureMethod_RSA_SHA1()
 
  logging.info('* Obtain an access token ...')
  oauth_request = OAuthRequest.from_consumer_and_token(
      consumer, request_token, http_url=url, parameters=parameters
      )
  oauth_request.sign_request(sig_method, consumer, None)
  
  return _fetch_token(oauth_request)

def _fetch_token(oauth_request):
  url = oauth_request.to_url()
  logging.info('REQUEST url=%s' % url)
  response = urlfetch.fetch(url)
  logging.info('RESPONSE => %s' % response.content)
  
  # TODO can't do this one until the oauth library gets patched
  #token = OAuthToken.from_string(response.content)
  params = cgi.parse_qs(response.content.strip(), keep_blank_values=True)
  if 'oauth_token' not in params or 'oauth_token_secret' not in params:
    return None
  key = params['oauth_token'][0]
  secret = params['oauth_token_secret'][0]
  token = OAuthToken(key, secret)

  logging.info('TOKEN: %s' % token)
  return token

def build_auth_url(request, request_token, url, callback=None, parameters=None):
  if not callback:
    callback = util.here(request)
  parameters = parameters and parameters or {}
  parameters.update({'oauth_token': request_token.key,
                     'oauth_callback': callback})
  auth_url = util.qsa(url, parameters)
  return auth_url



class JeOAuthDataStore(object):
  def lookup_consumer(self, key):
    if key == ROOT_CONSUMER.key:
      return ROOT_CONSUMER

    return api.oauth_get_consumer(api.ROOT, key)

  def lookup_token(self, token_type, token):
    # special case for root user
    if token_type == 'access' and token == ROOT_TOKEN.key:
      return ROOT_TOKEN

    f = getattr(api, 'oauth_get_%s_token' % token_type)
    rv = f(api.ROOT, token)
    return rv

  def lookup_nonce(self, oauth_consumer, oauth_token, nonce):
    return None

  def fetch_request_token(self, oauth_consumer):
    return api.oauth_generate_request_token(api.ROOT, oauth_consumer.key_)

  def fetch_access_token(self, oauth_consumer, oauth_token):
    if oauth_token.authorized:
      access_token = api.oauth_generate_access_token(api.ROOT,
                                             oauth_consumer.key_, 
                                             oauth_token.key_)
      request_token = api.oauth_get_request_token(api.ROOT, oauth_token.key_)
      request_token.delete()
      return access_token
    raise Exception("unauthorized request token")

  def authorize_request_token(self, oauth_token, user):
    pass
