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

from google.appengine.api import xmpp

def send_message(jids, body, from_jid=None,
                 message_type=xmpp.MESSAGE_TYPE_CHAT, raw_xml=False):
  return xmpp.send_message(jids, body, from_jid, message_type, raw_xml)


def from_request(cls, request):
  params = {'sender': request.REQUEST.get('from'),
            'target': request.REQUEST.get('to'),
            'message': request.REQUEST.get('body'),
            }
  return cls(**params)

