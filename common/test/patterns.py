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
from django.core import mail

from common import api
from common import exception
from common import patterns
from common import profile
from common.protocol import base

class MockService(base.Service):
  handlers = [patterns.SignInHandler,
              patterns.SignOutHandler,
              patterns.PromotionHandler,
              patterns.HelpHandler,
              patterns.CommentHandler,
              patterns.OnHandler,
              patterns.OffHandler,
              patterns.ChannelPostHandler,
              patterns.FollowHandler,
              patterns.LeaveHandler,
              patterns.PostHandler,
              ]

  called = None
  outbox = None

  def __init__(self, connection=None):
    super(MockService, self).__init__(connection)
    self.called = {}
    self.outbox = []

  def __getattr__(self, attr):
    def _fake(*args, **kw):
      self.called.setdefault(attr, 0)
      self.called[attr] += 1
    return _fake

  def clear(self):
    self.called = {}

  def send_message(self, to_list, message):
    self.outbox.append([to_list], message)

class PatternsTest(test.TestCase):
  sender = 'i_am_the_gatekeeper'
  target = 'i_am_the_keymaster'

  def setUp(self):
    self.mock = MockService()
    self.mock.init_handlers()
    super(PatternsTest, self).setUp()

  def tearDown(self):
    self.mock.clear()
    super(PatternsTest, self).tearDown()
    
  def assertCalled(self, message, called, sender=None, target=None):
    if sender is None:
      sender = self.sender
    if target is None:
      target = self.target
    self.mock.handle_message(sender, target, message)
    self.assertEqual(self.mock.called, 
                     called, 
                     '%s != %s for %s' % (self.mock.called, called, message)
                     )
    self.mock.clear()


  def test_channel_post_handler(self):
    called = {'channel_post': 1,
              'response_ok': 1
              }

    data = ['#fakechan: bling!',
            '#fakechan heya']
  
    for d in data:
      self.assertCalled(d, called)

  def test_comment_handler(self):
    called = {'add_comment': 1,
              'response_ok': 1
              }

    data = ['@fakenick: heya',
            '@fakenick heya']
  
    for d in data:
      self.assertCalled(d, called)

  def test_follow_handler_actor(self):
    called = {'actor_add_contact': 1,
              'response_ok': 1
              }

    data = ['follow fakenick',
            'add fakenick',
            'f fakenick',
            'F fakenick',
            ]
  
    for d in data:
      self.assertCalled(d, called)

  def test_follow_handler_channel(self):
    called = {'channel_join': 1,
              'response_ok': 1
              }

    data = ['follow #fakechan',
            'add #fakechan',
            'f #fakechan',
            'F #fakechan',
            'join #fakechan',
            ]
  
    for d in data:
      self.assertCalled(d, called)

  def test_help_handler(self):
    called = {'help': 1,
              'response_ok': 1
              }

    data = ['help',
            'HELP']
  
    for d in data:
      self.assertCalled(d, called)

  def test_leave_handler_actor(self):
    called = {'actor_remove_contact': 1,
              'response_ok': 1
              }

    data = ['leave fakenick',
            'remove fakenick',
            'l fakenick',
            'L fakenick',
            ]
  
    for d in data:
      self.assertCalled(d, called)

  def test_leave_handler_channel(self):
    called = {'channel_part': 1,
              'response_ok': 1
              }

    data = ['leave #fakechan',
            'remove #fakechan',
            'l #fakechan',
            'L #fakechan',
            'part #fakechan',
            ]
  
    for d in data:
      self.assertCalled(d, called)

  def test_off_handler(self):
    called = {'stop_notifications': 1,
              'response_ok': 1
              }

    data = ['off',
            'stop',
            'end',
            'quit',
            'cancel',
            'unsubscribe',
            'pause',
            'STOP',
            ]
  
    for d in data:
      self.assertCalled(d, called)

  def test_on_handler(self):
    called = {'start_notifications': 1,
              'response_ok': 1
              }

    data = ['on',
            'start',
            'wake',
            'ON',
            ]

    for d in data:
      self.assertCalled(d, called)

  def test_post_handler(self):
    called = {'post': 1,
              'response_ok': 1
              }

    data = ['BLAH BLAH BLAH',
            'hurrah!',
            '@ asdasd asda s!',
            '# a asddas asdlld',
            '! asdas ldslf',
            ]

    for d in data:
      self.assertCalled(d, called)

  def test_promotion_handler(self):
    called = {'promote_user': 1,
              'response_ok': 1
              }

    data = ['sign up groovy',
            'SIGN UP groovy']
  
    for d in data:
      self.assertCalled(d, called)

  def test_sign_in_handler(self):
    called = {'sign_in': 1,
              'response_ok': 1
              }

    data = ['sign in fakenick fakepassword',
            'claim fakenick fakepassword',
            'SIGN IN fakenick fakepassword',
            ]
  
    for d in data:
      self.assertCalled(d, called)
  
  def test_sign_out_handler(self):
    called = {'sign_out': 1,
              'response_ok': 1
              }

    data = ['sign out',
            'SIGN OUT',
            'sign OUT'
            ]
  
    for d in data:
      self.assertCalled(d, called)
