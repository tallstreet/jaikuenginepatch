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

from django.core.management.base import BaseCommand
from optparse import make_option
import sys

class Command(BaseCommand):
  """ Copied from the default django test command, 
  extended to include coverage
  """
  option_list = BaseCommand.option_list + (
      make_option(
          '--verbosity', action='store', dest='verbosity', default='1',
          type='choice', choices=['0', '1', '2'],
          help='Verbosity level; 0=minimal output, 1=normal output, 2=all output'
          ),
      make_option(
          '--noinput', action='store_false', dest='interactive', 
          default=True, 
          help='Tells Django to NOT prompt the user for input of any kind.'
          ),
      make_option(
          '--coverage', action='store_true', dest='coverage', 
          default=False, 
          help='Includes coverage reporting for the tests'
          ),
      make_option(
          '--profile_all', action='store_true', dest='profile_all', 
          default=False, 
          help='Includes profile reporting for all tests'
          ),
      make_option(
          '--include_profile', action='store_true', dest='include_profile', 
          default=False, 
          help='Includes profile reporting for profiled tests'
          ),
      )
  help = 'Runs the test suite for the specified applications, or the entire site if no apps are specified.'
  args = '[appname ...]'

  requires_model_validation = False

  def handle(self, *test_labels, **options):
    from django.conf import settings

    verbosity = int(options.get('verbosity', 1))
    interactive = options.get('interactive', True)
    include_coverage = options.get('coverage', False)
    profile_all = options.get('profile_all', False)
    include_profile = options.get('include_profile', False)

    test_path = settings.TEST_RUNNER.split('.')
    # Allow for Python 2.5 relative paths
    if len(test_path) > 1:
      test_module_name = '.'.join(test_path[:-1])
    else:
      test_module_name = '.'
    test_module = __import__(test_module_name, {}, {}, test_path[-1])
    test_runner = getattr(test_module, test_path[-1])

    failures = test_runner(test_labels, 
                           verbosity=verbosity, 
                           interactive=interactive, 
                           include_coverage=include_coverage, 
                           include_profile=include_profile, 
                           profile_all=profile_all)
    if failures:
      sys.exit(failures)
