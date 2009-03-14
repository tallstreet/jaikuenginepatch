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

import time
import logging

from django import http
from django.conf import settings
from django.utils.http import http_date

from common.display import prep_stream_dict, prep_entry_list, prep_entry, prep_comment_list
from common import decorator
from common import exception
from common import api


@decorator.cache_forever
def blob_image_jpg(request, nick, path):
  try:
    img = api.image_get(request.user, nick, path, format='jpg')
    if not img:
      return http.HttpResponseNotFound()

    content_type = "image/jpg"
    response = http.HttpResponse(content_type=content_type)
    response.write(img.content)
    return response
  except exception.ApiException, e:
    logging.info("exc %s", e)
    return http.HttpResponseForbidden()
  except Exception:
    return http.HttpResponseNotFound()
