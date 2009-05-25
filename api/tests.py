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
import xmlrpclib
from oauth import oauth

from django.conf import settings

from api import xmlrpc
from common import api
from common import clean
from common import legacy
from common import oauth_util
from common import profile
from common import util
from common.protocol import xmpp
from common.protocol import sms
from common.test import base
from common.test import util as test_util

class ImTestCase(base.ViewTestCase):
  endpoint = '/_ah/xmpp/message'

  def setUp(self):
    super(ImTestCase, self).setUp()
    self.overrides = test_util.override(IM_ENABLED=True)

  def tearDown(self):
    super(ImTestCase, self).tearDown()
    self.overrides.reset()

  def sign_in(self, from_jid, nick, password=None):
    if not password:
      password = self.passwords[clean.nick(nick)]
    message = 'SIGN IN %s %s' % (nick, password)
    return self.send(from_jid, message)

  def send(self, from_jid, message):
    r = self.client.post(
        self.endpoint, 
        {
          'from': from_jid.full(),
          'to': settings.IM_BOT,
          'body': message
        }
    )
    return r

class SignInTest(ImTestCase):
  from_jid = xmpp.JID.from_uri('test@example.com/demo')
  def test_sign_in(self):
    self.assertEqual(len(xmpp.outbox), 0)
    r = self.sign_in(self.from_jid, 'hermit')
    self.assertEqual(len(xmpp.outbox), 1)

class NotificationsTest(ImTestCase):
  from_jid = xmpp.JID.from_uri('test@example.com/demo')
  def test_start_stop(self):
    actor_pre_ref = api.actor_get(api.ROOT, 'hermit')
    self.assertEqual(actor_pre_ref.extra.get('im_notify', False), False)
  
    r = self.sign_in(self.from_jid, 'hermit')

    self.send(self.from_jid, 'start')

    actor_post_ref = api.actor_get(api.ROOT, 'hermit')
    self.assertEqual(actor_post_ref.extra.get('im_notify', False), True)

    self.send(self.from_jid, 'stop')
    
    actor_last_ref = api.actor_get(api.ROOT, 'hermit')
    self.assertEqual(actor_last_ref.extra.get('im_notify', False), False)

  def test_notify_on_post(self):
    api.post(api.ROOT, nick='popular', message='la la la')
    self.exhaust_queue('popular')

    # should notify popular and unpopular
    self.assertEqual(len(xmpp.outbox), 2)

  def test_notify_on_comment(self):
    api.entry_add_comment(api.ROOT, 
                          stream='stream/popular@example.com/presence',
                          entry='stream/popular@example.com/presence/12345',
                          nick='popular', 
                          content='la la la')

    self.exhaust_queue_any()

    # should notify popular and unpopular
    self.assertEqual(len(xmpp.outbox), 2)

  def test_notify_on_restricted_comment(self):
    api.subscription_request(api.ROOT, 
                             'stream/hermit@example.com/comments',
                             'inbox/unpopular@example.com/overview')

    api.entry_add_comment(api.ROOT, 
                          stream='stream/popular@example.com/presence',
                          entry='stream/popular@example.com/presence/12347',
                          nick='hermit', 
                          content='la la la')

    self.exhaust_queue_any()

    # should notify popular and unpopular
    self.assertEqual(len(xmpp.outbox), 1)

  def test_notify_on_channel_post(self):
    api.channel_post(api.ROOT, 
                     nick='popular', 
                     channel="#popular", 
                     message='la la la')
    # should notify popular and unpopular
    self.assertEqual(len(xmpp.outbox), 2)

class PostTest(ImTestCase):
  from_jid = xmpp.JID.from_uri('test@example.com/demo')
  def test_post_signed_in(self):
    message = "test post"
    r = self.sign_in(self.from_jid, 'hermit')
    r = self.send(self.from_jid, message)

class ChannelPostTest(ImTestCase):
  from_jid = xmpp.JID.from_uri('test@example.com/demo')
  message = "test post from jabber"
  channel = "#popular@example.com"

  def verify_post_present(self):
    # Verify that the channel was updated.
    self.login('popular')
    r = self.client.get('/channel/popular')
    self.assertContains(r, self.message)

  def verify_post_not_present(self):
    # Verify that the channel was updated.
    self.login('popular')
    r = self.client.get('/channel/popular')
    self.assertNotContains(r, self.message)

  def test_post_signed_in(self):
    post = "%s %s" % (self.channel, self.message)
    r = self.sign_in(self.from_jid, 'popular')
    r = self.send(self.from_jid, post)
    self.verify_post_present()

  def test_post_not_signed_in(self):
    post = "%s %s" % (self.channel, self.message)
    r = self.send(self.from_jid, post)
    self.verify_post_not_present()

  def test_post_not_member(self):
    # Test posting to a channel, where the user is not a member.
    # (user automatically joined).
    post = "%s %s" % (self.channel, self.message)
    r = self.sign_in(self.from_jid, 'hermit')
    r = self.send(self.from_jid, post)
    self.verify_post_present()

    # TODO(tyler): Add test to verify the user is now a member and following
    # the channel via jabber.

class OAuthTest(base.ViewTestCase):
  def setUp(self):
    super(OAuthTest, self).setUp()
    self.desktop_consumer = oauth.OAuthConsumer("TESTDESKTOPCONSUMER", "secret")
    self.sig_hmac = oauth.OAuthSignatureMethod_HMAC_SHA1()

  def test_tokens(self):
    request_request = oauth.OAuthRequest.from_consumer_and_token(
        self.desktop_consumer,
        http_url="http://%s/api/request_token" % settings.DOMAIN,
        )
    request_request.sign_request(self.sig_hmac, self.desktop_consumer, None)
    response = self.client.get("/api/request_token", request_request.parameters)

    request_token = oauth.OAuthToken.from_string(response.content)

    # cheat and authorize this token using the backend
    api.oauth_authorize_request_token(api.ROOT, 
                                      request_token.key,
                                      actor='popular@example.com', 
                                      perms="read")

    access_request = oauth.OAuthRequest.from_consumer_and_token(
        self.desktop_consumer,
        request_token,
        http_url="http://%s/api/access_token" % (settings.DOMAIN),
        )
    access_request.sign_request(self.sig_hmac, self.desktop_consumer,
                                request_token)

    response = self.client.get("/api/access_token", access_request.parameters)

    access_token = oauth.OAuthToken.from_string(response.content)

  def test_update_bad_type(self):
    """Verify that sending a bad auth mode fails"""
    r = self.login('popular')
    r = self.client.post('/api/keys/TESTDESKTOPCONSUMER', {
      'nick': 'popular@example.com',
      '_nonce': util.create_nonce('popular', 'oauth_consumer_update'),
      'oauth_consumer_update': '',
      'app_name': 'Foo',
      'consumer_type' : 'Bad Consumer Type',
      'consumer_key' : 'TESTDESKTOPCONSUMER',
    })

    # TODO(tyler): I think I'm smoking crack, but there should be a better
    # error, and I don't know why it isn't happening.  The validation
    # is failing (as it should), but there doesn't seem to be any error
    # page or message to the user.
    self.assertWellformed(r)

  def test_update(self):
    """Verify that sending a good auth mode succeeds"""
    r = self.login('popular')
    r = self.client.post('/api/keys/TESTDESKTOPCONSUMER', {
      'nick': 'popular@example.com',
      '_nonce': util.create_nonce('popular', 'oauth_consumer_update'),
      'oauth_consumer_update': '',
      'app_name': 'New App Name',
      'consumer_type' : 'web',
      'consumer_key' : 'TESTDESKTOPCONSUMER',
    })

    r = self.assertRedirectsPrefix(r, '/api/keys/TESTDESKTOPCONSUMER')
    self.assertTemplateUsed(r, 'api/templates/key.html')
    self.assertContains(r, 'API Key information updated')
    self.assertWellformed(r)
    self.assertContains(r, 'New App Name')

  def test_delete(self):
    r = self.login('popular')
    r = self.client.get('/api/keys/TESTDESKTOPCONSUMER', {
      'nick': 'popular@example.com',
      '_nonce': util.create_nonce('popular', 'oauth_consumer_delete'),
      'oauth_consumer_delete': '',
      'consumer_key' : 'TESTDESKTOPCONSUMER',
      'confirm' : '1',
    })

    r = self.assertRedirectsPrefix(r, '/api/keys')
    self.assertTemplateUsed(r, 'api/templates/keys.html')
    self.assertContains(r, 'API Key deleted')
    self.assertNotContains(r, 'TESTDESKTOPCONSUMER')
    self.assertWellformed(r)

  def test_revoke_access_token(self):
    r = self.login('popular')
    r = self.client.get('/api/tokens', {
      '_nonce': util.create_nonce('popular', 'oauth_revoke_access_token'),
      'oauth_revoke_access_token': '',
      'key': 'POPULARDESKTOPACCESSTOKEN',
      'confirm' : 1,
    })

    r = self.assertRedirectsPrefix(r, '/api/tokens')
    self.assertTemplateUsed(r, 'api/templates/tokens.html')
    self.assertContains(r, 'token revoked')
    self.assertNotContains(r, 'POPULARDESKTOPACCESSTOKEN')
    self.assertWellformed(r)


class SmsTestCase(base.ViewTestCase):
  endpoint = '/api/sms_receive/%s' % settings.SMS_VENDOR_SECRET
  popular = '+14084900694'

  def sign_in(self, from_mobile, nick, password=None):
    if not password:
      password = self.passwords[clean.nick(nick)]
    message = 'SIGN IN %s %s' % (nick, password)
    return self.send(from_mobile, message)

  def send(self, from_mobile, message):
    r = self.client.post(
        self.endpoint, 
        {
          'sender': from_mobile,
          'target': settings.SMS_TARGET,
          'message': message
        }
    )
    return r


class SmsPostTest(SmsTestCase):
  def test_post_signed_in(self):
    message = "test post"
    r = self.sign_in(self.popular, 'popular')
    r = self.send(self.popular, message)

    self.exhaust_queue_any()

    inbox = api.inbox_get_actor_overview(api.ROOT, 'popular@example.com')
    entry_ref = api.entry_get(api.ROOT, inbox[0])
    self.assertEqual(entry_ref.title(), message)


class XmlRpcTest(base.FixturesTestCase):
  def setUp(self):
    super(XmlRpcTest, self).setUp()
    self.overrides = None

  def tearDown(self):
    if self.overrides:
      self.overrides.reset()
    super(XmlRpcTest, self).tearDown()

  def assert_valid_actor_get_response(self, params):
    xml = xmlrpclib.dumps((params,), 'actor_get')
    response = self.client.post('/api/xmlrpc', xml, 'text/xml')
    rv = xmlrpclib.loads(response.content)
    expected = {
        'actor': {'avatar_updated_at': '2009-01-01 00:00:00',
                  'extra': {'follower_count': 4,
                            'contact_count': 2,
                            'icon': 'default/animal_3'},
                  'privacy': 3,
                  'nick': 'popular@example.com',
                  'deleted_at': None,
                  'type': 'user' }
        }
    self.assertEquals(expected, rv[0][0])

  def oauth_request(self):
    consumer = oauth.OAuthConsumer('TESTDESKTOPCONSUMER', 'secret')
    access_token = oauth.OAuthToken('POPULARDESKTOPACCESSTOKEN', 'secret')

    request = oauth.OAuthRequest.from_consumer_and_token(
        oauth_consumer=consumer,
        token=access_token,
        http_url=xmlrpc.URL,
        http_method='POST',
        parameters={'nick': 'popular'})
    request.sign_request(oauth_util.HMAC_SHA1, consumer, access_token)
    return request

  def test_xmlrpc_with_legacy_key(self):
    self.overrides = test_util.override(API_ALLOW_LEGACY_AUTH=True)
    popular_ref = api.actor_get(api.ROOT, 'popular')
    personal_key = legacy.generate_personal_key(popular_ref)
    params = {'user': 'popular',
              'personal_key': personal_key,
              'nick': 'popular'}
    self.assert_valid_actor_get_response(params)

  def test_xmlrpc_with_disabled_legacy_key(self):
    self.overrides = test_util.override(API_ALLOW_LEGACY_AUTH=False)
    popular_ref = api.actor_get(api.ROOT, 'popular')
    personal_key = legacy.generate_personal_key(popular_ref)
    params = {'user': 'popular',
              'personal_key': personal_key,
              'nick': 'popular'}
    xml = xmlrpclib.dumps((params,), 'actor_get')
    response = self.client.post('/api/xmlrpc', xml, 'text/xml')
    self.assertContains(response, 'Parameter not found')

  def test_xmlrpc_bad_legacy_key(self):
    self.overrides = test_util.override(API_ALLOW_LEGACY_AUTH=True)
    params = {'nick': 'popular',
              'user': 'popular',
              'personal_key': 'INVALID PERSONAL KEY!'}
    xml = xmlrpclib.dumps((params,), 'actor_get')
    response = self.client.post('/api/xmlrpc', xml, 'text/xml')
    self.assertContains(response, 'Invalid API user')

  def test_xmlrpc_with_oauth(self):
    oauth_request = self.oauth_request()
    self.assert_valid_actor_get_response(oauth_request.parameters)

  def test_xmlrpc_bad_oauth(self):
    oauth_request = self.oauth_request()
    params = dict(oauth_request.parameters)
    params['oauth_key'] = 'INVALID OAUTH KEY!'
    xml = xmlrpclib.dumps((params,), 'actor_get')
    response = self.client.post('/api/xmlrpc', xml, 'text/xml')
    self.assertContains(response, 'Invalid signature')

  def test_xmlrpc_no_auth(self):
    params = {'nick' : 'popular'}
    xml = xmlrpclib.dumps((params,), 'actor_get')
    response = self.client.post('/api/xmlrpc', xml, 'text/xml')
    self.assertContains(response, 'Parameter not found')

  def test_get_request(self):
    response = self.client.get('/api/xmlrpc')
    self.assertContains(response, 'XML-RPC message must be an HTTP-POST request')
