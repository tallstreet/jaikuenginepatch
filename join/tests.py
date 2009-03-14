import Cookie
import os

from django.conf import settings
from common.tests import ViewTestCase

from common import api
from common import clean
from common import util

class JoinTest(ViewTestCase):
  def setUp(self):
    super(JoinTest, self).setUp()

    self.form_data = {'nick': 'johndoe',
                      'first_name': 'John',
                      'last_name': 'Doe',
                      'email': 'johndoe@google.com',
                      'password': 'good*password',
                      'confirm': 'good*password',
                      'hide': '1',
                      #'invite': ''
                      }
  def tearDown(self):
    self.form_data = None

  def assert_join_validation_error(self, response, content):
    self.assertContains(response, content)
    self.assertTemplateUsed(response, 'join/templates/join.html')
    self.assertTemplateUsed(response, 'common/templates/form_error.html')

  def test_join_page(self):
    r = self.client.get('/join')
    self.assertContains(r, 'SIGN UP')
    self.assertTemplateUsed(r, 'join/templates/join.html')

  def test_join_with_valid_data(self):
    r = self.client.post('/join', self.form_data)
    r = self.assertRedirectsPrefix(r, '/welcome')

  def test_join_with_invalid_email(self):
    self.form_data['email'] = 'invalid'
    r = self.client.post('/join', self.form_data)
    self.assert_join_validation_error(r, 'supply a valid email address')

  def test_join_with_used_email(self):
    self.form_data['email'] = 'popular@example.com'
    r = self.client.post('/join', self.form_data)
    self.assert_join_validation_error(r, 'already associated')

  def test_join_with_deleted_email(self):
    self.form_data['email'] = 'popular@example.com'
    r = self.client.post('/join', self.form_data)
    self.assert_join_validation_error(r, 'already associated')

    api.actor_remove(api.ROOT, 'popular@example.com')

    self.form_data['email'] = 'popular@example.com'
    r = self.client.post('/join', self.form_data)
    r = self.assertRedirectsPrefix(r, '/welcome')

  def test_join_with_invalid_nick(self):
    self.form_data['nick'] = 'a'
    r = self.client.post('/join', self.form_data)
    self.assert_join_validation_error(r, 'Invalid nick')

  def test_join_with_reserved_nick(self):
    self.form_data['nick'] = 'popular'
    r = self.client.post('/join', self.form_data)
    self.assert_join_validation_error(r, 'already in use')

  def test_join_with_banned_nick(self):
    self.form_data['nick'] = 'json'
    r = self.client.post('/join', self.form_data)
    self.assert_join_validation_error(r, 'not allowed')

  def test_join_with_used_nick(self):
    self.form_data['nick'] = 'popular'
    r = self.client.post('/join', self.form_data)
    self.assert_join_validation_error(r, 'already in use')

  def test_join_with_used_nick_case_insensitive(self):
    self.form_data['nick'] = 'Popular'
    r = self.client.post('/join', self.form_data)
    self.assert_join_validation_error(r, 'already in use')


class WelcomeTest(ViewTestCase):
  def setUp(self):
    super(WelcomeTest, self).setUp()
    self.login('girlfriend')

  def tearDown(self):
    self.logout()

  def test_photo_view(self):
    r = self.client.get('/welcome/1')
    self.assertContains(r, 'Your photo')
    self.assertTemplateUsed(r, 'join/templates/welcome_photo.html')

  def test_photo_upload(self):
    nick = 'popular'
    nick = clean.nick(nick)
    old_avatar = api.actor_get(api.ROOT, nick).extra.get('icon', 
                                                         'avatar_default')

    self.login(nick)
    f = open('testdata/test_avatar.jpg')
    r = self.client.post('/welcome/1',
                         {
                           'imgfile': f,
                           '_nonce' :
                              util.create_nonce('popular', 'change_photo'),
                         })
    r = self.assertRedirectsPrefix(r, '/welcome/1?')

    new_avatar = api.actor_get(api.ROOT, nick).extra.get('icon', 
                                                         'avatar_default')
    self.assertNotEquals(old_avatar, new_avatar)

    self.assertContains(r, 'Avatar uploaded')
    self.assertTemplateUsed(r, 'join/templates/welcome_photo.html')
    self.assertTemplateUsed(r, 'common/templates/flash.html')

  def test_mobile_activation_view(self):
    r = self.client.get('/welcome/2')
    self.assertContains(r, 'SIGN IN')
    self.assertTemplateUsed(r, 'join/templates/welcome_mobile.html')

  def test_contacts_view(self):
    r = self.client.get('/welcome/3')
    self.assertContains(r, 'Find some friends')
    self.assertTemplateUsed(r, 'join/templates/welcome_contacts.html')

  def test_done_view(self):
    r = self.client.get('/welcome/done')
    self.assertContains(r, 'Congratulations!')
    self.assertTemplateUsed(r, 'join/templates/welcome_done.html')
