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
          '--verbosity', action='store', dest='verbosity', default='1',
          type='choice', choices=['0', '1', '2'],
          help='Verbosity level; 0=minimal output, 1=normal output, 2=all output'
          ),
      )

  help = 'Builds the documentation'
  args = ''

  requires_model_validation = False

  def handle(self, *test_labels, **options):
    build.generate_api_docs()
    build.build_docs()
