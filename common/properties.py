#!/usr/bin/python2.4
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
__author__ = 'termie@google.com (Andy Smith)'

import re
import time, datetime
try:
  import cPickle as pickle
except ImportError:
  import pickle

from google.appengine.ext import db
from google.appengine.api.datastore_types import Blob

DJANGO_DATE = "%Y-%m-%d"
DJANGO_TIME = "%H:%M:%S"

class DateTimeProperty(db.DateTimeProperty):
  def validate(self, value):
    """Validate a datetime, attempt to convert from string

    Returns:
      A valid datetime object
    """
    # XXX termie: pretty naive at this point, ask for forgiveness
    try:
      us = 0
      m_fractional = re.search('(.*)\.(\d+)$', value)
      if (m_fractional):
        value = m_fractional.group(1)
        fractional_s = m_fractional.group(2)
        scaled_to_us = fractional_s + '0' * (6 - len(fractional_s))
        truncated_to_us = scaled_to_us[0:6]
        us = int(truncated_to_us)
      t = time.strptime(value, "%s %s"%(DJANGO_DATE, DJANGO_TIME))
      t = (t)[0:6] + (us,)
      d = datetime.datetime(*t)
      value = d

    except ValueError, e:
      # eat the error
      pass
    except TypeError, e:
      # we passed it a datetime, probably, let the orignal handle this
      pass

    value = super(DateTimeProperty, self).validate(value)
    return value

class DictProperty(db.Property):
  def validate(self, value):
    value = super(DictProperty, self).validate(value)
    if not isinstance(value, dict):
      raise Exception("NOT A DICT %s" % value)
    return value

  def default_value(self):
    return {}

  def datastore_type(self):
    return Blob

  def get_value_for_datastore(self, model_instance):
    value = super(DictProperty, self).get_value_for_datastore(model_instance)
    return Blob(pickle.dumps(value, protocol=-1))

  def make_value_from_datastore(self, model_instance):
    value = super(DictProperty, self).make_value_from_datastore(model_instance)
    return pickle.loads(str(value))
