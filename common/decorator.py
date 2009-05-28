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

from django import http
from django.conf import settings

from common import exception
from common import util

def debug_only(handler):
  def _wrapper(request, *args, **kw):
    if not settings.DEBUG:
      raise http.Http404()
    return handler(request, *args, **kw)
  _wrapper.__name__ = handler.__name__
  return _wrapper

def login_required(handler):
  def _wrapper(request, *args, **kw):
    if not request.user:
      raise exception.LoginRequiredException()
    return handler(request, *args, **kw)
  _wrapper.__name__ = handler.__name__
  return _wrapper


def add_caching_headers(headers):
  def _cache(handler):
    def _wrap(request, *args, **kw):
      rv = handler(request, *args, **kw)
      return util.add_caching_headers(rv, headers)
    _wrap.func_name == handler.func_name
    return _wrap
  return _cache

# TOOD(termie): add caching headers to cache response forever
cache_forever = add_caching_headers(util.CACHE_FOREVER_HEADERS)

# TOOD(termie): add caching headers to cache response never
cache_never = add_caching_headers(util.CACHE_NEVER_HEADERS)

