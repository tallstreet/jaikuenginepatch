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

import Cookie
import logging
import os
import urllib

from django.conf import settings
from django.core import mail

from common.tests import ViewTestCase

from common import api
from common import clean
from common import util
from common.test import util as test_util

class HistoryTest(ViewTestCase):
  def test_public_history_when_signed_out(self):
    r = self.login_and_get(None, '/user/popular')
    self.assertContains(r, "Posts from popular")
    self.assertTemplateUsed(r, 'actor/templates/history.html')
    self.assertWellformed(r)

  def test_private_history_when_signed_out(self):
    r = self.login_and_get(None, '/user/girlfriend')
    self.assertContains(r, 'private user')
    # self.assert_error_contains(r, "Posts from girlfriend", 403)

  def test_private_history_when_signed_in_as_contact(self):
    r = self.login_and_get('boyfriend', '/user/girlfriend')
    self.assertContains(r, "Posts from girlfriend")
    self.assertTemplateUsed(r, 'actor/templates/history.html')

  def test_private_history_when_signed_in_as_noncontact(self):
    r = self.login_and_get('annoying', '/user/girlfriend')
    self.assertContains(r, 'private user')

    # self.assert_error_contains(r, "Posts from girlfriend", 403)

  def test_public_history_when_signed_in_as_self(self):
    r = self.login_and_get('popular', '/user/popular')
    self.assertContains(r, "Your Posts")
    self.assertTemplateUsed(r, 'actor/templates/history.html')
    self.assertContains(r, 'entry_remove=', 3)
    r = self.assertGetLink(r, 'confirm-delete', link_no = 0, of_count = 3)
    self.assertEqual(r.status_code, 302, r.content)
    r = self.client.get('/user/popular')
    self.assertContains(r, 'entry_remove=', 2)

  def test_private_history_when_signed_in_as_self(self):
    r = self.login_and_get('celebrity', '/user/celebrity')
    self.assertContains(r, "Your Posts")
    self.assertTemplateUsed(r, 'actor/templates/history.html')

  def test_wrong_case(self):
    r = self.login_and_get(None, '/user/POPular')
    self.assertContains(r, "Posts from popular")
    self.assertTemplateUsed(r, 'actor/templates/history.html')
    self.assertWellformed(r)

  def set_presence(self, user, location):
    params = {
      'nick': '%s@example.com' % user,
      'presence_set': '',
      'location' : location,
      '_nonce': util.create_nonce('%s@example.com' % user, 
                                  'presence_set')
    }
    return self.client.post('/user/popular', params)

  def test_presence_self(self):
    """Tests setting and getting presence on the history page"""
    presence = "This is the presence"
    user = 'popular'
    r = self.login(user)
    r = self.set_presence(user, presence)
    r = self.assertRedirectsPrefix(r, '/user/popular?flash')
    self.assertContains(r, presence)
    self.assertContains(r, 'Location updated')    
    self.assertTemplateUsed(r, 'actor/templates/history.html')

  def test_presence_loggged_out(self):
    # TODO(tyler): currently this doesn't really make you log in, it just
    # doesn't save the update
    presence = "This is the presence"
    user = 'popular'
    r = self.set_presence(user, presence)
    self.assertNotContains(r, presence)
    self.assertNotContains(r, 'Location updated')    
    self.assertTemplateUsed(r, 'actor/templates/history.html')
    
  def test_presence_other(self):
    """Tests setting and getting presence on the history page"""
    presence = "This is the presence"
    user = 'popular'
    r = self.login(user)
    r = self.set_presence(user, presence)
    
    # Retrieve for another user
    r = self.login_and_get('unpopular', '/user/popular')
    self.assertContains(r, presence)
    self.assertTemplateUsed(r, 'actor/templates/history.html')

    # Ensure we cannot save the presence
    new_presence = 'This is the new presence'
    r = self.set_presence(user, new_presence)
    self.assertNotContains(r, new_presence)
    self.assertNotContains(r, 'Location updated')    

  def test_rss_and_atom_feeds(self):
    r = self.client.get('/user/popular')
    self.assertContains(r, 'href="/user/popular/rss"')
    self.assertContains(r, 'href="/user/popular/atom"')


class SubscriptionTest(ViewTestCase):
  def test_subscribe_and_unsubscribe(self):
    r = self.login_and_get('popular', '/user/celebrity')
    self.assertContains(r, 'class="subscribe', 2)
    r = self.assertGetLink(r, 'subscribe', link_no = 0, of_count = 2)
    self.assertEqual(r.status_code, 302, r.content)
    r = self.client.get('/user/celebrity')
    self.assertContains(r, 'class="subscribe', 1)
    self.assertContains(r, 'class="unsubscribe', 1)
    r = self.assertGetLink(r, 'unsubscribe', link_no = 0, of_count = 1)
    self.assertEqual(r.status_code, 302, r.content)
    r = self.client.get('/user/celebrity')
    self.assertContains(r, 'class="subscribe', 2)

class OverviewTest(ViewTestCase):
  def test_public_overview_when_signed_in_as_self(self):
    r = self.login_and_get('popular', '/user/popular/overview')
    self.assertContains(r, "Hi popular! Here's the latest from your contacts")
    self.assertTemplateUsed(r, 'actor/templates/overview.html')

  def test_public_overview_when_signed_out(self):
    r = self.login_and_get(None, '/user/popular/overview')
    # self.assert_error_contains(r, "Not allowed", 403)

  def test_private_overview_when_signed_in_as_self(self):
    r = self.login_and_get('celebrity', '/user/celebrity/overview')
    self.assertContains(r, "Hi celebrity! Here's the latest from your contacts")
    self.assertTemplateUsed(r, 'actor/templates/overview.html')

  def test_private_overview_when_signed_out(self):
    r = self.login_and_get(None, '/user/celebrity/overview')
    # self.assert_error_contains(r, "Not allowed", 403)

  def set_presence(self, user, location):
    params = {
      'nick': '%s@example.com' % user,
      'presence_set': '',
      'location' : location,
      '_nonce': util.create_nonce('%s@example.com' % user, 
                                  'presence_set')
    }
    return self.client.post('/user/popular/overview', params)

  def test_presence_self(self):
    """Tests setting and getting presence on the overview page"""
    presence = "This is the presence"
    user = 'popular'
    r = self.login(user)
    r = self.set_presence(user, presence)
    r = self.assertRedirectsPrefix(r, '/user/popular/overview?flash')
    self.assertContains(r, presence)
    self.assertContains(r, 'Location updated')    
    self.assertTemplateUsed(r, 'actor/templates/overview.html')

  def test_presence_loggged_out(self):
    # TODO(tyler): Logged out or another user sends the user to /user/<user>
    presence = "This is the presence"
    user = 'popular'
    r = self.set_presence(user, presence)
    r = self.assertRedirectsPrefix(r, '/user/popular')
    self.assertNotContains(r, presence)
    self.assertNotContains(r, 'Location updated')    
    self.assertTemplateUsed(r, 'actor/templates/history.html')

  def test_overview_with_unconfirmed_email(self):
    r = self.login_and_get('hermit', '/user/hermit/overview')
    self.assertContains(r, "not yet confirmed")
    self.assertTemplateUsed(r, 'actor/templates/overview.html')

class ItemTest(ViewTestCase):

  def test_public_item_when_signed_out(self):
    r = self.login_and_get(None, '/user/popular/presence/12345')
    self.assertContains(r, 'test entry 1')
    self.assertTemplateUsed(r, 'actor/templates/item.html')
    if settings.MARK_AS_SPAM_ENABLED:
      # test mark as spam links
      self.assertContains(r, 'mark_as_spam', 0)
    # test delete links
    self.assertContains(r, 'entry_remove=', 0)
    self.assertContains(r, 'entry_remove_comment', 0)
    # test that all posts and comments have timestamps
    self.assertContains(r, 'ago', 3)

  def test_public_item_when_signed_in_as_poster(self):
    r = self.login_and_get('popular', '/user/popular/presence/12345')
    self.assertContains(r, 'test entry 1')
    self.assertTemplateUsed(r, 'actor/templates/item.html')
    if settings.MARK_AS_SPAM_ENABLED:
      self.assertContains(r, 'mark_as_spam', 1)
    self.assertContains(r, 'entry_remove=', 1)
    self.assertContains(r, 'entry_remove_comment', 2)

  def test_public_item_when_signed_in_as_commenter(self):
    r = self.login_and_get('unpopular', '/user/popular/presence/12345')
    self.assertContains(r, 'test entry 1')
    self.assertTemplateUsed(r, 'actor/templates/item.html')
    if settings.MARK_AS_SPAM_ENABLED:
      self.assertContains(r, 'mark_as_spam', 2)
    self.assertContains(r, 'entry_remove=', 0)
    self.assertContains(r, 'entry_remove_comment', 1)

  def test_public_item_when_signed_in_as_nonparticipant(self):
    r = self.login_and_get('girlfriend', '/user/popular/presence/12345')
    self.assertContains(r, 'test entry 1')
    self.assertTemplateUsed(r, 'actor/templates/item.html')
    if settings.MARK_AS_SPAM_ENABLED:
      self.assertContains(r, 'mark_as_spam', 3)
    self.assertContains(r, 'entry_remove=', 0)
    self.assertContains(r, 'entry_remove_comment', 0)

  def test_private_item_when_signed_out(self):
    r = self.login_and_get(None, '/user/girlfriend/presence/16961')
    # self.assert_error_contains(r, 'girlfriend', 403)

  def test_private_item_when_signed_in_as_poster(self):
    r = self.login_and_get('girlfriend', '/user/girlfriend/presence/16961')
    self.assertContains(r, 'private test entry 1')
    self.assertTemplateUsed(r, 'actor/templates/item.html')
    if settings.MARK_AS_SPAM_ENABLED:
      self.assertContains(r, 'mark_as_spam', 1)
    self.assertContains(r, 'entry_remove=', 1)
    self.assertContains(r, 'entry_remove_comment', 2)
    # test that all posts and comments have timestamps
    self.assertContains(r, 'ago', 3)

  def test_private_item_when_signed_in_as_commenter(self):
    r = self.login_and_get('boyfriend', '/user/girlfriend/presence/16961')
    self.assertContains(r, 'private test entry 1')
    self.assertTemplateUsed(r, 'actor/templates/item.html')
    if settings.MARK_AS_SPAM_ENABLED:
      self.assertContains(r, 'mark_as_spam', 2)
    self.assertContains(r, 'entry_remove=', 0)
    self.assertContains(r, 'entry_remove_comment', 1) # can only delete own comment
    self.assertWellformed(r)

  def test_entry_remove(self):
    item_url = '/user/girlfriend/presence/16961'
    r = self.login_and_get('girlfriend', item_url)
    r = self.assertGetLink(r, 'confirm-delete', link_no = 0, of_count = 3)
    self.assertEqual(r.status_code, 302, r.content)
    r = self.client.get(item_url)
    self.assertEqual(r.status_code, 404, r.content)

  def test_entry_remove_comment(self):
    item_url = '/user/girlfriend/presence/16961'
    r = self.login_and_get('girlfriend', item_url)
    r = self.assertGetLink(r, 'confirm-delete', link_no = 1, of_count = 3)
    self.assertEqual(r.status_code, 302, r.content)
    r = self.client.get(item_url)
    self.assertContains(r, 'entry_remove_comment', 1)

class CommentTest(ViewTestCase):
  entry = 'stream/popular@example.com/presence/12345'

  def test_email_notification(self):
    r = self.login('hermit')
    content = 'TEST COMMENT'
    params = {'entry_add_comment': '',
              'nick': 'hermit@example.com',
              'stream': 'stream/popular@example.com/presence',
              'entry': self.entry,
              'content': content,
              '_nonce': util.create_nonce('hermit@example.com', 
                                          'entry_add_comment')
              }
    r = self.client.post('/user/popular/presence/12345',
                         params)
    self.exhaust_queue_any()
    
    self.assertEqual(len(mail.outbox), 2)
    for email in mail.outbox:
      # test that the link is valid
      url = test_util.get_relative_url(email.body)
      r = self.client.get(url)
      self.assertContains(r, content)
      self.assertTemplateUsed(r, 'actor/templates/item.html')

  def test_email_notification_entities(self):
    r = self.login('hermit')
    content = 'TEST COMMENT single quote \' ç'
    params = {'entry_add_comment': '',
              'nick': 'hermit@example.com',
              'stream': 'stream/popular@example.com/presence',
              'entry': self.entry,
              'content': content,
              '_nonce': util.create_nonce('hermit@example.com', 
                                          'entry_add_comment')
              }
    r = self.client.post('/user/popular/presence/12345',
                         params)

    self.exhaust_queue_any()
    
    self.assertEqual(len(mail.outbox), 2)
    for email in mail.outbox:
      msg = email.message()
      self.assertEqual(msg.get_charset(), 'utf-8')
      self.assertEqual(-1, email.body.find('&#39;'))

class ContactsTest(ViewTestCase):

  def test_contacts_when_signed_in(self):
    r = self.login_and_get('popular', '/user/popular/contacts')
    self.assertContains(r, 'Your contacts')
    self.assertTemplateUsed(r, 'actor/templates/contacts.html')
    self.assertContains(r, 'class="remove', 2)
    r = self.assertGetLink(r, 'remove', link_no = 0, of_count = 2)
    self.assertEqual(r.status_code, 302, r.content)
    r = self.client.get('/user/popular/contacts')
    self.assertContains(r, 'class="remove', 1)

  def test_followers_when_signed_in(self):
    r = self.login_and_get('popular', '/user/popular/followers')
    self.assertContains(r, 'Your followers')
    self.assertTemplateUsed(r, 'actor/templates/followers.html')
    self.assertContains(r, 'class="add', 3)
    r = self.assertGetLink(r, 'add', link_no = 0, of_count = 3)
    self.assertEqual(r.status_code, 302, r.content)
    r = self.client.get('/user/popular/contacts')
    self.assertContains(r, 'class="remove', 3)

  def test_invite_friends_link_presence(self):
    r = self.client.get('/user/popular/contacts')
    self.assertNotContains(r, 'Invite friends')
    r = self.login_and_get('popular', '/user/popular/contacts')
    self.assertContains(r, 'Invite friends')
    self.logout()
    r = self.client.get('/user/popular/contacts')
    self.assertNotContains(r, 'Invite friends')
    
  def test_invite_link_redirects_to_login_when_logged_out(self):
    r = self.login_and_get(None, '/user/popular/invite')
    r = self.assertRedirectsPrefix(r, '/login?redirect_to=%2Fuser%2Fpopular%2Finvite')
  
  def test_invite_link_redirects_to_correct_page(self):
    r = self.login_and_get('popular', '/user/girlfriend/invite')
    r = self.assertRedirectsPrefix(r, '/user/popular/invite')
    
  def test_email_notification(self):
    # new follower

    r = self.login('hermit')
    params = {'actor_add_contact': '',
              'owner': 'hermit@example.com',
              'target': 'popular@example.com',
              '_nonce': util.create_nonce('hermit@example.com', 
                                          'actor_add_contact')
              }
    r = self.client.post('/user/popular', params)
    
    self.assertEqual(len(mail.outbox), 1, 'new follower')
    
    email = mail.outbox[0]
    # test that the link is valid
    url = test_util.get_relative_url(email.body)

    r = self.client.get(url)
    self.assertTemplateUsed(r, 'actor/templates/history.html')
    
    mail.outbox = []
    
    # new follower mutual
    r = self.login('popular')
    params = {'actor_add_contact': '',
              'owner': 'popular@example.com',
              'target': 'unpopular@example.com',
              '_nonce': util.create_nonce('popular@example.com', 
                                          'actor_add_contact')
              }
    r = self.client.post('/user/unpopular', params)
    
    self.assertEqual(len(mail.outbox), 1, 'new follower mutual')
    
    email = mail.outbox[0]

    # test that the link is valid
    url = test_util.get_relative_url(email.body)
    r = self.client.get(url)
    self.assertTemplateUsed(r, 'actor/templates/history.html')

class SettingsTest(ViewTestCase):
  def test_settings_404(self):
    r = self.login_and_get('popular', '/user/popular/settings/NonExist')
    self.assertContains(r, 'Page not found', status_code=404)

  def test_settings_index(self):
    r = self.login_and_get('popular', '/user/popular/settings')
    self.assertContains(r, 'Settings')
    self.assertTemplateUsed(r, 'actor/templates/settings_index.html')

  def test_settings_profile(self):
    r = self.login_and_get('popular', '/user/popular/settings/profile')
    self.assertContains(r, 'Profile')
    self.assertTemplateUsed(r, 'actor/templates/settings_profile.html')

  def test_settings_mobile(self):
    # add tests for activate/confirm
    r = self.login_and_get('popular', '/user/popular/settings/mobile')
    self.assertContains(r, 'Mobile')
    self.assertTemplateUsed(r, 'actor/templates/settings_mobile.html')

  def test_settings_email(self):
    # add tests for activate/confirm
    r = self.login_and_get('popular', '/user/popular/settings/email')
    self.assertContains(r, 'Email')
    self.assertTemplateUsed(r, 'actor/templates/settings_email.html')

  def test_settings_im(self):
    # add tests for activate/confirm
    r = self.login_and_get('popular', '/user/popular/settings/im')
    self.assertContains(r, 'IM')
    self.assertTemplateUsed(r, 'actor/templates/settings_im.html')

  def test_settings_password(self):
    r = self.login_and_get('popular', '/user/popular/settings/password')
    self.assertContains(r, 'Change Your Password')
    self.assertTemplateUsed(r, 'actor/templates/settings_password.html')

  def test_settings_photo(self):
    r = self.login_and_get('popular', '/user/popular/settings/photo')
    self.assertContains(r, 'Your photo')
    self.assertTemplateUsed(r, 'actor/templates/settings_photo.html')

  def test_settings_delete(self):
    r = self.login_and_get(
        'popular', 
        '/user/popular/settings/delete',
        {
          '_nonce' : util.create_nonce('popular', 'actor_remove'),
          'actor_remove' : '',
          'nick' : 'popular',
        },
    )
    r = self.assertRedirectsPrefix(r, '/logout')
    
    # TODO(tyler): Add a test that the user cannot log back in!
      


  def test_settings_upload_avatar(self):
    nick = 'obligated'
    self.login(nick)

    nick = clean.nick(nick)
    old_contact_avatars = api.actor_get_contacts_avatars_since(api.ROOT, nick)
    contacts = api.actor_get_contacts(api.ROOT, nick)
    self.assertEquals(len(old_contact_avatars), len(contacts) + 1)
    old_avatar = api.actor_get(api.ROOT, nick).extra.get('icon',
                                                         'avatar_default')
    start_time = api.utcnow()
    no_contact_avatars = api.actor_get_contacts_avatars_since(api.ROOT, nick,
                                                              since_time=start_time)
    self.assertEquals(len(no_contact_avatars), 0)

    # TODO(teemu): add more tests for different file types (gif and jpg).
    # Alternatively, test those against api.avatar_upload.
    f = open('testdata/test_avatar.jpg')
    r = self.client.post('/user/obligated/settings/photo',
                         {
                           'imgfile': f,
                           '_nonce' : 
                              util.create_nonce('obligated', 'change_photo'),
                         })
    r = self.assertRedirectsPrefix(r, '/user/obligated/settings/photo')

    actor_ref = api.actor_get(api.ROOT, nick)
    new_avatar = actor_ref.extra.get('icon', 'avatar_default')
    self.assertNotEquals(old_avatar, new_avatar)
    self.assertTrue(actor_ref.avatar_updated_at >= start_time)
    new_contact_avatars = api.actor_get_contacts_avatars_since(api.ROOT, nick,
                                                               since_time=start_time)
    self.assertEquals(len(new_contact_avatars), 1)
    self.assertEquals(new_contact_avatars.pop().nick, nick)

    self.assertContains(r, 'Avatar uploaded')
    self.assertTemplateUsed(r, 'actor/templates/settings_photo.html')
    self.assertTemplateUsed(r, 'common/templates/flash.html')

  def test_settings_change_avatar(self):
    nick = 'obligated'
    self.login(nick)

    nick = clean.nick(nick)
    old_avatar = api.actor_get(api.ROOT, nick).extra.get('icon',
                                                         'avatar_default')

    # TODO(teemu): add more tests for different file types (gif and jpg).
    # Alternatively, test those against api.avatar_upload.
    r = self.client.post('/user/obligated/settings/photo',
                         {
                           'avatar': 'default/animal_9',
                           '_nonce' :
                              util.create_nonce('obligated', 'change_photo'),
                         })
    r = self.assertRedirectsPrefix(r, '/user/obligated/settings/photo')

    new_avatar = api.actor_get(api.ROOT, nick).extra.get('icon',
                                                         'avatar_default')
    self.assertNotEquals(old_avatar, new_avatar)

    self.assertContains(r, 'Avatar changed')
    self.assertTemplateUsed(r, 'actor/templates/settings_photo.html')
    self.assertTemplateUsed(r, 'common/templates/flash.html')

  def test_settings_privacy(self):
    r = self.login_and_get('popular', '/user/popular/settings/privacy')
    self.assertContains(r, 'Privacy')
    self.assertTemplateUsed(r, 'actor/templates/settings_privacy.html')

  def test_settings_design(self):
    r = self.login_and_get('popular', '/user/popular/settings/design')
    self.assertContains(r, 'Change Design')
    self.assertTemplateUsed(r, 'actor/templates/settings_design.html')

  def test_settings_badge(self):
    r = self.login_and_get('popular', '/user/popular/settings/badge')
    self.assertContains(r, 'badge')
    self.assertTemplateUsed(r, 'actor/templates/settings_badge.html')

  def test_settings_notifications(self):
    r = self.login_and_get('popular', '/user/popular/settings/notifications')
    self.assertContains(r, 'notifications')
    self.assertTemplateUsed(r, 'actor/templates/settings_notifications.html')

  def test_settings_webfeeds(self):
    r = self.login_and_get('popular', '/user/popular/settings/feeds')
    self.assertContains(r, 'feeds')
    self.assertTemplateUsed(r, 'actor/templates/settings_feeds.html')

class NewUserTest(ViewTestCase):
  def test_pages_as_newuser(self):
    api.user_create(api.ROOT, nick = 'mmmm', password = 'mmmmmm',
                    first_name = 'm',
                    last_name ='m')
    for page in ('/user/root',
                 '/user/mmmm/overview',
                 '/user/mmmm/contacts',
                 '/user/mmmm/followers',
                 '/user/mmmm',
                 '/channel/popular',
                 '/channel/popular/presence/13345'):
      r = self.login_and_get('mmmm', page, password='mmmmmm')
      self.assertEqual(r.status_code, 200, page + ' failed:' +
                       str(r.status_code))


class PostTest(ViewTestCase):

  def test_post_message_in_overview(self):
    self.login('popular')
    msg = 'a post from unit test'
    r = self.client.post('/user/popular/overview', 
                         {'message': msg,
                          '_nonce': util.create_nonce('popular', 'post'),
                          'nick': 'popular@example.com',
                          'post': '',
                           })
    r = self.assertRedirectsPrefix(r, '/user/popular/overview')
    self.assertContains(r, msg)
    self.assertContains(r, 'a moment ago')
    self.assertTemplateUsed(r, 'actor/templates/overview.html')

  def test_post_message_in_personal_history(self):
    self.login('popular')
    msg = 'a post from unit test'
    r = self.client.post('/user/popular',
                         {'message': msg,
                          '_nonce': util.create_nonce('popular', 'post'),
                          'nick': 'popular@example.com',
                          'post': '',
                           })
    r = self.assertRedirectsPrefix(r, '/user/popular')
    self.assertContains(r, msg)
    self.assertContains(r, 'a moment ago')
    self.assertTemplateUsed(r, 'actor/templates/history.html')
