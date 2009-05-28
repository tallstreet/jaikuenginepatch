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

from django import test
from django.conf import settings

from common import clean
from common import exception
from common import util
from common.test import util as test_util


class CleanTest(test.TestCase):
  normalize_data = []
  good_data = []
  bad_data = []

  cleaner = staticmethod(lambda x: x)

  def _test_normalization(self, data):
    for t, example in data:
      try:
        result = self.cleaner(t)
      except exception.ValidationError, e:
        message = ("%s(%s) failed validation [%s]" %
            (self.cleaner.__name__, t, e))
        raise AssertionError, message
      self.assertEqual(result, example)

  def test_normalization(self):
    self._test_normalization(self.normalize_data)

  def test_good_data(self):
    self._test_normalization([(x, x) for x in self.good_data])

  def test_bad_data(self):
    for t in self.bad_data:
      self.assertRaises(exception.ValidationError, self.cleaner, t)


class CleanBgRepeatTest(CleanTest):
  normalize_data = [
    ('no-repeat', 'no-repeat'),
    ('', ''),
    ('repeat', ''),
    ('FooBar', ''),
  ]

  cleaner = staticmethod(clean.bg_repeat)


class CleanBgColorTest(CleanTest):
  good_data = [
    '#000000', '#123456', '#ffffff', '#EFEF00', 'red'
  ]

  bad_data = [
    '123;',
    '#123"asd',
  ]

  cleaner = staticmethod(clean.bg_color)


class CleanImageTest(CleanTest):
  good_data = [
    '%s/bg_%s.jpg' % ('popular@example.com', '012340'),
    '%s/bg_%s.jpg' % ('popular@example.com', '0123af'),

    # How about a deterministic test:
    '%s/bg_%s.jpg' % ('popular@example.com', util.generate_uuid()),
    None
  ]

  bad_data = [
    '%s/bg_%s.jpg' % ('popu@lar@example.com', '012340'),
    '%s/bg_%s.jpg' % ('popular@example.com', '0123afx'),
  ]

  normalize_data = [(x, x) for x in good_data]
  cleaner = staticmethod(clean.bg_image)


class CleanChannelTest(CleanTest):
  normalize_data = [('channel', '#channel@example.com'),
                    ('#channel', '#channel@example.com'),
                    ('so', '#so@example.com'),
                    ('#rty', '#rty@example.com'),
                    ]

  good_data = ['#channel@example.com',
               '#so@example.com',
               '#45foo@example.com',
               ]

  bad_data = ['a', 'a' * 45,
              'asd_', 'asd_f', '_asd',
              '123%#', '#!adsf',
              u'\xebasdf', 'ëdward',
              ]

  cleaner = staticmethod(clean.channel)


class CleanUserTest(CleanTest):
  normalize_data = [('popular', 'popular@example.com'),
                    ('so', 'so@example.com'),
                    ]

  good_data = ['popular@example.com',
               'so@example.com',
               '45foo@example.com',
               ]

  bad_data = ['a', 'a' * 45,
              'asd_', 'asd_f', '_asd',
              '123%#', '#212', '!adsf',
              '#asdf', u'\xebasdf',
              '\xc3\xabdward'
              ]

  cleaner = staticmethod(clean.user)


class CleanNickTest(CleanTest):
  normalize_data = (CleanUserTest.normalize_data +
                    [('#channel', '#channel@example.com'),
                     ('#rty', '#rty@example.com')]
                    )

  good_data = (CleanChannelTest.good_data +
                    CleanUserTest.good_data)

  bad_data = (CleanChannelTest.bad_data)

  cleaner = staticmethod(clean.nick)

class CleanRedirectToTest(CleanTest):
  normalize_data = [
      ('http://www.gogle.com', '/'),
      ('https://www.gogle.com', '/'),
      ('foo\nbar', '/'),
      ('foo\rbar', '/'),
      ('ftp://' + settings.HOSTED_DOMAIN, '/'),
      (settings.HOSTED_DOMAIN, 'http://' + settings.HOSTED_DOMAIN),
      ]
  good_data = [
      '/relative_url',
      'http://' + settings.HOSTED_DOMAIN,
      'http://foo.' + settings.HOSTED_DOMAIN,
      'https://' + settings.HOSTED_DOMAIN,
      'https://foo.' + settings.HOSTED_DOMAIN,
      'http://' + settings.GAE_DOMAIN,
      'http://foo.' + settings.GAE_DOMAIN,
      'https://' + settings.GAE_DOMAIN,
      'https://foo.' + settings.GAE_DOMAIN,
      ]

  cleaner = staticmethod(clean.redirect_to)
