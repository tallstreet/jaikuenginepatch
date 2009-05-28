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

from common import util
from common.models import CachingModel

class CacheMiddleware(object):
  def process_request(self, request):
    CachingModel.enable_cache(True)
    CachingModel.reset_cache()

  def process_response(self, request, response):
    # don't cache anything by default
    # we'll set caching headers manually on appropriate views if they should
    # be cached anyway
    # TODO(termie): add the caching headers
    response = util.add_caching_headers(response, util.CACHE_NEVER_HEADERS)
    return response
