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
import time

from django.conf import settings

from common import clock
from common import exception
from common import memcache

# Wrap utcnow so that it can be mocked in tests. We can't replace the function
# in the datetime module because it's an extension, not a python module.
utcnow = lambda: clock.utcnow()

def _d2t(dt):
  return time.mktime(dt.timetuple())

# TODO(termie): replace month with an implementation that gives the first
#               second of next month rather than this 30-days from now
BUCKETS = {'minute': lambda: _d2t(utcnow()) + 60,
           'hour': lambda: _d2t(utcnow()) + 60 * 60,
           'day': lambda: _d2t(utcnow()) + 60 * 60 * 24,
           'month': lambda: _d2t(utcnow()) + 60 * 60 * 24 * 30,
           } 

def throttle_key(actor_ref, action, bucket):
  nick = ''
  if actor_ref:
    nick = actor_ref.nick
  return 'throttle/%s/%s/%s' % (nick, action, bucket)

def throttle(actor_ref, action, **kw):
  """ enforces throttling of some action per user with defined limits
  """
  if actor_ref and actor_ref.nick == settings.ROOT_NICK:
    return

  already_throttled = False
  for k, v in kw.iteritems():
    if k in BUCKETS:
      throttled = throttle_status(actor_ref, action, bucket=k, max=v)
      
      # if anything is throttled we will raise an error in the end
      if throttled and not already_throttled:
        already_throttled = k

      # for any thresholds not yet hit increase the count
      if not throttled:
        throttle_inc(actor_ref, action, bucket=k)
        
  if already_throttled:
    raise exception.ApiThrottled(
        'Too many attempts this %s' % already_throttled)

def throttle_status(actor_ref, action, bucket, max):
  """ check whether a throttling threshold has been hit
  """
  cache_key = throttle_key(actor_ref, action, bucket)
  count = memcache.client.get(cache_key)
  if count >= max:
    return True
  return False

def throttle_inc(actor_ref, action, bucket):
  timeout = BUCKETS[bucket]()
  cache_key = throttle_key(actor_ref, action, bucket)
  
  memcache.client.add(cache_key, 0, timeout)
  memcache.client.incr(cache_key)
