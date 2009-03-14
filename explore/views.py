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

from common import api, util
from common.display import prep_entry_list, prep_stream_dict

ENTRIES_PER_PAGE = 20

def explore_recent(request, format="html"):

  per_page = ENTRIES_PER_PAGE
  offset, prev = util.page_offset(request)

  inbox = api.inbox_get_explore(request.user, limit=(per_page + 1),
                                offset=offset)

  # START inbox generation chaos
  # TODO(termie): refacccttttooorrrrr
  entries = api.entry_get_entries(request.user, inbox)
  per_page = per_page - (len(inbox) - len(entries))
  entries, more = util.page_entries(request, entries, per_page)

  stream_keys = [e.stream for e in entries]

  streams = api.stream_get_streams(request.user, stream_keys)

  actor_nicks = [e.owner for e in entries] + [e.actor for e in entries]
  actors = api.actor_get_actors(request.user, actor_nicks)

  # here comes lots of munging data into shape
  streams = prep_stream_dict(streams, actors)
  entries = prep_entry_list(entries, streams, actors)

  # END inbox generation chaos

  area = 'explore'
  sidebar_green_top = True
  
  c = template.RequestContext(request, locals())

  if format == 'html':
    t = loader.get_template('explore/templates/recent.html')
    return http.HttpResponse(t.render(c));
  elif format == 'json':
    t = loader.get_template('explore/templates/recent.json')
    r = util.HttpJsonResponse(t.render(c), request)
    return r
  elif format == 'atom':
    t = loader.get_template('explore/templates/recent.atom')
    r = util.HttpAtomResponse(t.render(c), request)
    return r
  elif format == 'rss':
    t = loader.get_template('explore/templates/recent.rss')
    r = util.HttpRssResponse(t.render(c), request)
    return r
