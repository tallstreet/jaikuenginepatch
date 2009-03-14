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

from django import http
from django import template
from django.conf import settings
from django.template import loader

from common import api
from common import clean


def badge_badge(request, format, nick):
  view = api.actor_get(request.user, nick)
  
  presence = api.presence_get(request.user, view.nick)
  
  if not presence:
    # look offline please
    line = 'Offline'
    light = 'gray'
    location = ''
  else:
    line = presence.extra.get('status', 'Offline')
    light = presence.extra.get('light', 'gray')
    location = presence.extra.get('location', '')

  if format == 'image':
    return http.HttpResponseRedirect('/images/badge_%s.gif' % light)

  if format == 'js-small':
    multiline = len(line) > 17
    truncated_line = len(line) > 30 and "%s..." % (line[:27]) or line
    content_type = 'text/javascript'
    template_path = 'js_small.js'
  elif format == 'js-medium' or format == 'js-large':
    truncated_line = len(line) > 40 and "%s..." % (line[:27]) or line
    content_type = 'text/javascript'
    template_path = '%s.js' % format.replace('-', '_')
  elif format == 'json':
    content_type = 'text/javascript'
    template_path = 'badge.json'

  elif format == 'xml':
    content_type = 'application/xml'
    template_path = 'badge.xml'

  c = template.RequestContext(request, locals())
  t = loader.get_template('badge/templates/%s' % template_path)
  r = http.HttpResponse(t.render(c))
  r['Content-type'] = content_type
  return r
