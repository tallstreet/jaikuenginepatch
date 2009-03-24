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
import os
import sys
from optparse import make_option

from django.core.management.base import BaseCommand

import build

class Command(BaseCommand):
  option_list = BaseCommand.option_list + (
      make_option(
          '--skip-zip', action='store_true', dest='skip_zip', default=False,
          help='Do not clean up zip files'
          ),
      )

  help = 'Cleans up the results of a build'
  args = ''

  requires_model_validation = False

  def handle(self, *test_labels, **options):
    skip_zip = options.get('skip_zip', False)
    build.clean(skip_zip=skip_zip)
