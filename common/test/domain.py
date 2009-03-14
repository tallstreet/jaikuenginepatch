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
import urlparse

from django.conf import settings

from common import clean
from common.test import base
from common.test import util

class DomainTest(base.ViewTestCase):
  domain = 'www.jaikuengine.com'
  gae_domain = 'jaikuengine.appspot.com'
  hosted_domain = 'jaikuengine.com'

  def get_with_host(self, url, host, ssl=False):
    params = {'path': url,
              'SERVER_NAME': host,
              }
    if ssl:
      params['wsgi.url_scheme'] = 'https'
      params['SERVER_PORT'] = '443'

    return self.client.get(**params)

  def post_with_host(self, url, data, host, ssl=False):
    params = {'path': url,
              'SERVER_NAME': host,
              'data': data,
              }
    if ssl:
      params['wsgi.url_scheme'] = 'https'
      params['SERVER_PORT'] = '443'

    return self.client.post(**params)


  # some data driven testing
  def check_domain_redirects(self, requests, **overrides):
    o = util.override(**overrides)
    
    for url, redirect in requests:
      scheme, netloc, path, params, query, fragment = urlparse.urlparse(url)
      
      if redirect:
        e_scheme, e_netloc, e_path, e_params, e_query, e_fragment = \
            urlparse.urlparse(redirect)
      if scheme == 'https':
        ssl = True
      else:
        ssl = False

      r = self.get_with_host(path, host=netloc, ssl=ssl)
      if redirect:
        self.assertRedirectsPrefix(r, redirect, status_code=301)
      else:
        self.assertEqual(r.status_code, 200)

    o.reset()

  def test_hosted_domain_redirect(self):
    bad_hosts = ['www.somewhere.com',
                 'somewhere.com',
                 'jaikuengine.com',
                 self.gae_domain,
                 ]
    good_host = self.domain

    base_url = 'http://%s/tour'
    ssl_url = 'https://%s/tour'
    
    bad_requests = [(base_url % host, base_url % good_host) 
                    for host in bad_hosts]
    ssl_requests = [(ssl_url % host, base_url % good_host) 
                    for host in bad_hosts]
    
    good_requests = [(base_url % good_host, None)]
    requests = bad_requests + ssl_requests + good_requests
    
    # check with SSL_LOGIN_ENABLED
    self.check_domain_redirects(requests,
                                DOMAIN=self.domain,
                                HOSTED_DOMAIN_ENABLED=True,
                                HOSTED_DOMAIN=self.hosted_domain,
                                SUBDOMAINS_ENABLED=False,
                                SSL_LOGIN_ENABLED=True,
                                )

    # check with subdomains enabled
    self.check_domain_redirects(requests,
                                DOMAIN=self.domain,
                                HOSTED_DOMAIN_ENABLED=True,
                                HOSTED_DOMAIN=self.hosted_domain,
                                SUBDOMAINS_ENABLED=True,
                                SSL_LOGIN_ENABLED=True,
                                )
    
    # check without SSL_LOGIN_ENABLED
    self.check_domain_redirects(requests,
                                DOMAIN=self.domain,
                                HOSTED_DOMAIN_ENABLED=True,
                                HOSTED_DOMAIN=self.hosted_domain,
                                SUBDOMAINS_ENABLED=False,
                                SSL_LOGIN_ENABLED=False,
                                )

    # check with subdomains enabled
    self.check_domain_redirects(requests,
                                DOMAIN=self.domain,
                                HOSTED_DOMAIN_ENABLED=True,
                                HOSTED_DOMAIN=self.hosted_domain,
                                SUBDOMAINS_ENABLED=True,
                                SSL_LOGIN_ENABLED=False,
                                )

  def test_hosted_domain_redirect_login_ssl(self):
    bad_hosts = ['www.somewhere.com',
                 'somewhere.com',
                 'jaikuengine.com',
                 ]

    good_host = self.gae_domain

    base_url = 'http://%s/login'
    ssl_url = 'https://%s/login'
    
    bad_domain_and_ssl = [(base_url % host, ssl_url % good_host) 
                          for host in bad_hosts]
    
  
    bad_domain = [(ssl_url % host, ssl_url % good_host) 
                  for host in bad_hosts]
    
    bad_ssl = [(base_url % good_host, ssl_url % good_host)]

    good = [(ssl_url % good_host, None)]

    requests = (bad_domain_and_ssl
                + bad_domain
                + bad_ssl
                + good)

    # check with SSL_LOGIN_ENABLED
    self.check_domain_redirects(requests,
                                DOMAIN=self.domain,
                                GAE_DOMAIN=self.gae_domain,
                                HOSTED_DOMAIN_ENABLED=True,
                                HOSTED_DOMAIN=self.hosted_domain,
                                SUBDOMAINS_ENABLED=False,
                                SSL_LOGIN_ENABLED=True,
                                )

    # check with subdomains enabled
    self.check_domain_redirects(requests,
                                DOMAIN=self.domain,
                                GAE_DOMAIN=self.gae_domain,
                                HOSTED_DOMAIN_ENABLED=True,
                                HOSTED_DOMAIN=self.hosted_domain,
                                SUBDOMAINS_ENABLED=True,
                                SSL_LOGIN_ENABLED=True,
                                )

  def test_hosted_domain_redirect_login(self):
    bad_hosts = ['www.somewhere.com',
                 'somewhere.com',
                 'jaikuengine.com',
                 self.gae_domain
                 ]

    good_host = self.domain

    base_url = 'http://%s/login'
    ssl_url = 'https://%s/login'
    
    bad_domain_and_ssl = [(ssl_url % host, base_url % good_host) 
                          for host in bad_hosts]
    
    bad_domain = [(base_url % host, base_url % good_host) 
                  for host in bad_hosts]
    
    bad_ssl = [(ssl_url % good_host, base_url % good_host)]

    good = [(base_url % good_host, None)]

    requests = (bad_domain_and_ssl
                + bad_domain
                + bad_ssl
                + good)

    # check without SSL_LOGIN_ENABLED
    self.check_domain_redirects(requests,
                                DOMAIN=self.domain,
                                HOSTED_DOMAIN_ENABLED=True,
                                HOSTED_DOMAIN=self.hosted_domain,
                                SUBDOMAINS_ENABLED=False,
                                SSL_LOGIN_ENABLED=False,
                                )

    # check with subdomains enabled
    self.check_domain_redirects(requests,
                                DOMAIN=self.domain,
                                HOSTED_DOMAIN_ENABLED=True,
                                HOSTED_DOMAIN=self.hosted_domain,
                                SUBDOMAINS_ENABLED=True,
                                SSL_LOGIN_ENABLED=False,
                                )

  def test_redirect(self):
    bad_hosts = ['www.somewhere.com',
                 'somewhere.com',
                 'jaikuengine.com',
                 self.domain,
                 ]
    good_host = self.gae_domain

    base_url = 'http://%s/tour'
    ssl_url = 'https://%s/tour'
    
    bad_domain = [(base_url % host, base_url % good_host) 
                  for host in bad_hosts]
    bad_domain_and_ssl = [(ssl_url % host, base_url % good_host) 
                          for host in bad_hosts]
    bad_ssl = [(ssl_url % good_host, base_url % good_host)]

    good = [(base_url % good_host, None)]
    requests = bad_domain + bad_domain_and_ssl + bad_ssl + good
    
    # check with SSL_LOGIN_ENABLED
    self.check_domain_redirects(requests,
                                DOMAIN=self.gae_domain,
                                HOSTED_DOMAIN_ENABLED=False,
                                SUBDOMAINS_ENABLED=False,
                                SSL_LOGIN_ENABLED=True,
                                )
    
    # check with subdomains enabled
    self.check_domain_redirects(requests,
                                DOMAIN=self.gae_domain,
                                HOSTED_DOMAIN_ENABLED=False,
                                HOSTED_DOMAIN=self.hosted_domain,
                                SUBDOMAINS_ENABLED=True,
                                SSL_LOGIN_ENABLED=True,
                                )

    
    # check without SSL_LOGIN_ENABLED
    self.check_domain_redirects(requests,
                                DOMAIN=self.gae_domain,
                                HOSTED_DOMAIN_ENABLED=False,
                                SUBDOMAINS_ENABLED=False,
                                SSL_LOGIN_ENABLED=False,
                                )

    # check with subdomains enabled
    self.check_domain_redirects(requests,
                                DOMAIN=self.gae_domain,
                                HOSTED_DOMAIN_ENABLED=False,
                                HOSTED_DOMAIN=self.hosted_domain,
                                SUBDOMAINS_ENABLED=True,
                                SSL_LOGIN_ENABLED=False,
                                )

  def test_redirect_login(self):
    bad_hosts = ['www.somewhere.com',
                 'somewhere.com',
                 'jaikuengine.com',
                 ]

    good_host = self.gae_domain

    base_url = 'http://%s/login'
    ssl_url = 'https://%s/login'
    
    bad_domain_and_ssl = [(ssl_url % host, base_url % good_host) 
                          for host in bad_hosts]
    
    bad_domain = [(base_url % host, base_url % good_host) 
                  for host in bad_hosts]
    
    bad_ssl = [(ssl_url % good_host, base_url % good_host)]

    good = [(base_url % good_host, None)]

    requests = (bad_domain_and_ssl
                + bad_domain
                + bad_ssl
                + good)

    # check without SSL_LOGIN_ENABLED
    self.check_domain_redirects(requests,
                                DOMAIN=self.gae_domain,
                                HOSTED_DOMAIN_ENABLED=False,
                                SUBDOMAINS_ENABLED=False,
                                SSL_LOGIN_ENABLED=False,
                                )

    # check with subdomains enabled
    self.check_domain_redirects(requests,
                                DOMAIN=self.gae_domain,
                                HOSTED_DOMAIN_ENABLED=False,
                                HOSTED_DOMAIN=self.hosted_domain,
                                SUBDOMAINS_ENABLED=True,
                                SSL_LOGIN_ENABLED=False,
                                )

  def test_redirect_login_ssl(self):
    bad_hosts = ['www.somewhere.com',
                 'somewhere.com',
                 'jaikuengine.com',
                 ]

    good_host = self.gae_domain

    base_url = 'http://%s/login'
    ssl_url = 'https://%s/login'
    
    bad_domain_and_ssl = [(base_url % host, ssl_url % good_host) 
                          for host in bad_hosts]
    
    bad_domain = [(ssl_url % host, ssl_url % good_host) 
                  for host in bad_hosts]
    
    bad_ssl = [(base_url % good_host, ssl_url % good_host)]

    good = [(ssl_url % good_host, None)]

    requests = (bad_domain_and_ssl
                + bad_domain
                + bad_ssl
                + good)

    # check with SSL_LOGIN_ENABLED
    self.check_domain_redirects(requests,
                                DOMAIN=self.gae_domain,
                                GAE_DOMAIN=self.gae_domain,
                                HOSTED_DOMAIN_ENABLED=False,
                                SUBDOMAINS_ENABLED=False,
                                SSL_LOGIN_ENABLED=True,
                                )
    
    # check with subdomains enabled
    self.check_domain_redirects(requests,
                                DOMAIN=self.gae_domain,
                                GAE_DOMAIN=self.gae_domain,
                                HOSTED_DOMAIN_ENABLED=False,
                                HOSTED_DOMAIN=self.hosted_domain,
                                SUBDOMAINS_ENABLED=True,
                                SSL_LOGIN_ENABLED=True,
                                )

  def test_login_sso(self):
    o = util.override(DOMAIN=self.domain,
                      GAE_DOMAIN=self.gae_domain,
                      HOSTED_DOMAIN_ENABLED=True,
                      HOSTED_DOMAIN=self.hosted_domain,
                      SUBDOMAINS_ENABLED=True,
                      SSL_LOGIN_ENABLED=True,
                      )

    r = self.post_with_host('/login',
                            {'log': 'popular',
                             'pwd': self.passwords[clean.nick('popular')]
                             },
                            self.gae_domain,
                            ssl=True
                            )
    
    check_redirect = 'http://%s/login/noreally' % self.domain
    r = self.assertRedirectsPrefix(r, 
                                   check_redirect,
                                   status_code=302,
                                   target_status_code=302)
    r = self.assertRedirectsPrefix(r, 
                                   '/user/popular/overview',
                                   status_code=302,
                                   target_status_code=200)
    o.reset()
    
  def test_api_subdomain(self):
    self.override = util.override(DOMAIN=self.domain,
                                  HOSTED_DOMAIN_ENABLED=True,
                                  HOSTED_DOMAIN=self.hosted_domain,
                                  SUBDOMAINS_ENABLED=True,
                                  )
                                  
    
    r = self.get_with_host('/docs', host='api.%s' % self.hosted_domain)
    self.assertContains(r, 'Documentation')

    r = self.get_with_host('/', host='api.%s' % self.hosted_domain)
    r = self.assertRedirectsPrefix(r, 
                                   'http://api.%s/docs' % self.hosted_domain,
                                   status_code=301
                                   )
    self.assertContains(r, 'Documentation')


  def test_blank_wildcard_subdomain(self):
    self.override = util.override(DOMAIN=self.domain,
                                  HOSTED_DOMAIN_ENABLED=True,
                                  HOSTED_DOMAIN=self.hosted_domain,
                                  SUBDOMAINS_ENABLED=True,
                                  WILDCARD_USER_SUBDOMAINS_ENABLED=True
                                  )
                                  
    
    r = self.get_with_host('', host='%s' % self.hosted_domain)
    r = self.assertRedirectsPrefix(r, 
                                   'http://www.%s' % self.hosted_domain,
                                   status_code=301)
    self.assertContains(r, 'test entry')

  def test_wildcard_subdomain(self):
    self.override = util.override(DOMAIN=self.domain,
                                  HOSTED_DOMAIN_ENABLED=True,
                                  HOSTED_DOMAIN=self.hosted_domain,
                                  SUBDOMAINS_ENABLED=True,
                                  WILDCARD_USER_SUBDOMAINS_ENABLED=True
                                  )
                                  
    
    r = self.get_with_host('', host='popular.%s' % self.hosted_domain)
    self.assertContains(r, 'test entry')

# TODO(termie): remove this, once the temporary fix is removed that breaks
#               all these tests
del DomainTest
