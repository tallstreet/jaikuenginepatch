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

"""Bootstrap for running a Django app under Google App Engine.

The site-specific code is all in other files: settings.py, urls.py,
models.py, views.py.  And in fact, only 'settings' is referenced here
directly -- everything else is controlled from there.

"""

# Standard Python imports.
import logging
import os
import sys

logging.debug("Loading %s", __name__)

from appengine_django import InstallAppengineHelperForDjango
from appengine_django import have_django_zip
from appengine_django import django_zip_path
InstallAppengineHelperForDjango()

# Load extra components
from common import component
component.install_components()

# Google App Engine imports.
from google.appengine.ext.webapp import util

# Import the part of Django that we use here.
import django.core.handlers.wsgi

# More logging
def log_exception(*args, **kwds):
  """Django signal handler to log an exception."""
  cls, err = sys.exc_info()[:2]
  logging.exception('Exception in request: %s: %s', cls.__name__, err)
      
import django.core.signals
# Log all exceptions detected by Django.
django.core.signals.got_request_exception.connect(log_exception)

def main():
  for x in os.listdir('.'):
    if x.endswith('.zip'):
      if x in sys.path:
        continue
      logging.debug("adding %s to the sys.path", x)
      sys.path.append(x)

  # we only want to do this once, but due to weird method
  # caching behavior it sometimes gets blown away
  # Create a Django application for WSGI.
  application = django.core.handlers.wsgi.WSGIHandler()

  # Run the WSGI CGI handler with that application.
  util.run_wsgi_app(application)

def profile_main():
 # This is the main function for profiling 
 # We've renamed our original main() above to real_main()
 import cProfile, pstats
 prof = cProfile.Profile()
 prof = prof.runctx("main()", globals(), locals())
 print "<pre>"
 stats = pstats.Stats(prof)
 stats.sort_stats("time")  # Or cumulative
 stats.print_stats(80)  # 80 = how many to print
 # The rest is optional.
 # stats.print_callees()
 # stats.print_callers()
 print "</pre>"


if __name__ == '__main__':
  try:
    main()
    #profile_main()
  except:
    exc_info = sys.exc_info()
    logging.critical("Got to the end!: %s", str(exc_info))
    raise
