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
import re

from django.conf import settings
from django.core import mail

from common import api
from common import clean
from common import exception
from common import profile
from common import sms as sms_service
from common.protocol import sms
from common.test import base
from common.test import util as test_util

class SmsTest(base.FixturesTestCase):
  sender = '+14084900694'
  target = settings.SMS_TARGET

  def setUp(self):
    super(SmsTest, self).setUp()

    # this is actually a TestSmsConnection instance, overriden by the base
    # classes
    self.service = sms_service.SmsService(sms.SmsConnection())
    self.service.init_handlers()
    

  def receive(self, message, sender=None, target=None):
    if sender is None:
      sender = self.sender
    if target is None:
      target = self.target

    self.service.handle_message(sender, target, message)
    self.exhaust_queue_any()
    outbox = sms.outbox[:]
    sms.outbox = []
    return outbox

  def assertOutboxContains(self, outbox, pattern, sender=None):
    if sender is None:
      sender = self.sender

    if type(pattern) is type(''):
      pattern = re.compile(pattern)

    
    for mobile, message in outbox:
      if mobile == sender and pattern.search(message):
        return True

    self.fail('Not in outbox: /%s/ \n %s' % (pattern.pattern, outbox))
      

  def sign_in(self, nick, sender=None):
    password = self.passwords[clean.nick(nick)]
    r = self.receive('SIGN IN %s %s' % (nick, password), sender=sender)
    return r

  # Note: all of these tests assume that double opt-in for the user
  #       has already been completed
  def test_sign_in(self):
    nick = 'popular'
    password = self.passwords[clean.nick(nick)]

    r = self.receive('SIGN IN %s %s' % (nick, password))
    self.assertOutboxContains(r, 'Welcome to %s SMS %s' % (settings.SITE_NAME, nick))
  
  def test_sign_on(self):
    self.sign_in('popular')
    
    r = self.receive('SIGN OUT')
    self.assertOutboxContains(r, sms_service.HELP_SIGNED_OUT)

    r = self.receive('SIGN OUT')
    self.assertOutboxContains(r, sms_service.HELP_SIGN_IN)
  
  def test_post_and_reply(self):

    unpop = '+14083839393'
    r = self.sign_in('unpopular', sender=unpop)
    r = self.receive('on', sender=unpop)

    r = self.sign_in('popular')
    r = self.receive('on')
    
    r = self.receive('bling blao')
    self.assertOutboxContains(r, 'popular: bling blao', sender=unpop)

    r = self.receive('@popular: sup dawg', sender=unpop)
    self.assertOutboxContains(r, 'unpopular\^bb: sup dawg')

  def test_whitelist(self):
    o = test_util.override(SMS_MT_WHITELIST=re.compile('\+23'))
    
    def _all_blocked():
      r = self.sign_in('popular')

    self.assertRaises(exception.ServiceError, _all_blocked)

    r = self.sign_in('popular', '+2345678900')
    self.assert_(r)

    o.reset()

  def test_blacklist(self):
    o = test_util.override(SMS_MT_BLACKLIST=re.compile('\+1'))
    
    def _all_blocked():
      r = self.sign_in('popular')

    self.assertRaises(exception.ServiceError, _all_blocked)

    r = self.sign_in('popular', '+2345678900')
    self.assert_(r)

    o.reset()
