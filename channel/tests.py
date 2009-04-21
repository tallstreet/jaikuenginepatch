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

from common import messages
from common import profile
from common import util
from common.tests import ViewTestCase

class SmokeTest(ViewTestCase):
  def test_popular_channel_public(self):
    l = profile.label('channel_get_public')
    r = self.login_and_get(None, '/channel/popular')
    l.stop()
    self.assertContains(r, "Posts in #popular")
    self.assertWellformed(r)

  def test_wrong_case(self):
    r = self.login_and_get(None, '/channel/POPular')
    self.assertContains(r, "Posts in #popular")
    self.assertWellformed(r)

  def test_popular_channel_logged_in(self):
    l = profile.label('channel_get_logged_in')
    r = self.login_and_get('popular', '/channel/popular')
    l.stop()
    self.assertContains(r, "Posts in #popular")
    self.assertWellformed(r)

  def test_rss_and_atom_feeds(self):
    r = self.client.get('/channel/popular')
    self.assertContains(r, 'href="/channel/popular/rss"')
    self.assertContains(r, 'href="/channel/popular/atom"')


class NonExistentTest(ViewTestCase):
  def test_nonexist_channel_logged_out(self):
    r = self.client.get('/channel/doesntexist')
    r = self.assertRedirectsPrefix(r, '/channel/create', target_status_code=302)
    r = self.assertRedirectsPrefix(r, '/login?')
    self.assertWellformed(r)

  def test_nonexist_channel_logged_in(self):
    r = self.login_and_get('popular', '/channel/doesntexist')
    r = self.assertRedirectsPrefix(r, '/channel/create')
    self.assertTemplateUsed(r, 'channel/templates/create.html')
    self.assertWellformed(r)


class IndexTest(ViewTestCase):
  def test_channel_index(self):
    self.login('unpopular')
    r = self.client.get('/channel')
    self.assertTemplateUsed(r, 'channel/templates/index.html')
    self.assertContains(r, 'Create a New Channel')
    self.assertContains(r, 'No channels')  # nothing administered
    self.assertContains(r, '#popular')     # one followed
    self.assertWellformed(r)

  def test_channel_index_logged_out(self):
    r = self.client.get('/channel')
    self.assertTemplateUsed(r, 'channel/templates/index_signedout.html')

    # Public / recent channels not currently displayed
    self.assertContains(r, 'Want your own')
    self.assertWellformed(r)


class CreationTest(ViewTestCase):
  def test_create_new_channel_logged_out(self):
    r = self.client.post('/channel/create', {'channel_name': 'broken'})
    r = self.assertRedirectsPrefix(r, '/login')
    self.assertWellformed(r)

  def test_create_new_channel(self):
    # 'Create a new channel' post doesn't really create a channel, but
    # shows a page that allows you to create a channel by posting a first message
    # to it.
    self.login('popular')
    r = self.client.post('/channel/create',
                         {'nick': 'popular@example.com',
                          'channel': 'broken',
                          'channel_create': '',
                          '_nonce' : 
                              util.create_nonce('popular', 'channel_create'),
                          }
                         )
    r = self.assertRedirectsPrefix(r, '/channel/broken')
    self.assertTemplateUsed(r, 'channel/templates/history.html')
    self.assertTemplateUsed(r, 'common/templates/message_form.html')
    self.assertWellformed(r)

  def test_create_channel_already_exists(self):
    # 'Create a new channel' post doesn't really create a channel, but
    # shows a page that allows you to create a channel by posting a first message
    # to it.
    self.login('popular')
    r = self.client.post('/channel/create',
                         {'nick': 'popular@example.com',
                          'channel': 'popular',
                          'channel_create': '',
                          '_nonce' : 
                              util.create_nonce('popular', 'channel_create'),
                          }
                         )
    self.assertContains(r, 'Name of the channel is already in use')
    self.assertWellformed(r)

  def test_first_post_to_create_channel_logged_out(self):
    r = self.client.post('/channel/fastfingers', {'message': 'First post!'})
    r = self.assertRedirectsPrefix(r, '/channel/create', target_status_code=302)
    r = self.assertRedirectsPrefix(r, '/login')
    self.assertWellformed(r)

  def test_first_post_to_create_channel(self):
    self.login('popular')
    r = self.client.post('/channel/fastfingers',
                         {'channel': '#fastfingers@example.com',
                          'message': 'First post!',
                          '_nonce': 
                              util.create_nonce('popular', 'set_presence'),
                          }
                         )
    r = self.assertRedirectsPrefix(r, '/channel/create')
    self.assertTemplateUsed(r, 'channel/templates/create.html')
    self.assertWellformed(r)

  def test_recreate_deleted_channel(self):
    self.login('popular')
    
    # First, delete a channel.
    r = self.client.post('/channel/popular/settings/delete',
                         {
                           'actor_remove' : '',
                           'nick' : '#popular@example.com',
                           '_nonce' : 
                              util.create_nonce('popular', 'actor_remove'),
                         })
    r = self.assertRedirectsPrefix(r, '/channel')
    self.assertContains(r, 'Deleted')  # Pre-condition
    
    r = self.client.post('/channel/create',
                         {'nick': 'popular@example.com',
                          'channel': 'popular',
                          'channel_create': '',
                          '_nonce' : 
                              util.create_nonce('popular', 'channel_create'),
                          }
                         )
    self.assertContains(r, 'Name of the channel is already in use')
    self.assertWellformed(r)

  def test_create_new_channel_with_trailing_whitespace(self):
    self.login('popular')
    r = self.client.post('/channel/create',
                         {'nick': 'popular@example.com',
                          'channel': 'whitespace ',
                          'channel_create': '',
                          '_nonce' : 
                              util.create_nonce('popular', 'channel_create'),
                          }
                         )
    r = self.assertRedirectsPrefix(r, '/channel/whitespace')
    self.assertContains(r, 'Channel created')
    self.assertWellformed(r)

  def test_create_new_channel_with_funny_chars(self):
    self.login('popular')
    r = self.client.post('/channel/create',
                         {'nick': 'popular@example.com',
                          'channel': 'weird_',
                          'channel_create': '',
                          '_nonce' : 
                              util.create_nonce('popular', 'channel_create'),
                          }
                         )
    self.assertContains(r, 'Invalid channel')
    self.assertWellformed(r)

  def test_create_new_channel_short(self):
    self.login('popular')
    r = self.client.post('/channel/create',
                         {'nick': 'popular@example.com',
                          'channel': '2',
                          'channel_create': '',
                          '_nonce' : 
                              util.create_nonce('popular', 'channel_create'),
                          }
                         )
    self.assertContains(r, 'Invalid channel')
    self.assertWellformed(r)


class ChannelJoinTest(ViewTestCase):
  def test_join_channel(self):
    self.login('annoying')  # pick a user that is NOT a member
    r = self.client.post('/channel/popular',
                         {'nick': 'annoying@example.com',
                          'channel_join': '',
                          'channel' : '#popular@example.com',
                          '_nonce' : 
                              util.create_nonce('annoying', 'channel_join'),
                          }
                         )
    r = self.assertRedirectsPrefix(r, '/channel/popular')
    self.assertContains(r, 'You have joined')
    self.assertWellformed(r)

  def test_join_channel_already_member(self):
    self.login('popular')  # pick a user that is a member
    r = self.client.post('/channel/popular',
                         {'nick': 'popular@example.com',
                          'channel_join': '',
                          'channel' : '#popular@example.com',
                          '_nonce' : 
                              util.create_nonce('popular', 'channel_join'),
                          }
                         )    
    self.assertContains(r, 'already a member')
    self.assertWellformed(r)


class ChannelDeleteTest(ViewTestCase):
  def test_delete_channel_as_admin(self):
    self.login('popular')
    r = self.client.post('/channel/popular/settings/delete',
                         {'nick': '#popular@example.com',
                          'actor_remove': '',
                          '_nonce' : 
                              util.create_nonce('popular', 'actor_remove'),
                          }
                         )
    r = self.assertRedirectsPrefix(r, '/channel')
    self.assertContains(r, messages.flash('actor_remove'))
    self.assertWellformed(r)

  def test_delete_channel_as_member(self):
    self.login('unpopular')

    r = self.client.post('/channel/popular/settings/delete',
                         {'nick': '#popular@example.com',
                          'actor_remove': '',
                          '_nonce' : 
                              util.create_nonce('unpopular', 'actor_remove'),
                          }
                         )
    self.assertContains(r, 'not allowed')
    self.assertWellformed(r)


class ChannelLeaveTest(ViewTestCase):
  def test_leave_channel(self):
    self.login('unpopular')
    # TODO(tyler): Figure out why get doesn't work (since the request is
    #              generally issued as a get).
#    r = self.client.get('/channel/popular?part=%23popular%40example.com')

    # TODO(tyler): Figure out why escaping the url, while *required* for users
    #              does *not* work here!
    r = self.client.post('/channel/popular',
                         {'nick': 'unpopular@example.com',
                          'channel_part': '',
                          'channel' : '#popular@example.com',
                           '_nonce' : 
                               util.create_nonce('unpopular', 'channel_part'),
                          }
                         )
    r = self.assertRedirectsPrefix(r, '/channel/popular')
    self.assertContains(r, 'left the channel')
    self.assertWellformed(r)

  def test_leave_channel_not_member(self):
    self.login('annoying')
    r = self.client.post('/channel/popular',
                         {'nick': 'annoying@example.com',
                          'channel_part': '',
                          'channel' : '#popular@example.com',
                           '_nonce' : 
                               util.create_nonce('annoying', 'channel_part'),
                          }
                         )
    self.assertContains(r, 'not a member')
    self.assertWellformed(r)

class SettingsTest(ViewTestCase):
  page_to_template_extension = {
    '' : 'index',
    '/details' : 'details',
    '/photo' : 'photo',
    '/design' : 'design',
    '/delete' : 'delete',
  }

  def test_settings_all_pages_logged_out(self):
    for page in self.page_to_template_extension:
      r = self.client.get('/channel/popular/settings' + page)
      r = self.assertRedirectsPrefix(r, '/login')
    
  def test_settings_all_pages_logged_in(self):
    self.login('popular')
    for page, template_extention in self.page_to_template_extension.iteritems():
      r = self.client.get('/channel/popular/settings' + page)
      self.assertTemplateUsed(
          r,
          'channel/templates/settings_%s.html' % template_extention)
      self.assertWellformed(r)

  def test_settings_channel_not_exist(self):
    self.login('popular')
    for page, template_extention in self.page_to_template_extension.iteritems():
      if page == '/delete':
        # See note in views.py for the issue with the delete page.
        continue
      r = self.client.get('/channel/nonexist/settings' + page)
      # TODO(termie): it redirects twice and this function doesn't handle that
      #r = self.assertRedirectsPrefix(r, '/channel/nonexist')
      #self.assertWellformed(r)
      
  def test_settings_delete_channel(self):
    self.login('popular')
    r = self.client.post('/channel/popular/settings/delete',
                         {
                           'actor_remove' : '',
                           'nick' : '#popular@example.com',
                           '_nonce' : 
                              util.create_nonce('popular', 'actor_remove'),
                         })
    r = self.assertRedirectsPrefix(r, '/channel')
    self.assertContains(r, 'Deleted')
    self.assertWellformed(r)

  def test_settings_details(self):
    self.login('popular')
    external_url = 'http://example.com'
    description = 'test desc'
    r = self.client.post('/channel/popular/settings/details',
                         {'channel_update': '',
                          'channel': '#popular@example.com',
                          'description': description,
                          'external_url': external_url,
                          '_nonce': util.create_nonce('popular', 
                                                       'channel_update'),
                          }
                         )
    r = self.assertRedirectsPrefix(r, '/channel/popular/settings/details')
    self.assertContains(r, description)
    self.assertContains(r, external_url)
    self.assertWellformed(r)

  def test_settings_details_bad_url(self):
    self.login('popular')
    external_url = 'javascript:alert(1);'
    description = 'test desc'
    r = self.client.post('/channel/popular/settings/details',
                         {'channel_update': '',
                          'channel': '#popular@example.com',
                          'description': description,
                          'external_url': external_url,
                          '_nonce': util.create_nonce('popular', 
                                                       'channel_update'),
                          }
                         )
    self.assertContains(r, 'Invalid url')
    self.assertWellformed(r)


class CommentTest(ViewTestCase):
  def test_post_and_delete_comment_logged_in(self):
    self.login('popular')

    # Is there a better way to get the correct url?
    comment = 'This is the comment'
    r = self.client.post('/channel/popular/presence/13345',
                         {'stream': 'stream/#popular@example.com/presence',
                          'entry': 'stream/#popular@example.com/presence/13345',
                          'nick': 'popular@example.com',
                          'entry_add_comment' : '',
                          'content' : comment,
                          '_nonce' : 
                              util.create_nonce('popular', 'entry_add_comment'),
                          }
                         )

    self.exhaust_queue_any()
    
    r = self.assertRedirectsPrefix(r, '/channel/popular/presence/13345?flash')
    self.assertContains(r, comment)
    self.assertContains(r, 'Comment added')
    
    # Now delete what we just added
    r = self.assertGetLink(r, 'confirm-delete', link_no=1, of_count=2)
    r = self.assertRedirectsPrefix(r, '/channel/popular/presence/13345?flash')
    self.assertContains(r, 'Comment deleted')
    
