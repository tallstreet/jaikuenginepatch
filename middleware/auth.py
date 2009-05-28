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

from django.conf import settings
# TODO andy: this is very basic to begin with, it will need to do some
#            fancy bits if we are going to support more kinds of wild
#            authenticatory neatness

# copied largely from django's contrib.auth stuff
class LazyUser(object):
  def __get__(self, request, obj_type=None):
    if not hasattr(request, '_cached_user'):
      from common import user
      request._cached_user = user.get_user_from_request(request)
    return request._cached_user

class AuthenticationMiddleware(object):
  def process_request(self, request):
    request.__class__.user = LazyUser()
