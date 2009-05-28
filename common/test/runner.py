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

import unittest


from common import profile
from common.test import coverage

from django.conf import settings
from django.db import models
from django.test import simple
from django.test import utils

def _any_startswith(app, app_names):
  return [a for a in app_names if app.startswith(a)]

def run_tests(test_labels, verbosity=1, interactive=True, extra_tests=[], 
              include_coverage=False, include_profile=False, profile_all=False):
    """
    Copy and munge of django's django.test.simple.run_tests method,
    we're extending it to handle coverage
    
    -- Original Docs --

    Run the unit tests for all the test labels in the provided list.
    Labels must be of the form:
     - app.TestClass.test_method
        Run a single specific test method
     - app.TestClass
        Run all the test methods in a given class
     - app
        Search for doctests and unittests in the named application.

    When looking for tests, the test runner will look in the models and
    tests modules for the application.
    
    A list of 'extra' tests may also be provided; these tests
    will be added to the test suite.
    
    Returns the number of tests that failed.
    """
    utils.setup_test_environment()
    
    settings.DEBUG = False
    profile.PROFILE_ALL_TESTS = False
    suite = unittest.TestSuite()
    
    coverage_modules = []
    if include_coverage:
      coverage.start()
    if profile_all:
      profile.PROFILE_ALL_TESTS = True

    if test_labels:
        for label in test_labels:
            if '.' in label:
                suite.addTest(simple.build_test(label))
            else:
                app = models.get_app(label)
                suite.addTest(simple.build_suite(app))
                coverage_modules.append(app)
    else:
        for app in models.get_apps():
            if app.__name__.startswith('appengine_django'):
              continue
            suite.addTest(simple.build_suite(app))
            coverage_modules.append(app)
    
    for test in extra_tests:
        suite.addTest(test)

    old_name = settings.DATABASE_NAME
    from django.db import connection
    connection.creation.create_test_db(verbosity, autoclobber=not interactive)

    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    if include_coverage:
      coverage.stop()
      app_names = [mod.__name__.split('.')[0] for mod in coverage_modules]

      coverage_paths = ['%s/*.py' % app 
                        for app in settings.INSTALLED_APPS
                        if _any_startswith(app, app_names)]
                            
      coverage.report(coverage_paths, ignore_errors=1)

    if profile_all or include_profile:
      f = open(settings.PROFILING_DATA_PATH, 'w')
      f.write(profile.csv())
      f.close()
      profile.clear()


    connection.creation.destroy_test_db(old_name, verbosity)
    
    utils.teardown_test_environment()
    
    return len(result.failures) + len(result.errors)
