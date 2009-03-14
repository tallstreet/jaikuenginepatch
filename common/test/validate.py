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

from common import exception
from common import normalize
from common import util
from common import validate
from common.test import util as test_util

class ValidateNickTest(test.TestCase):
  def test_banned_nicks(self):
    self.assertRaises(exception.ValidationError, lambda : validate.not_banned_name(normalize.nick('json')))
    self.assertRaises(exception.ValidationError, lambda : validate.not_banned_name(normalize.nick('www')))
    self.assertRaises(exception.ValidationError, lambda : validate.not_banned_name(normalize.nick('shop')))

class ValidateMobileNumberTest(test.TestCase):
  def test_valid_numbers(self):
    # Valid cases, just pass
    validate.mobile_number('+447565434588')
    validate.mobile_number('+35850444123')
  
  def test_too_short(self):
    self.assertRaises(exception.ValidationError, validate.mobile_number, '+4412345')

  def test_nonnumeric_format(self):
    self.assertRaises(exception.ValidationError, validate.mobile_number, '+44123456789a')
    self.assertRaises(exception.ValidationError, validate.mobile_number, '+4412345678 9')
    self.assertRaises(exception.ValidationError, validate.mobile_number, ' +44123456789')
    self.assertRaises(exception.ValidationError, validate.mobile_number, '+44123456789 ')
    self.assertRaises(exception.ValidationError, validate.mobile_number, '+4412345678+4')
    self.assertRaises(exception.ValidationError, validate.mobile_number, '+44123456789#0')
    self.assertRaises(exception.ValidationError, validate.mobile_number, '+1615-590-540')

  def test_noninternational_format(self):
    self.assertRaises(exception.ValidationError, validate.mobile_number, '050444123')

  def test_italian_number( self):
    self.assertRaises(exception.ValidationError, validate.mobile_number, '+397565434588')

class ValidateEmailTest(test.TestCase):
  def test_valid_emails(self):
    validate.email('root@example.com')
    validate.email('root@google.com')
    validate.email('foo+bar@zed.com')

  def test_invalid_emails(self):
    self.assertRaises(exception.ValidationError, validate.email, '')
    self.assertRaises(exception.ValidationError, validate.email, ' ')
    self.assertRaises(exception.ValidationError, validate.email, 'root@fi')
    self.assertRaises(exception.ValidationError, validate.email, '@example.com')
    self.assertRaises(exception.ValidationError, validate.email, 'example')
    self.assertRaises(exception.ValidationError, validate.email, 'j@j@example')

class ValidatePasswordTest(test.TestCase):
  def test_valid_passwords(self):
    validate.password('a'*6)
    validate.password('bbb bbb')
    validate.password('c'*16)

  def test_invalid_passwords(self):
    self.assertRaises(exception.ValidationError, validate.password, 'a'*17)
    self.assertRaises(exception.ValidationError, validate.password, 'b'*5)
    self.assertRaises(exception.ValidationError, validate.password, '')

class ValidateNameTest(test.TestCase):
  def test_valid_names(self):
    validate.name('a')
    validate.name('ab ba')
    validate.name('b'*60)
    validate.full_name('a')
    validate.full_name('ab ba')
    validate.full_name('a'*121)
    validate.full_name('b'*60 + ' ' + 'c'*60)

  def test_invalid_names(self):
    self.assertRaises(exception.ValidationError, validate.name, '')
    self.assertRaises(exception.ValidationError, validate.name, 'a'*61)
    self.assertRaises(exception.ValidationError, validate.full_name, '')
    self.assertRaises(exception.ValidationError, validate.full_name, 'a'*122)


class ValidateAvatarPathTest(test.TestCase):
  def test_good_paths(self):
    paths = [
      'popular@example.com/avatar_1345',
    ]
    for p in paths:
      validate.avatar_path(p)

  def test_bad_paths(self):
    paths = [
      'popular/avatar_12341.jpg', # should be a full nick
      'popular@foo@bar.com/avatar_12341.jpg', # bad nick
      '@@/avatar_12341.jpg', # bad nick
    ]
    for p in paths:
      self.assertRaises(exception.ValidationError, validate.avatar_path, p)


class ValidateNonceTest(test.TestCase):
  def test_good_nonces(self):
    fake_user = 'popular@example.com'
    action = 'some_action'

    
    nonce = util.create_nonce(fake_user, action)
    params = {'_nonce': nonce}
  
    validate.nonce(test_util.FakeRequest(
                       user=fake_user,
                       post=params),
                   action)

    validate.nonce(test_util.FakeRequest(
                      user=fake_user,
                      get=params),
                   action)
                    

  def test_bad_nonces(self):
    fake_user = 'popular@example.com'
    action = "some_action"

    future_nonce = util.create_nonce(fake_user, action, offset=10)

    def _future_nonce():
      validate.nonce(test_util.FakeRequest(
                         user=fake_user,
                         post={'_nonce': future_nonce}),
                     action)
    self.assertRaises(exception.ValidationError, _future_nonce)

    def _madeup_nonce():
      validate.nonce(test_util.FakeRequest(
                         user=fake_user,
                         post={'_nonce': 'TEST'}),
                     action)
    self.assertRaises(exception.ValidationError, _madeup_nonce)

    notme_nonce = util.create_nonce(fake_user, action, offset=10)
    def _notme_nonce():
      validate.nonce(test_util.FakeRequest(
                         user='unpopular@example.com',
                         post={'_nonce': notme_nonce}),
                     action)
    self.assertRaises(exception.ValidationError, _notme_nonce)

    notany_nonce = util.create_nonce(fake_user, action, offset=10)
    def _notany_nonce():
      validate.nonce(test_util.FakeRequest(
                         user=None,
                         post={'_nonce': notany_nonce},
                     ),
                     action)
    self.assertRaises(exception.ValidationError, _notany_nonce)


  def test_slightly_old_nonces(self):
    fake_user = 'popular@example.com'
    action = 'some_action'

    nonce = util.create_nonce(fake_user, action, offset=-1)
  
    validate.nonce(test_util.FakeRequest( 
                       user=fake_user,
                       post={'_nonce': nonce}),
                   action)
  
    old_nonce = util.create_nonce(fake_user, action, offset=-2)
    def _old_nonce():
      validate.nonce(test_util.FakeRequest(
                         user=fake_user,
                         post={'_nonce': old_nonce}),
                     action)
    self.assertRaises(exception.ValidationError, _old_nonce)
