# -*- coding: utf-8 -*-
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

from django import test
from django.conf import settings

from common import monitor
from common.test import util as test_util


class MonitorTest(test.TestCase):

  def _test_normalization(self, data):
    for t, example in data:
      try:
        result = self.cleaner(t)
      except exception.ValidationError, e:
        message = ("%s(%s) failed validation [%s]" %
            (self.cleaner.__name__, t, e))
        raise AssertionError, message
      self.assertEqual(result, example)

  def test_export_dict(self):
    data = {'good-name': ('label-time', {'some':0, 
                                         'mapping':1, 
                                         'variables': 5.0}
                          )
            }

    o = monitor.export(data)
    self.assertEquals(
        o, 'good-name map:label-time mapping:1 some:0 variables:5.0')

  def test_export_list(self):
    data = {'good-name': (0, 2, 8, 256)
            }

    o = monitor.export(data)
    self.assertEquals(
        o, 'good-name 0/2/8/256')


  def test_export_multiple(self):
    data = {'good-name': (0, 2, 8, 256),
            'party-time': 2,
            'dicto': ('label-time', {'heya': 0, 'foo': 0})
            }
    
    o = monitor.export(data)
    self.assertEquals(
        o, ('dicto map:label-time foo:0 heya:0\n'
            'good-name 0/2/8/256\n'
            'party-time 2'))

