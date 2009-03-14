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
import re

from django.conf import settings

from cleanliness import encoding
from common import component
from common.protocol import base

class JID(object):
  _re_jid = re.compile(r'([^:/@]+)@([^/])(/.*)')
  def __init__(self, node, host, resource=None):
    self.node = node
    self.host = host
    self.resource = resource

  @classmethod
  def from_uri(cls, uri):
    # TODO(termie): very simplistic
    #m = cls._re_jid.search(uri)
    node, rest = uri.split('@', 1)
    try:
      host, rest = rest.split('/', 1)
      resource = '/' + rest
    except ValueError:
      host = rest
      resource = '/'
    return cls(node, host, resource)

  def base(self):
    return '%s@%s' % (self.node, self.host)

  def full(self):
    return '%s@%s%s' % (self.node, self.host, self.resource)

class XmppMessage(object):
  sender = None
  target = None
  message = None

  def __init__(self, sender, target, message):
    self.sender = JID.from_uri(sender)
    self.target = JID.from_uri(target)
    self.message = message

  @classmethod
  def from_request(cls, request):
    xmpp_service = component.best['xmpp_service']
    return xmpp_service.from_request(cls, request)

class XmppConnection(base.Connection):
  def send_message(self, to_jid_list, message):
    if settings.IM_TEST_ONLY:
      to_jid_list = [x for x in to_jid_list 
                     if x.base() in settings.IM_TEST_JIDS]

    message = encoding.smart_str(message)
    xmpp_service = component.best['xmpp_service']

    xmpp_service.send_message([j.base() for j in to_jid_list], message)
