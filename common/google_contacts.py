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

import math
import random
import logging
import time
import urllib

import atom.service
import gdata.auth
import gdata.service
import gdata.alt.appengine
import simplejson

from django.conf import settings

from common import exception


CONTACTS_RESOURCE = "http://www.google.com/m8/feeds/contacts/default/full?alt=json&start-index=%d&max-results=%d&orderby=lastmodified&sortorder=descending"
GROUPS_RESOURCE = "http://www.google.com/m8/feeds/groups/default/full?alt=json"

SCOPE_URL = 'http://www.google.com/m8/feeds'

converter = lambda x: x


def client():
  additional_headers = {'GData-Version': '2'}
  client = gdata.service.GDataService(additional_headers=additional_headers)
  gdata.alt.appengine.run_on_appengine(client)
  return client
  

def auth_sub_url(next_url):
  c = client()
  params = {'secure': False,
            'session': True}
  if settings.EMAIL_LIMIT_DOMAIN:
    params['domain'] = settings.EMAIL_LIMIT_DOMAIN

  auth_url = c.GenerateAuthSubURL(next_url,
                                  (SCOPE_URL,),
                                  **params)
  return auth_url

def auth_sub_token_from_request(request):
  return gdata.auth.extract_auth_sub_token_from_url(request.get_full_path())

def upgrade_to_session_token(token):
  c = client()
  return c.upgrade_to_session_token(token)
  
def get_groups(token):
  c = client()
  c.override_token = token
    
  resource = GROUPS_RESOURCE
  try:
    feed_json = c.Get(resource, converter=converter)
    rv = simplejson.loads(feed_json)
  except gdata.service.RequestError, e:
    raise
    if e.args and 'status' in e.args[0] and e.args[0]['status'] == 401:
      raise exception.ServiceError('Invalid AuthSub token')
    raise
  
  return rv['feed']['entry']

def get_system_group(token, group="Contacts"):
  groups = get_groups(token)
  for group in groups:
    if group.get('gContact$systemGroup', {}).get('id') == 'Contacts':
      return group['id']['$t']
  return None

def get_contacts(token, group=None, index=1, max=100):
  """ retrieves the list of contacts for the given email address, token needs
      to be authorised for this user """
  c = client()
  c.override_token = token
  
  logging.info("TOKEN %s", token)

  resource = CONTACTS_RESOURCE % (index, max + 1)
  if group:
    resource += "&" + urllib.urlencode({'group': group})


  logging.info("Starting fetch of GData feed at %s", resource)

  more = False
  try:
    feed_json = c.Get(resource, converter=converter)
    rv = simplejson.loads(feed_json)
    if len(rv['feed']['entry']) > max:
      more = index + max
  except gdata.service.RequestError, e:
    raise
    if e.args and 'status' in e.args[0] and e.args[0]['status'] == 401:
      raise exception.ServiceError('Invalid AuthSub token')
    raise
  
  return rv['feed']['entry'][:max], more

def get_contacts_emails(token, group=None, index=1, max=100):
  raw_contacts, more = get_contacts(token, group, index, max)
  contacts = []
  for c in raw_contacts:
    name = c['title']['$t']
    for e in c.get('gd$email', []):
      contacts.append((name, e['address']))
  return contacts, more
