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

from django import test

from jaikucommon import api
from jaikucommon import util
from jaikucommon import validate
from jaikucommon.test import base

class CommonViewTest(base.ViewTestCase):
  def test_redirect_slash(self):
    r = self.login_and_get('popular', '/user/popular/overview/')
    redirected = self.assertRedirectsPrefix(r, '/user/popular/overview')
    self.assertTemplateUsed(redirected, 'overview.html')

  def test_confirm(self):
    nonce = util.create_nonce('popular', 'entry_remove')
    entry = 'stream/popular%40example.com/presence/12345'
    path = '/user/popular/overview'
    r = self.login_and_get('popular', path, {'entry_remove': entry,
                                             '_nonce': nonce})
    
    r = self.assertRedirectsPrefix(r, '/confirm')
    self.assertContains(r, nonce)
    self.assertContains(r, entry)
    self.assertContains(r, path)


class UtilTestCase(test.TestCase):
  def test_get_user_from_topic(self):
    topics = [('root@example.com', 'inbox/root@example.com/presence'),
              ('root@example.com', 'inbox/root@example.com/overview'),
              ('root@example.com', 'stream/root@example.com/presence/12345'),
              (None, 'stream//presence'),
              (None, 'stream/something/else'),
              ('duuom+aasdd@gmail.com', 'crazy/duuom+aasdd@gmail.com/dddfff$$%%///'),
              ('asdad@asdasd@asdasd', 'multi/asdad@asdasd@asdasd/cllad/asdff')]
    for t in topics:
      self.assertEqual(util.get_user_from_topic(t[1]), t[0], t[1])


# We're going to import the rest of the test cases into the local
# namespace so that we can run them as 
# python manage.py test jaikucommon.WhateverTest
from jaikucommon.test.api import *
from jaikucommon.test.clean import *
from jaikucommon.test.db import *
from jaikucommon.test.domain import *
from jaikucommon.test.patterns import *
from jaikucommon.test.queue import *
from jaikucommon.test.sms import *
from jaikucommon.test.throttle import *
from jaikucommon.test.validate import *
from jaikucommon.templatetags.test.avatar import *
from jaikucommon.templatetags.test.presence import *

# This is for legacy compat with older tests
# TODO(termie): remove me when no longer needed
from jaikucommon.test.base import *
from jaikucommon.test.util import *
