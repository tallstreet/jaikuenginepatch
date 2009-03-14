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

import urlparse
import sys

from beautifulsoup import BeautifulSoup

from django import http
from django import test
from django.conf import settings
from django.test import client

from common import clean
from common import memcache
from common import profile
from common import util
from common.protocol import sms
from common.protocol import xmpp
from common.test import util as test_util

try:
  import xml.etree.ElementTree as etree
  import xml.parsers.expat
except ImportError:
  etree = None

class FixturesTestCase(test.TestCase):
  fixtures = ['actors', 'streams', 'contacts', 'streamentries',
              'inboxentries', 'subscriptions', 'oauthconsumers',
              'invites', 'emails', 'ims', 'activations',
              'oauthaccesstokens']

  passwords = {'obligated@example.com':  'bar',
               'popular@example.com':    'baz',
               'celebrity@example.com':  'baz',
               'boyfriend@example.com':  'baz',
               'girlfriend@example.com': 'baz',
               'annoying@example.com':   'foo',
               'unpopular@example.com':  'foo',
               'hermit@example.com':     'baz',
               'broken@example.com':     'baz',
               'root@example.com':      'fakepassword',
               'hotness@example.com':    'fakepassword'};
  
  def setUp(self):
    settings.DEBUG = False

    xmpp.XmppConnection = test_util.TestXmppConnection
    xmpp.outbox = []

    sms.SmsConnection = test_util.TestSmsConnection
    sms.outbox = []

    memcache.client = test_util.FakeMemcache()

    if profile.PROFILE_ALL_TESTS:
      profile.start()

    self.client = client.Client(SERVER_NAME=settings.DOMAIN)

  def tearDown(self):
    if profile.PROFILE_ALL_TESTS:
      profile.stop()

    if hasattr(self, 'override'):
      self.override.reset()
      del self.override

  def exhaust_queue(self, nick):
    test_util.exhaust_queue(nick)

  def exhaust_queue_any(self):
    test_util.exhaust_queue_any()

class ViewTestCase(FixturesTestCase):
  def login(self, nick, password=None):
    if not password:
      password = self.passwords[clean.nick(nick)]
    r = self.client.post('/login', {'log': nick, 'pwd': password})
    return

  def logout(self):
    self.client.cookies.pop(settings.USER_COOKIE)
    self.client.cookies.pop(settings.PASSWORD_COOKIE)

  def login_and_get(self, nick, path, *args, **kw):
    if nick:
      self.login(nick, kw.get('password', None))
    return self.client.get(path, *args, **kw)

  def assert_error_contains(self, response, content, code=200):
    self.assertContains(response, content, 1, code);

  # TODO(teemu): propose this to appengine_django project, when best submit path (Google-internal or
  # public) is decided.
  def assertRedirectsPrefix(self, response, expected_url_prefix, 
                            status_code=302, target_status_code=200, 
                            host=None):
    """Asserts that a response redirected to an URL with specified prefix,
    and that the redirect URL can be loaded. Return redirected response, so
    that further asserts can be performed on it.

    Note that assertRedirects won't work for external links since it uses
    TestClient to do a request.
    """
    self.assertEqual(response.status_code, status_code,
                     ("Response didn't redirect as expected: Response code was"
                      " %d (expected %d) content %s" % (
                          response.status_code, status_code, response.content)))
    url = response['Location']
    scheme, netloc, path, query, fragment = urlparse.urlsplit(url)

    e_scheme, e_netloc, e_path, e_query, e_fragment = (
        urlparse.urlsplit(expected_url_prefix))

    if not (e_scheme or e_netloc):
      expected_url_prefix = urlparse.urlunsplit(
          ('http', host or settings.DOMAIN, e_path, e_query, e_fragment))
    self.assertEqual(url.find(expected_url_prefix), 0,
                     "Response redirected to '%s',"
                     " expected prefix url '%s'" % (url, expected_url_prefix))

    # Get the redirection page, using the same client that was used
    # to obtain the original response.
    params = {'path': path,
              'data': http.QueryDict(query),
              'SERVER_NAME': netloc,
              }

    if scheme == 'https':
      params['wsgi.url_scheme'] = 'https'
      params['SERVER_PORT'] = '443'
      

    redirect_response = response.client.get(**params)
    self.assertEqual(redirect_response.status_code, 
                     target_status_code,
                     "Couldn't retrieve redirection page '%s': response code"
                     " was %d (expected %d)" % (url,
                                                redirect_response.status_code,
                                                target_status_code)
                     )
    return redirect_response

  def assertWellformed(self, r):
    """Tries to parse the xhmtl content in r, fails the test if not wellformed,
    returns the ElementTree object if it is.
    Not run if elementtree is not available (e.g., plain 2.4).
    """
    if not etree:
      return None
    try:
      parsed = etree.fromstring(r.content)
      return parsed
    except xml.parsers.expat.ExpatError, e:
      # TODO(mikie): this should save the output to a file for inspection.
      line = ''
      lineno = -1
      if getattr(e, 'lineno', None):
        lines = r.content.splitlines()
        line = lines[e.lineno - 1]
        line = "'" + line + "'"
        lineno = e.lineno
      codestr = ''
      if getattr(e, 'code', None):
        codestr = xml.parsers.expat.ErrorString(e.code)
      self.assertTrue(False,
                      'failed to parse response, error %s on line %d %s (%s)' %
                          (codestr, lineno, line, str(e)))
    except:
      self.assertTrue(False, 'failed to parse response, error %s' %
                      str(sys.exc_info()[0]))

  def assertGetLink(self, response, link_class, link_no,
                    of_count=-1, msg=''):
    """Tries to find an anchor element with the given class from the response.
    Checks that there are of_count total links of that class
    (unless of_count==-1). Gets the page from that link.
    """
    self.assertWellformed(response)
    parsed = BeautifulSoup.BeautifulSoup(response.content)
    found = parsed.findAll('a', attrs = { 'class': link_class})
    anchors = [a for a in found]
    if of_count > -1:
      self.assertEqual(len(anchors), of_count, msg)
    a = anchors[link_no]
    href = a['href']
    # 2.4 sgmllib/HTMLParser doesn't decode HTML entities, this
    # fixes the query parameter separator.
    # TODO(mikie): how do we properly detect the sgmllib version?
    if int(sys.version.split(' ')[0].split('.')[1]) < 5:
      href = href.replace('&amp;', '&')
    args = util.href_to_queryparam_dict(href)
    args['confirm'] = 1
    url = response.request['PATH_INFO']
    return self.client.get(url, args)
