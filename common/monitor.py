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

""" A library to export some stats that we can use for monitoring.
"""

def export(values):
  o = []
  for k, v in sorted(values.items()):
    o.append('%s %s' % (escape(k), build_value(v)))
  return '\n'.join(o)
      
class ExportedMap(object):
  def __init__(self, label, value):
    self.label = label
    self.value = value

  def __str__(self):
    o = ['map:%s' % escape(self.label)]
    for k, v in sorted(self.value.items()):
      o.append('%s:%s' % (escape(k), escape(v)))
    return ' '.join(o)

class ExportedList(object):
  def __init__(self, value):
    self.value = value

  def __str__(self):
    return '/'.join([escape(v) for v in self.value])

class ExportedCallable(object):
  def __init__(self, callable):
    self.callable = callable

  def __str__(self):
    return make_value(self.callable())

def build_value(value):
  """ attempt to do some inference of types """
  # a dict, with label
  if type(value) is type(tuple()) and type(value[1]) is type(dict()):
    return ExportedMap(label=value[0], value=value[1])
  elif type(value) is type(tuple()) or type(value) is type(list()):
    return ExportedList(value)
  elif callable(value):
    return ExportedCallable(value)
  else:
    return escape(value)

def escape(value):
  return str(value).replace('\\', '\\\\').replace(':', '\\:').replace(' ', '-')
