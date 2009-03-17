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

from django import template
from django.utils.html import escape
from common.util import safe

register = template.Library()

@register.filter(name="location")
def location(value, arg=None):
  if type(value) is type('str') or type(value) is type(u'ustr'):
    return value

  try:
    country = value.get('country', {}).get('name', None)
    city = value.get('city', {}).get('name', None)
    base = value.get('base', {}).get('current', {}).get('name', None)
    cell = value.get('cell', {}).get('name', None)
    parts = []
    if base:
      parts.append(base)
    elif cell:
      parts.append(cell)
    if city:
      parts.append(city)
    if country:
      parts.append(country)
    return ', '.join(parts)
  except Exception, exc:
    return '?'
