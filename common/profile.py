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
import time

from django import template
from django.conf import settings
from django.template import loader

PROFILE_ALL_TESTS = False

enabled = False
def start():
  global enabled
  enabled = True
  return

def stop():
  global enabled
  enabled = False
  return

def clear():
  global storage
  storage = []

default_label = 'default'
current_label = 'general'

class Label(object):
  """ convenience class for clearing a label """

  name = None
  previous = None

  def __init__(self, name, previous=default_label):
    self.name = name
    self.previous = previous

  def start(self):
    global current_label
    current_label = self.name
    start()

  def stop(self):
    global current_label
    current_label = self.previous
    stop()

def label(name):
  """ for labeling a section of profile data to associate it with
      some specific call or whatever
  """
  l = Label(name, current_label)
  l.start()
  return l


# deco
def _log_call(f, tag='general'):
  call_name = f.func_name
    
  def _wrap(self, *args, **kw):
    if enabled:
      call_self = self
      start_time = time.time()
    rv = f(self, *args, **kw)
    if enabled:
      time_diff = round(time.time() - start_time, 5) * 1000
      store_call(call_self, call_name, tag=tag, time_ms=time_diff)
    return rv
  _wrap.func_name = call_name

  return _wrap

def log_call(tag):
  def _deco(f):
    f = _log_call(f, tag=tag)
    return f
  return _deco

def log_write(f):
  return _log_call(f, tag='write')

def log_read(f):
  return _log_call(f, tag='read')

def profiled(f):
  def _wrap(*args, **kw):
    start()
    rv = f(*args, **kw)
    stop()
  _wrap.func_name = f.func_name
  return _wrap
  
def _log_api_call(f, call_self, tag='api'):
  call_name = f.func_name
    
  def _wrap(*args, **kw):
    if enabled:
      start_time = time.time()
    rv = f(*args, **kw)
    if enabled:
      time_diff = round(time.time() - start_time, 5) * 1000
      store_call(call_self, call_name, tag=tag, time_ms=time_diff)
    return rv
  _wrap.func_name = call_name

  return _wrap

def install_api_profiling():
  from common import api
  for k in dir(api):
    f = getattr(api, k)
    if type(f) != type(log_call):
      continue
    setattr(api, k, _log_api_call(f, api, tag='api')) 



def flattened(header=False):
  o = []
  if header:
    o.append(('tag', 'call', 'time_ms'))
  o.extend(storage)

  return o

def csv(header=False):
  rv = flattened(header)
  csv = '\n'.join([','.join([str(cell) for cell in row]) for row in rv])
  return csv

 
def html():
  # our storage looks like:
  # label, tag, class_func_key, time_ms

  # assumes a single label for now
  o = {}
  total_ms = 0.0
  for (label, tag, class_func_key, time_ms) in storage:
    o.setdefault(tag, {'sub': {}, 'time_ms': 0.0, 'count': 0})

    o[tag]['sub'].setdefault(class_func_key, {'each': [], 'time_ms': 0.0})

    o[tag]['sub'][class_func_key]['each'].append(time_ms)
    o[tag]['sub'][class_func_key]['time_ms'] += time_ms
    
    o[tag]['time_ms'] += time_ms
    o[tag]['count'] += 1

    total_ms += time_ms
  
  for tag in o:
    # sort the calls by name
    o[tag]['sub'] = sorted(o[tag]['sub'].iteritems(), key=lambda x: x[0])


  c = template.Context({'timing': o, 'total': total_ms})
  t = loader.get_template('common/templates/profiling.html')
  return t.render(c)
 

storage = []
def store_call(call_class, call_name, tag='general', time_ms=0.0):
  global current_label
  global enabled

  if not enabled:
    return

  class_name = getattr(call_class, 
                       '__name__', 
                       getattr(call_class.__class__, '__name__')
                       )
  call_class = class_name
  class_func_key = "%s.%s" % (call_class, call_name)

  storage.append((current_label, tag, class_func_key, time_ms))
