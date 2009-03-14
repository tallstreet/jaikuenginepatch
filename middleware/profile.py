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

import cStringIO as StringIO
import logging
import pstats
import sys


from django import http
from django.conf import settings

from common import profile as common_profile
from common import exception

try:
  import cProfile as profile
except ImportError:
  import profile

try:
  import cStringIO as StringIO
except ImportError:
  import StringIO

class ProfileMiddleware(object):
  prof_label = None

  def process_request(self, request):
    if not settings.DEBUG:
      return

  def process_view(self, request, callback, callback_args, callback_kwargs):
    if not settings.DEBUG:
      return

    # hotshot data
    if '_prof_heavy' in request.REQUEST:
      self.profiler = profile.Profile()
      args = (request,) + callback_args
      return self.profiler.runcall(callback, *args, **callback_kwargs)

    # output data for use in the profiling code
    if ('_prof_db' in request.REQUEST 
        or request.META.get('HTTP_X_PROFILE', '') == 'db'):
        self.prof_label = common_profile.label(request.path)

    # output data to be included on the page
    if '_prof_quick' in request.REQUEST:
      try:
        common_profile.install_api_profiling()
      except:
        exception.log_exception()
        
      self.prof_label = common_profile.label(request.path)

  def process_response(self, request, response):
    if not settings.DEBUG:
      return response

    if '_prof_heavy' in request.REQUEST:
      self.profiler.create_stats()

      out = StringIO.StringIO()
      old_stdout = sys.stdout 
      sys.stdout = out

      stats = pstats.Stats(self.profiler)
      stats.sort_stats('time', 'calls')

      stats.print_stats()
      sys.stdout = old_stdout
      
      stats_str = out.getvalue()
      
      new_response = http.HttpResponse(stats_str)
      new_response['Content-type'] = 'text/plain'
      return new_response

    # NOTE: this will not work in any environment other than the dev server
    #       as this is not shared-state-safe, only one request is allowed
    #       at a time for this data to be accurate
    if ('_prof_db' in request.REQUEST 
        or request.META.get('HTTP_X_PROFILE', '') == 'db'):
      self.prof_label.stop()
      csv = common_profile.csv()
      common_profile.clear()
      return http.HttpResponse(csv)

    if '_prof_quick' in request.REQUEST:
      self.prof_label.stop()
      html = common_profile.html()
      common_profile.clear()
      response.write(html)
      return response
    
    


    return response
  

