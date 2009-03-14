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

import datetime
import logging
import re
import time as py_time

from django.conf import settings

from common import api
from common import clock
from common import exception
from common.protocol import sms
from common.protocol import xmpp


utcnow = lambda: clock.utcnow()

_re_match_url = re.compile(r'(http://[^/]+(/[^\s]+))', re.M)
def get_url(s):
  m = _re_match_url.search(s)
  if not m:
    return None
  return m.group(1)

def get_relative_url(s):
  m = _re_match_url.search(s)
  if not m:
    return None
  return m.group(2)

def exhaust_queue(nick):
  for i in xrange(1000):
    try:
      api.task_process_actor(api.ROOT, nick)
    except exception.ApiNoTasks:
      break
    
def exhaust_queue_any():
  for i in xrange(1000):
    try:
      api.task_process_any(api.ROOT)
    except exception.ApiNoTasks:
      break

class TestXmppConnection(xmpp.XmppConnection):
  def send_message(self, to_jid_list, message):
    logging.debug('XMPP SEND -> %s: %s', to_jid_list, message)
    for jid in to_jid_list:
      xmpp.outbox.append((jid, message))

class TestSmsConnection(sms.SmsConnection):
  def send_message(self, to_list, message):
    to_list = self.filter_targets(to_list, message)
    logging.debug('SMS SEND -> %s: %s', to_list, message)
    for recp in to_list:
      sms.outbox.append((recp, message))

class FakeRequest(object):
  def __init__(self, **kw):
    self.user = kw.get('user', None)
    self.POST = kw.get('post', {})
    self.GET = kw.get('get', {})

  @property
  def REQUEST(self):
    return dict(list(self.POST.items()) + list(self.GET.items()))

class FakeMemcache(object):
  """ a disappointingly full-featured fake memcache :( """
  def __init__(self, *args, **kw):
    self._data = {}
    pass
  
  def _get_valid(self, key):
    if key not in self._data:
      return None
    data = self._data[key]
    if data[1]:
      now = py_time.mktime(utcnow().timetuple())
      if now > data[1]:
        #logging.info('invalid key, %s, %s > %s', key, now, data[1])
        return None
    #logging.info('valid key, %s returning: %s', key, data[0])
    return data[0]

  def set(self, key, value, time=0):
    if time:
      if time < 2592000: # approx 1 month
        time = py_time.mktime(utcnow().timetuple()) + time
    #logging.info('setting key %s to %s', key, (value, time))
    self._data[key] = (value, time)
    return True
  
  def set_multi(self, mapping, time=0, key_prefix=''):
    for k, v in mapping.iteritems():
      self.set(key_prefix + k, v, time=time)
    return []

  def add(self, key, value, time=0):
    if self._get_valid(key) is not None:
      return False
    self.set(key, value, time)
    return True
  
  def incr(self, key, delta=1):
    data = self._get_valid(key)
    if data is None:
      return None
    
    data_tup = self._data[key]
    try:
      count = int(data)
    except ValueError:
      return None
    count += delta
    self.set(key, count, time=data_tup[1])
    return count

  def decr(self, key, delta=1):
    return incr(key, delta=-(delta))
  
  def delete(self, key, seconds=0):
    # NOTE: doesn't support seconds
    try:
      del self._data[key]
      return 2
    except KeyError:
      return 1

  def get(self, key):
    return self._get_valid(key)

  def get_multi(self, keys, key_prefix=''):
    out = {}
    for k in keys:
      v = self._get_valid(key_prefix + k)
      out[k] = v
    return out


class ClockOverride(object):
  old = None
  kw = None

  def __init__(self, module, **kw):
    self.kw = kw
    self.old = {}
    self.module = module

  def override(self):
    self.old = getattr(self.module, 'utcnow')
    new_utcnow = lambda: (datetime.datetime.utcnow() + 
                          datetime.timedelta(**self.kw))
    setattr(self.module, 'utcnow', new_utcnow)
  
  def reset(self):
    setattr(self.module, 'utcnow', self.old)

def override_clock(module, **kw):
  o = ClockOverride(module, **kw)
  o.override()
  return o

class SettingsOverride(object):
  old = None
  kw = None

  def __init__(self, **kw):
    self.kw = kw
    self.old = {}

  def override(self):
    for k, v in self.kw.iteritems():
      self.old[k] = getattr(settings, k, None)
      setattr(settings, k, v)
  
  def reset(self):
    for k, v in self.old.iteritems():
      setattr(settings, k, v)

def override(**kw):
  o = SettingsOverride(**kw)
  o.override()
  return o
