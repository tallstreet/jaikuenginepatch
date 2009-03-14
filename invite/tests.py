import logging

from django.conf import settings
from django.core import mail

from common import api
from common import util
from common import tests


class SmokeTest(tests.ViewTestCase):
  def test_invite_email_logged_in(self):
    r = self.login_and_get('hermit', '/invite/email/ACTORINVITE')
    self.assertWellformed(r)
    self.assertTemplateUsed(r, 'invite/templates/email.html')

  def test_invite_email_channel_logged_in(self):
    r = self.login_and_get('hermit', '/invite/email/CHANNELINVITE')
    self.assertWellformed(r)
    self.assertTemplateUsed(r, 'invite/templates/email.html')

  def test_invite_email(self):
    r = self.login_and_get(None, '/invite/email/ACTORINVITE')
    self.assertWellformed(r)
    self.assertTemplateUsed(r, 'invite/templates/email.html')

  def test_invite_email_channel(self):
    r = self.login_and_get(None, '/invite/email/CHANNELINVITE')
    self.assertWellformed(r)
    self.assertTemplateUsed(r, 'invite/templates/email.html')


class AcceptInviteTest(tests.ViewTestCase):
  actor_code = 'ACTORINVITE'
  channel_code = 'CHANNELINVITE'
  def test_invite_email_accept_logged_in(self):
    r = self.login_and_get('hermit', '/invite/email/%s' % self.actor_code)
    r = self.client.post(
        '/invite/email/%s' % self.actor_code, 
        {'invite_accept': '',
         'nick': 'hermit',
         'code': self.actor_code,
         '_nonce': util.create_nonce('hermit', 'invite_accept'),
         }
        )
    r = self.assertRedirectsPrefix(r, '/user/hermit/overview')
    self.assertContains(r, 'accepted')
    self.assertWellformed(r)
    self.assertTemplateUsed(r, 'actor/templates/overview.html')

    # verify that invite code no longer exists
    r = self.client.get('/invite/email/%s' % self.actor_code)
    r = self.assertRedirectsPrefix(r, '/error')

  def test_invite_email_reject_logged_in(self):
    r = self.login_and_get('hermit', '/invite/email/%s' % self.actor_code)
    r = self.client.post(
        '/invite/email/%s' % self.actor_code, 
        {'invite_reject': '',
         'nick': 'hermit',
         'code': self.actor_code,
         '_nonce': util.create_nonce('hermit', 'invite_reject'),
         }
        )
    r = self.assertRedirectsPrefix(r, '/user/hermit/overview')
    self.assertContains(r, 'rejected')
    self.assertWellformed(r)
    self.assertTemplateUsed(r, 'actor/templates/overview.html')

    # verify that invite code no longer exists
    r = self.client.get('/invite/email/%s' % self.actor_code)
    r = self.assertRedirectsPrefix(r, '/error')


class MailTest(tests.ViewTestCase):
  def test_invite_email_link(self):
    self.login('popular')
    popular_ref = api.actor_get(api.ROOT, 'popular@example.com')
    r = self.client.post(
        '/user/popular/invite',
        {'email': 'termie@google.com',
         'nick': 'popular@example.com',
         '_nonce': util.create_nonce(popular_ref, 'invite_request_email'),
         'invite_request_email': ''
         }
        )
    r = self.assertRedirectsPrefix(r, '/user/popular/invite')
    self.assertContains(r, 'Invitation sent')
    self.assertTemplateUsed(r, 'actor/templates/invite.html')
    self.assertEqual(len(mail.outbox), 1)

    sent_mail = mail.outbox[0]
    url = tests.get_relative_url(sent_mail.body)
    
    r = self.login_and_get('hermit', url)
    self.assertTemplateUsed(r, 'invite/templates/email.html')
