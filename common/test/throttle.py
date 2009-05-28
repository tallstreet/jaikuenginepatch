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

import datetime
import logging

from django.conf import settings

from common import api
from common import clock
from common import exception
from common import throttle
from common.test import base
from common.test import util as test_util

class ThrottleTest(base.FixturesTestCase):
  def setUp(self):
    super(ThrottleTest, self).setUp()
    self.popular = api.actor_get(api.ROOT, 'popular@example.com')

  def test_basic(self):
    
    # lather
    # succeed the first two times, fail the third
    throttle.throttle(self.popular, 'test', minute=2)
    throttle.throttle(self.popular, 'test', minute=2)

    def _failPants():
      throttle.throttle(self.popular, 'test', minute=2)

    self.assertRaises(exception.ApiThrottled, _failPants)

    # rinse
    # magically advance time by a couple minutes
    o = test_util.override_clock(clock, seconds=120)
    
    # repeat
    # succeed the first two times, fail the third
    throttle.throttle(self.popular, 'test', minute=2)
    throttle.throttle(self.popular, 'test', minute=2)

    self.assertRaises(exception.ApiThrottled, _failPants)

    o.reset()
