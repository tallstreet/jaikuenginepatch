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
import os

from django import http
from django.conf import settings

class DomainMiddleware(object):
  def process_request(self, request):
    # We've got a few different things to do here depending on settings.
    # TODO(termie): This should really have an associated diagram.

    level = logging.DEBUG
  
    host = request.get_host()
    
    check_url = '%s%s (secure: %s)' % (host, 
                                       request.get_full_path(), 
                                       request.is_secure())
    logging.log(level,'domain|checking| %s', check_url)

    # TODO(termie): Temporary fix
    if host == settings.GAE_DOMAIN:
      return

    full_url = 'http://%s%s' % (settings.DOMAIN, request.get_full_path())
    # TODO(termie): this needs to be significantly smarter, a query string
    #               breaks this immediately
    full_url = full_url.rstrip('/')
    
    # check if we are at one of the urls that needs to be served over SSL
    # TODO(termie): these are hardcoded at the moment
    #               but it seems like incorporating into urls.py is overkill

    if (settings.SSL_LOGIN_ENABLED 
        and (request.path == '/login' 
             or request.path == '/join')):
        ssl_url = 'https://%s%s' % (settings.GAE_DOMAIN, 
                                    request.get_full_path())

        if not request.is_secure():
          logging.log(level,
                      'domain|redirect| ssl on and login but insecure')
          return http.HttpResponsePermanentRedirect(ssl_url)
        
        if not host == settings.GAE_DOMAIN:
          logging.log(level,
                      'domain|redirect| ssl on and login but not gae')
          return http.HttpResponsePermanentRedirect(ssl_url)
        
        logging.log(level,'domain|success | ssl on, secure request, login')   
        return

    # we already handled any of the secure requests we intend on handling
    if request.is_secure():
      logging.log(level,'domain|redirect| unhandled secure request')
      return http.HttpResponsePermanentRedirect(full_url)

    # shortcut if we are now in the proper place
    if host == settings.DOMAIN:
      logging.log(level, 'domain|success | on target domain')
      return

    # if we're not hosted we only have one domain to work with
    if not settings.HOSTED_DOMAIN_ENABLED and host != settings.DOMAIN:
      logging.log(level,'domain|redirect| no hosted domain and %s != %s', 
                   host, 
                   settings.DOMAIN)
      return http.HttpResponsePermanentRedirect(full_url)


    # if we don't have subdomains enabled, we better be at the real domain
    if not settings.SUBDOMAINS_ENABLED and host != settings.DOMAIN:
      logging.log(level,'domain|redirect| subdomains disabled and %s != %s', 
                   host, 
                   settings.DOMAIN)
      return http.HttpResponsePermanentRedirect(full_url)
    

    # TODO(termie): i'm sure this is the least efficient way to do any of this,
    #               but i don't want to waste brain cycles on it at the moment
    host_parts = host.split('.')
    expected_parts = settings.HOSTED_DOMAIN.split('.')
    
    while expected_parts:
      expected_last = expected_parts.pop()
      host_last = host_parts.pop()
      if expected_last != host_last:
        logging.log(level,'domain|redirect| subdomain check, %s not in %s', 
                     host, 
                     settings.HOSTED_DOMAIN)
        return http.HttpResponsePermanentRedirect(full_url)
    
    # the leftovers
    subdomain = '.'.join(host_parts)
    
    if subdomain == '':
        logging.log(level, 'domain|redirect| subdomain check, %s is emptry', 
                    host
                    )
        return http.HttpResponsePermanentRedirect(full_url)

    # check for mobile and tag the request, if it is a double subdomain
    # strip off the .m and continue processing as normal
    elif subdomain == 'm':
      logging.log(level,'domain|mobile| yup')
      request.mobile = True
    elif subdomain.endswith('.m'):
      logging.log(level,'domain|mobile| stripping .m: %s', subdomain)
      request.mobile = True
      subdomain = subdomain[:-2]
    
    # if it is a subdomain we know about
    if subdomain == settings.DEFAULT_HOSTED_SUBDOMAIN:
      logging.log(level,'domain|success | subdomain is default: %s', subdomain)
      return
    elif subdomain in settings.INSTALLED_SUBDOMAINS:
      request.urlconf = settings.INSTALLED_SUBDOMAINS[subdomain]
      logging.log(level,'domain|success | subdomain found: %s', subdomain)
      return
    
    # if we don't have a wildcard we've got nowhere else to go
    if not settings.WILDCARD_USER_SUBDOMAINS_ENABLED:
      logging.log(level,'domain|redirect| subdomain not found and no wildcards: %s',
                   subdomain)
      return http.HttpResponsePermanentRedirect(full_url)
    
    # otherwise this is probably a user page
    request.urlconf = 'actor.urls'
    request.subdomain = subdomain
    logging.log(level,'domain|success | using actor wildcard: %s', subdomain)
    return
