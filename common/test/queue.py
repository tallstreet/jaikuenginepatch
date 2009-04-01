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
import simplejson
from oauth import oauth

from django.conf import settings
from django.core import mail

from common import api
from common import exception
from common import mail as common_mail
from common import models
from common import oauth_util
from common import profile
from common.test import base
from common.test import util as test_util



class QueueTest(base.FixturesTestCase):
  def setUp(self):
    self.old_utcnow = test_util.utcnow
    self.now = test_util.utcnow()
    self.delta = datetime.timedelta(seconds=api.DEFAULT_TASK_EXPIRE)
    self.old_enabled = settings.QUEUE_ENABLED

    super(QueueTest, self).setUp()

    settings.QUEUE_ENABLED = True

  def tearDown(self):
    test_util.utcnow = self.old_utcnow
    super(QueueTest, self).tearDown()

    settings.QUEUE_ENABLED = self.old_enabled

  def test_task_crud(self):
    # make a fake task for posting a simple message
    nick = 'popular@example.com'
    action = 'post'
    uuid = 'forever'
    message = 'more'
    
    actor_ref = api.actor_get(api.ROOT, nick)

    # STOP TIME! OMG!
    test_util.utcnow = lambda: self.now

    # makin
    l = profile.label('api_task_create')
    task_ref = api.task_create(actor_ref, 
                               nick, 
                               action, 
                               uuid,
                               args=[],
                               kw={'nick': nick,
                                   'message': message,
                                   'uuid': uuid
                                   }
                               )
    l.stop()
    
    # grabbin
    l = profile.label('api_task_get (unlocked)')
    task_ref = api.task_get(actor_ref, nick, action, uuid)
    l.stop()
    
    # grab again, LOCK VILLE
    def _again():
      task_ref = api.task_get(actor_ref, nick, action, uuid)
    
    
    l = profile.label('api_task_get (locked)')
    self.assertRaises(exception.ApiLocked, _again)
    l.stop()

    # increment time
    new_now = self.now + self.delta
    test_util.utcnow = lambda: new_now

    # grab again, EXPIRED
    task_ref = api.task_get(actor_ref, nick, action, uuid)

    # locked if we try again
    self.assertRaises(exception.ApiLocked, _again)

    # updatin
    l = profile.label('api_task_update')
    task_ref = api.task_update(actor_ref, nick, action, uuid, '1')
    l.stop()
    self.assertEqual(task_ref.progress, '1')
    
    # grab again, FRESH AND CLEAN
    task_ref = api.task_get(actor_ref, nick, action, uuid)
    self.assertEqual(task_ref.progress, '1')

    # removin
    l = profile.label('api_task_remove')
    api.task_remove(actor_ref, nick, action, uuid)
    l.stop()

    # grab again, NOT FOUND
    def _not_found():
      task_ref = api.task_get(actor_ref, nick, action, uuid)

    self.assertRaises(exception.ApiNotFound, _not_found)

  def test_task_post(self):
    """ test that api.post creates a task and additional calls resume
    """
    nick = 'popular@example.com'
    uuid = 'HOWNOW'
    message = 'BROWNCOW'

    actor_ref = api.actor_get(api.ROOT, nick)

    # DROP
    old_max = api.MAX_FOLLOWERS_PER_INBOX
    api.MAX_FOLLOWERS_PER_INBOX = 1

    entry_ref = api.post(actor_ref, nick=nick, uuid=uuid, message=message)
    self.assertEqual(entry_ref.extra['title'], message)
    
    # make sure we can repeat
    two_entry_ref = api.post(actor_ref, nick=nick, uuid=uuid, message=message)
    self.assertEqual(entry_ref.uuid, two_entry_ref.uuid)
    
    # and that task_process_actor works
    task_more = api.task_process_actor(api.ROOT, nick)
    self.assert_(task_more)

    # and run out the queue
    task_more = api.task_process_actor(api.ROOT, nick)
    task_more = api.task_process_actor(api.ROOT, nick)
    task_more = api.task_process_actor(api.ROOT, nick)
    task_more = api.task_process_actor(api.ROOT, nick)

    def _nope():
      task_more = api.task_process_actor(api.ROOT, nick)
    
    self.assertRaises(exception.ApiNoTasks, _nope)   

    api.MAX_FOLLOWERS_PER_INBOX = old_max  

    pass

  def test_task_post_process_any(self):
    """ test that api.post creates a task and additional calls resume
    """
    nick = 'popular@example.com'
    uuid = 'HOWNOW'
    message = 'BROWNCOW'

    actor_ref = api.actor_get(api.ROOT, nick)

    # DROP
    old_max = api.MAX_FOLLOWERS_PER_INBOX
    api.MAX_FOLLOWERS_PER_INBOX = 1

    entry_ref = api.post(actor_ref, nick=nick, uuid=uuid, message=message)
    self.assertEqual(entry_ref.extra['title'], message)
    
    # make sure we can repeat
    two_entry_ref = api.post(actor_ref, nick=nick, uuid=uuid, message=message)
    self.assertEqual(entry_ref.uuid, two_entry_ref.uuid)
    
    # and that task_process_actor works
    task_more = api.task_process_any(api.ROOT)
    self.assert_(task_more)

    # and run out the queue
    task_more = api.task_process_any(api.ROOT)
    task_more = api.task_process_any(api.ROOT)
    task_more = api.task_process_any(api.ROOT)
    task_more = api.task_process_any(api.ROOT)

    def _nope():
      task_more = api.task_process_any(api.ROOT)
    
    self.assertRaises(exception.ApiNoTasks, _nope)

    api.MAX_FOLLOWERS_PER_INBOX = old_max  

    pass
