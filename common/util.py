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
import hmac
import logging
import math
import random
import re
import sys
import time
import urllib

from django import http
from django.conf import settings
from django.utils import safestring

from common import clean
from common import exception

try:
  import uuid
  _generate_uuid = lambda: uuid.uuid4().hex
except ImportError:
  logging.info("No uuid module, using fake")
  _generate_uuid = lambda: str(random.randint(10000000, 20000000))

try:
  import hashlib
  _hash = lambda k, m: hmac.new(k, m, hashlib.sha1).hexdigest()
  sha1 = lambda k: hashlib.sha1(k).hexdigest()
except ImportError:
  import sha
  logging.info("No hashlib module, using sha1")
  _hash = lambda k, m: sha.new(k + m).hexdigest()
  sha1 = lambda k: sha.new(k).hexdigest()

VALID_METHODS = ('GET', 'HEAD', 'POST', 'PUT', 'DELETE')
DEFAULT_AVATAR_PATH = 'avatar_default'

def add_caching_headers(response, headers):
  # already has caching headers set
  if response.has_header('Cache-control'):
    return response

  # this is a redirect or an error
  if response.status_code != 200:
    return response

  for k, v in headers.iteritems():
    response[k] = v
  return response

CACHE_NEVER_HEADERS = {'Cache-control': 'no-cache, must-revalidate',
                       'Pragma': 'no-cache',
                       'Expires': 'Fri, 01 Jan 1990 00:00:00 GMT',
                       }

a_bit_less_than_one_year_from_when_this_file_was_loaded = (
  datetime.datetime.now() + datetime.timedelta(days=364)
  ).strftime('%a, %d %b %Y %H:%M:%S GMT')

CACHE_FOREVER_HEADERS = {
    'Expires': a_bit_less_than_one_year_from_when_this_file_was_loaded,
    'Cache-control': 'public, max-age=%d' % (86400*364)
    }

def HttpRssResponse(content, request):
  response = http.HttpResponse(content)
  response['Content-type']  = 'application/rss+xml; charset=utf-8'
  return response

def HttpAtomResponse(content, request):
  response = http.HttpResponse(content)
  response['Content-type']  = 'application/atom+xml; charset=utf-8'
  return response

def HttpJsonResponse(content, request):
  response = http.HttpResponse(content)
  response['Content-type']  = 'text/javascript; charset=utf-8'
  return response


def hash_password(nick, password):
  return sha1(password)

def hash_password_intermediate(nick, password):
  return _hash(hash_salt() + nick, password)

def domain(request):
  domain = request.META['wsgi.url_scheme']+"://"+request.META['SERVER_NAME']
  if request.META['SERVER_PORT'] != '80':
    domain += ":%s" % request.META['SERVER_PORT']
  return domain

def here(request):
  base = domain(request)
  url = base + request.META['PATH_INFO']
  return url

def hash_salt():
  return settings.SECRET_KEY;

def hash_generic(value):
  value = clean.encoding.smart_str(value)
  return _hash(hash_salt(), value)

def generate_uuid():
  return _generate_uuid()

def generate_password():
  """Create a password for the user (to change)."""
  return hash_generic(generate_uuid())[:8]

def create_nonce(user, action, offset=0):
  if not user:
    nick = ""
  else:
    try:
      nick = user.nick
    except AttributeError:
      if settings.MANAGE_PY:
        # extra case to make testing easier
        nick = clean.nick(user)
      else:
        raise
  i = math.ceil(time.time() / 43200)
  i += offset

  nonce = hash_generic(str(i) + action + nick)
  return nonce[-12:-2]

def safe(f):
  def _wrapper(value, arg=None):
    rv = f(value, arg)
    return safestring.mark_safe(rv)
  #_wrapper.func_name = f.func_name
  _wrapper.__name__ = f.__name__
  return _wrapper

def get_redirect_to(request, default=None):
  redirect_to = request.REQUEST.get('redirect_to', default)
  if redirect_to is None:
    # TODO make this domain aware
    redirect_to = request.META.get('PATH_INFO')
  return redirect_to

def RedirectFlash(url, message):
  url = qsa(url,
            params={'flash': message,
                    '_flash': create_nonce(None, message)
                    }
            )
  return http.HttpResponseRedirect(url)

def RedirectError(message):
  url = qsa('http://%s/error' % settings.DOMAIN,
            params={'error': message,
                    '_error': create_nonce(None, message)
                    }
            )
  return http.HttpResponseRedirect(url)

def query_dict_to_keywords(query_dict):
  if settings.DEBUG:
    # support for profiling, pretend profiling stuff doesn't exist
    return dict([(str(k), v) for k, v in query_dict.items() if not k.startswith('_prof')])

  return dict([(str(k), v) for k, v in query_dict.items()])

def href_to_queryparam_dict(href):
  ret = {}

  qparamstr_parts = href.split('?')
  if len(qparamstr_parts) > 1:
    qparamstr = qparamstr_parts[1]
    for qparam in qparamstr.split('&'):
      keyvalue = [urllib.unquote(kv) for kv in qparam.split('=')]
      ret[keyvalue[0]] = keyvalue[1]
  return ret

def email_domain(s):
  """Returns the domain part of an email address."""
  return s.split('@')[-1]

def is_remote(s):
  # XXX termie: this should look up something in a list of local domains
  return s.split('@')[-1] != settings.NS_DOMAIN

def is_channel_nick(nick):
  return nick.startswith("#")

def get_user_from_topic(s):
  """Extracts the username from a topic or Stream object.

  Topics look like: 'stream/bar@example.com/comments'

  Returns:
    A string, the username, or None if the topic name didn't appear to contain a
    valid userid.
  """
  o = None
  # Check whether we got a topic name or a Stream instance
  if not (isinstance(s, str) or isinstance(s, unicode)):
    s = s.key().name()
  list = s.split('/')
  try:
    email = list[1]
    if '@' in email:
      o = email
  except IndexError:   # No '/' in s.
    pass
  return o

def qsa(url, params):
  # TODO termie make better
  sep = "?"
  if sep in url:
    sep = "&"
  url = url + sep + urllib.urlencode(params)
  return url

def datetime_to_timestamp(dt):
  return time.mktime(dt.utctimetuple())

def page_offset(request):
  """attempts to normalize timestamps into datetimes for offsets"""
  offset = request.GET.get('offset', None)
  if offset:
    try:
      offset = datetime.datetime.fromtimestamp(float(offset))
    except (TypeError, ValueError):
      offset = None
  return offset, (offset and True or False)

def page_offset_nick(request):
  offset = request.GET.get('offset', None)
  return offset, (offset and True or False)


def page_entries(request, entries, per_page):
  if len(entries) > per_page > 0:
    more = datetime_to_timestamp(entries[-2].created_at)
    return entries[:-1], more
  return entries, None

def page_actors(request, actors, per_page):
  """ attempts to break a result into pages

  if the number of actors is greater than per_page hand over the nick
  of the second-to-last actor to use as an offset.

  the length of actors should never be more than per_page + 1
  """
  if len(actors) > per_page:
    more = actors[-2].nick
    return actors[:-1], more
  return actors, None


def display_nick(nick):
  # TODO(teemu): combine nick functionality from models.py with this
  return nick.split("@")[0]

def url_nick(nick):
  short = nick.split("@")[0]
  if re.match('^#', short):
    return short[1:]
  return short

def BREAKPOINT():
  import pdb
  p = pdb.Pdb(None, sys.__stdin__, sys.__stdout__)
  p.set_trace()
