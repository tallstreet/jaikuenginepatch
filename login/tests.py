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

from django.conf import settings
from common.tests import ViewTestCase
from common import api
from common import clean
from common import exception
from common import util

class LoginTest(ViewTestCase):

  def test_login_when_signed_out(self):
    r = self.login_and_get(None, '/login')
    self.assertContains(r, "Forgot your password?")
    self.assertContains(r, "Sign Up Now")
    self.assertTemplateUsed(r, 'login/templates/login.html')

  def test_login_when_signed_in(self):
    r = self.login_and_get('popular', '/login')
    r = self.assertRedirectsPrefix(r, '/user/popular/overview')
    self.assertTemplateUsed(r, 'actor/templates/overview.html')
    self.assertTemplateUsed(r, 'common/templates/flash.html')

  def test_login_redirect_to(self):
    r = self.login_and_get('popular', '/login', {'redirect_to': '/channel'})
    r = self.assertRedirectsPrefix(r, '/channel')
    self.assertTemplateUsed(r, 'channel/templates/index.html')
    self.assertTemplateUsed(r, 'common/templates/flash.html')

  def test_login(self):
    log = 'popular'
    pwd = self.passwords[clean.nick(log)]
    r = self.client.post('/login', {'log': log, 'pwd': pwd})
    r = self.assertRedirectsPrefix(r, '/user/popular/overview')
    self.assertTemplateUsed(r, 'actor/templates/overview.html')
    self.assertTemplateUsed(r, 'common/templates/flash.html')

  def test_login_with_confirmed_email(self):
    log = 'hotness'
    pwd = self.passwords[clean.nick(log)]
    confirmed_email = 'hotness@foobar.com'
    r = self.client.post('/login', {'log': confirmed_email, 'pwd': pwd})
    r = self.assertRedirectsPrefix(r, '/user/hotness/overview')
    self.assertTemplateUsed(r, 'actor/templates/overview.html')
    self.assertTemplateUsed(r, 'common/templates/flash.html')

  def test_login_bad_password(self):
    log = 'popular'
    pwd = 'BAD PASSWORD'
    r = self.client.post('/login', {'log': log, 'pwd': pwd})
    self.assert_error_contains(r, 'Invalid username or password')
    self.assertTemplateUsed(r, 'login/templates/login.html')

  def test_login_bad_user(self):
    log = 'BAD USER'
    pwd = 'BAD PASSWORD'
    r = self.client.post('/login', {'log': log, 'pwd': pwd})
    self.assert_error_contains(r, 'Invalid username or password')
    self.assertTemplateUsed(r, 'login/templates/login.html')

  def test_login_user_cleanup(self):
    log = 'broken'
    pwd = self.passwords[clean.nick(log)]
    
    actor_ref_pre = api.actor_get(api.ROOT, log)
    self.assert_(not actor_ref_pre.normalized_nick)
    self.assertRaises(exception.ApiException, 
                      api.stream_get_presence,
                      api.ROOT, 
                      log)
    self.assertRaises(exception.ApiException, 
                      api.stream_get_comment,
                      api.ROOT, 
                      log)

    r = self.client.post('/login', {'log': log, 'pwd': pwd})
    r = self.assertRedirectsPrefix(r, '/user/broken/overview')
  

  
    actor_ref_post = api.actor_get(api.ROOT, log)
    self.assert_(actor_ref_post.normalized_nick)
    self.assert_(api.stream_get_presence(api.ROOT, log))
    self.assert_(api.stream_get_comment(api.ROOT, log))

  def test_login_deleted(self):
    log = 'popular'
    pwd = self.passwords[clean.nick(log)]
    r = self.client.post('/login', {'log': log, 'pwd': pwd})
    r = self.assertRedirectsPrefix(r, '/user/popular/overview')
    self.assertTemplateUsed(r, 'actor/templates/overview.html')
    self.assertTemplateUsed(r, 'common/templates/flash.html')

    api.actor_remove(api.ROOT, 'popular')
    r = self.client.post('/login', {'log': log, 'pwd': pwd})
    self.assert_error_contains(r, 'Invalid username')
    self.assertTemplateUsed(r, 'login/templates/login.html')
 

# Test cases and expected outcomes:
# 'annoying', 'girlfriend' do not have an emails associated
# 'hermit' has an unconfirmed email


class LoginForgotTest(ViewTestCase):
  ##### Forgot password tests:
  
  def test_login_forgot_already_logged_in(self):
    r = self.login_and_get('popular', '/login/forgot')
    
    # User gets sent back to the home page.  Unfortunately, since this is
    # 'prefix', it will match a redirect anywhere. :(
    r = self.assertRedirectsPrefix(r, '/', target_status_code=302)
    
    # For this reason, test the second redirect:
    r = self.assertRedirectsPrefix(r, '/user/popular/overview')

  def test_login_forgot(self):
    r = self.client.get('/login/forgot')
    self.assertTemplateUsed(r, 'login/templates/forgot.html')

  def test_login_forgot_nick_popular(self):
    r = self.client.post('/login/forgot', 
                         {
                           '_nonce': util.create_nonce(None, 'login_forgot'),
                           'login_forgot' : '',
                           'nick_or_email' : 'popular',
                         })

    r = self.assertRedirectsPrefix(r, '/login/forgot')
    self.assertTemplateUsed(r, 'login/templates/forgot.html')
    self.assertContains(r, 'New Password Emailed')
    self.assertTemplateUsed(r, 'common/templates/flash.html')    

  def test_login_reset(self):
    r = self.client.post('/login/forgot', 
                         {
                           '_nonce': util.create_nonce(None, 'login_forgot'),
                           'login_forgot' : '',
                           'nick_or_email' : 'popular',
                         })
    email = api.email_get_actor(api.ROOT, 'popular')
    activation_ref = api.activation_get(api.ROOT, 
                                        email, 
                                        'password_lost', 
                                        email)
    self.assert_(activation_ref)
    hash = util.hash_generic(activation_ref.code)
    r = self.client.get('/login/reset', {'email' : email, 'hash' : hash})
    self.assertContains(r, 'Your password has been reset')
    # once it's used, the activation link cannot be used again
    r = self.client.get('/login/reset', {'email' : email, 'hash' : hash})
    self.assertRedirectsPrefix(r, '/error', target_status_code=200)

  # User enters 'popular', 'popular' has a confirmed email.
  # - Send notification to that email.
  def test_nick_confirmed(self):
    r = self.client.post('/login/forgot', 
                         {
                           '_nonce': util.create_nonce(None, 'login_forgot'),
                           'login_forgot' : '',
                           'nick_or_email' : 'popular',
                         })
    
    r = self.assertRedirectsPrefix(r, '/login/forgot')
    self.assertTemplateUsed(r, 'login/templates/forgot.html')
    self.assertContains(r, 'New Password Emailed')
    self.assertTemplateUsed(r, 'common/templates/flash.html')

  # User enters 'hermit', 'hermit' has an unconfirmed email
  # - Send notification to that email.
  def test_nick_unconfirmed(self):
    r = self.client.post('/login/forgot', 
                         {
                           '_nonce': util.create_nonce(None, 'login_forgot'),
                           'login_forgot' : '',
                           'nick_or_email' : 'hermit',
                         })

    r = self.assertRedirectsPrefix(r, '/login/forgot')
    self.assertTemplateUsed(r, 'login/templates/forgot.html')
    self.assertContains(r, 'New Password Emailed')
    self.assertTemplateUsed(r, 'common/templates/flash.html')


  # TODO(termie): stub
  # User enters 'popular', 'popular' has an unconfirmed email (shared with other
  #  users)
  # - Send notification to that email.
  def test_nick_multiple_unconfirmed(self):
    pass


  # User enters 'annoying', 'annoying' does not have an email
  # - Tough shit.
  def test_nick_no_email(self):
    r = self.client.post('/login/forgot', 
                         {
                           '_nonce': util.create_nonce(None, 'login_forgot'),
                           'login_forgot' : '',
                           'nick_or_email' : 'annoying',
                         })
      
    self.assertTemplateUsed(r, 'login/templates/forgot.html')
    self.assertContains(r, 'does not have an email')

  
  # User enters a user that doesn't exist
  # - Tough shit.
  def test_unknown_nick(self):
    r = self.client.post('/login/forgot', 
                         {
                           '_nonce': util.create_nonce(None, 'login_forgot'),
                           'login_forgot' : '',
                           'nick_or_email' : 'idontexist',
                         })
      
    self.assertTemplateUsed(r, 'login/templates/forgot.html')
    self.assertContains(r, 'not found')
  
  # User enters 'foo@bar.com', a confirmed email for 'popular'
  # - Send notification to that email.
  def test_email_confirmed(self):
    r = self.client.post('/login/forgot', 
                         {
                           '_nonce': util.create_nonce(None, 'login_forgot'),
                           'login_forgot' : '',
                           'nick_or_email' : 'popular@example.com',
                         })

    r = self.assertRedirectsPrefix(r, '/login/forgot')
    self.assertTemplateUsed(r, 'login/templates/forgot.html')
    self.assertContains(r, 'New Password Emailed')
    self.assertTemplateUsed(r, 'common/templates/flash.html')

  # User enters 'foo@bar.com', an unconfirmed email for 'hermit'
  # - Send notification to that email
  def test_email_unconfirmed(self):
    r = self.client.post('/login/forgot', 
                         {
                           '_nonce': util.create_nonce(None, 'login_forgot'),
                           'login_forgot' : '',
                           'nick_or_email' : 'hermit@example.com',
                         })

    r = self.assertRedirectsPrefix(r, '/login/forgot')
    self.assertTemplateUsed(r, 'login/templates/forgot.html')
    self.assertContains(r, 'New Password Emailed')
    self.assertTemplateUsed(r, 'common/templates/flash.html')
  
  # TODO(termie): stub
  # User enters 'foo@bar.com', an unconfirmed email for 'popular', 'unpopular'
  # - Tough shit.
  def test_email_multiple_unconfirmed(self):
    pass

  # User enters 'foo@bar.com', which doesn't map to anything
  # - Tough shit.  
  def test_email_notfound(self):
    r = self.client.post('/login/forgot', 
                         {
                           '_nonce': util.create_nonce(None, 'login_forgot'),
                           'login_forgot' : '',
                           'nick_or_email' : 'foo@bar.com',
                         })
      
    self.assertTemplateUsed(r, 'login/templates/forgot.html')
    self.assertContains(r, 'does not match any accounts')

class LoginResetTest(ViewTestCase):
  #def test_mixed_case(self):
  #  activation_ref = api.activation_create(api.ROOT, 'CapitalPunishment@jaiku.com', 'password_lost', 'CapitalPunishment@jaiku.com')
  #  code = util.hash_generic(activation_ref)


  def test_login_forgot_nick_mixed_case(self):
    r = self.client.post('/login/forgot', 
                         {
                           '_nonce': util.create_nonce(None, 'login_forgot'),
                           'login_forgot' : '',
                           'nick_or_email' : 'CapitalPunishment',
                         })

    r = self.assertRedirectsPrefix(r, '/login/forgot')
    self.assertTemplateUsed(r, 'login/templates/forgot.html')
    self.assertContains(r, 'New Password Emailed')
    self.assertTemplateUsed(r, 'common/templates/flash.html')

class LogoutTest(ViewTestCase):

  # Once user is logged out, we should not display the "Signed in as XXX" msg.
  # See issue 336 for details
  def test_logout_does_not_remain_signed_in(self):
    r = self.login_and_get('popular', '/login')
    self.assertRedirectsPrefix(r, '/user/popular/overview')
    r = self.client.get('/logout')
    self.assertTemplateUsed(r, 'login/templates/logout.html')
    self.assertNotContains(r, "Signed in as")
