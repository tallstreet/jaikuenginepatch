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
import random

from django.conf import settings
from django.template import RequestContext, loader
from django.http import HttpResponse, HttpResponseRedirect

from common import exception
from common import user
from common.models import Actor

from common import api, util
from common.display import prep_stream_dict, prep_entry_list

ENTRIES_PER_PAGE = 5
SIDEBAR_LIMIT = 9
SIDEBAR_FETCH_LIMIT = 50

def front_front(request):
  # if the user is logged in take them to their overview
  if request.user:
    url = request.user.url(request=request)
    return HttpResponseRedirect(url + "/overview")

  # NOTE: grab a bunch of extra so that we don't ever end up with
  #       less than 5
  per_page = ENTRIES_PER_PAGE * 2

  inbox = api.inbox_get_explore(request.user, limit=per_page)

  # START inbox generation chaos
  # TODO(termie): refacccttttooorrrrr
  entries = api.entry_get_entries(request.user, inbox)
  per_page = per_page - (len(inbox) - len(entries))
  entries, more = util.page_entries(request, entries, per_page)

  stream_keys = [e.stream for e in entries]
  streams = api.stream_get_streams(request.user, stream_keys)

  actor_nicks = [e.owner for e in entries] + [e.actor for e in entries]
  actors = api.actor_get_actors(request.user, actor_nicks)

  # take it back down and don't show a more link
  entries = entries[:ENTRIES_PER_PAGE]
  more = None

  # here comes lots of munging data into shape
  streams = prep_stream_dict(streams, actors)
  entries = prep_entry_list(entries, streams, actors)

  # END inbox generation chaos

  try:
    # Featured Channels -- Ones to which the ROOT user is a member
    featured_channels = api.actor_get_channels_member(
        request.user, api.ROOT.nick, limit=SIDEBAR_FETCH_LIMIT)
    random.shuffle(featured_channels)

    # Just in case any are deleted:
    featured_channels = featured_channels[:2*SIDEBAR_LIMIT]
    featured_channels = api.channel_get_channels(
        request.user, featured_channels)
    featured_channels = [x for x in featured_channels.values() if x]
    featured_channels = featured_channels[:SIDEBAR_LIMIT]

    featured_members = api.actor_get_contacts(
        request.user, api.ROOT.nick, limit=SIDEBAR_FETCH_LIMIT)
    random.shuffle(featured_members)

    # Just in case any are deleted:
    featured_members = featured_members[:2*SIDEBAR_LIMIT]
    featured_members = api.actor_get_actors(request.user, featured_members)
    featured_members = [x for x in featured_members.values() if x]
    featured_members = featured_members[:SIDEBAR_LIMIT]

  except exception.ApiNotFound:
    pass

  root = api.ROOT

  area = 'frontpage'

  t = loader.get_template('front/templates/front.html')
  c = RequestContext(request, locals())

  return HttpResponse(t.render(c));
