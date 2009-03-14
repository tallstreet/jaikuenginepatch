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

from django import http
from django import template
from django.conf import settings
from django.template import loader

from common import api
from common import display
from common import util
from common import views as common_views

def invite_email(request, code):
  """User has received the invite email, and has followed the link to accept or
     or refuse it."""
  
  if request.user:
    handled = common_views.handle_view_action(
        request,
        {'invite_accept': request.user.url('/overview'),
         'invite_reject': request.user.url('/overview')
         }
        )
    if handled:
      return handled

  # Retrieve the invite
  invite = api.invite_get(api.ROOT, code)
  from_actor = invite.from_actor
  
  # Translate the from_actor into a display name
  from_actor_ref = api.actor_get(api.ROOT, from_actor)
  view = from_actor_ref

  if not from_actor_ref:
    # Corner case: from_actor was deleted since the invite was sent.
    # In this case, do we want to consider the invitation invalid?
    # (probably we do, because it's more likely that it was spam)
    return util.RedirectError("That invite is no longer valid")
    
    
  # We use api.ROOT in the next set of functions because the
  # invite is giving possibly private access to the user
  inbox = api.inbox_get_actor_contacts(api.ROOT,
                                       view.nick,
                                       limit=5)
  entries = api.entry_get_entries(api.ROOT, inbox)
  stream_keys = [e.stream for e in entries]
  streams = api.stream_get_streams(api.ROOT, stream_keys)
  actor_nicks = ([view.nick] +
                 [s.owner for s in streams.values() if s] +
                 [e.owner for e in entries] +
                 [e.actor for e in entries])
  actors = api.actor_get_actors(api.ROOT, actor_nicks)

  streams = display.prep_stream_dict(streams, actors)
  entries = display.prep_entry_list(entries, streams, actors)


  sidebar_green_top = True
  c = template.RequestContext(request, locals())

  t = loader.get_template('invite/templates/email.html')
  return http.HttpResponse(t.render(c))
