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
import traceback

from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.conf import settings

from common import exception
from common import util


class ExceptionMiddleware(object):
  def process_exception(self, request, exc):
    if isinstance(exc, exception.RedirectException):
      url = exc.build_url(request)
      return HttpResponseRedirect(url)
    if isinstance(exc, exception.Error):
      logging.warning("RedirectError: %s", traceback.format_exc())
      return util.RedirectError(exc.message)
    if not isinstance(exc, Http404):
      logging.error("5xx: %s", traceback.format_exc())
    if settings.DEBUG and not isinstance(exc, Http404):
      # fake out the technical_500_response because app engine
      # is annoying when it tries to rollback our stuff on 500
      import sys
      from django.views import debug
      exc_info = sys.exc_info()
      reporter = debug.ExceptionReporter(request, *exc_info)
      html = reporter.get_traceback_html()
      return HttpResponse(html, mimetype='text/html')
    return None
