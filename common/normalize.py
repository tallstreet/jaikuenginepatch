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

def mobile_number(mobile):
  return mobile

def sms_message(message):
  return message

def nick(nick):
  if not nick or len(nick) == 0:
    return None
  if not '@' in nick:
    return '%s@%s' % (nick, settings.NS_DOMAIN)
  else:
    return nick

def email(email):
  return email

def channel(channel):
  if not channel or len(channel) == 0:
    return None
  if channel[0:1] != '#':
    channel = '#' + channel
  if not '@' in channel:
    return '%s@%s' % (channel, settings.NS_DOMAIN)
  else:
    return channel
