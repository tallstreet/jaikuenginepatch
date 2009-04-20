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
from common import decorator
from common import display
from common import exception
from common import normalize
from common import user
from common import util
from common import validate
from common import views as common_views

CHANNEL_HISTORY_PER_PAGE = 20
CHANNELS_PER_INDEX_PAGE = 12
CHANNELS_PER_PAGE = 24
CONTACTS_PER_PAGE = 24


@decorator.login_required
def channel_create(request, format='html'):
  channel = request.REQUEST.get('channel', '')

  handled = common_views.handle_view_action(
      request,
      {'channel_create': '/channel/%s' % channel,
       }
      )
  if handled:
    return handled

  # for template sidebar
  sidebar_green_top = True

  area = 'channel'
  c = template.RequestContext(request, locals())

  if format == 'html':
    t = loader.get_template('channel/templates/create.html')
    return http.HttpResponse(t.render(c))


def channel_index(request, format='html'):
  """ the index page for channels, /channel

  should list the channels you administer, the channels you belong to
  and let you create new channels

  if you are not logged in, it should suggest that you log in to create or
  join channels and give a list of public channels
  """
  if not request.user:
    return channel_index_signedout(request, format='html')

  owned_nicks = api.actor_get_channels_admin(
      request.user,
      request.user.nick,
      limit=(CHANNELS_PER_INDEX_PAGE + 1))
  owned_more = len(owned_nicks) > CHANNELS_PER_INDEX_PAGE

  followed_nicks = api.actor_get_channels_member(
      request.user,
      request.user.nick,
      limit=(CHANNELS_PER_INDEX_PAGE + 1))
  followed_more = len(owned_nicks) > CHANNELS_PER_INDEX_PAGE

  channel_nicks = owned_nicks + followed_nicks
  channels = api.channel_get_channels(request.user, channel_nicks)

  owned_channels = [channels[x] for x in owned_nicks if channels[x]]
  for c in owned_channels:
    c.i_am_admin = True

  followed_channels = [
      channels[x] for x in followed_nicks 
          if channels[x] and x not in owned_nicks
  ]
  for c in followed_channels:
    c.i_am_member = True

  try:
    # for the Our Picks section of the sidebar
    ourpicks_channels = api.actor_get_channels_member(request.user, api.ROOT.nick)
    ourpicks_channels = api.channel_get_channels(request.user, ourpicks_channels)  
    ourpicks_channels = [x for x in ourpicks_channels.values() if x]
  except exception.ApiNotFound:
    pass

  area = 'channel'
  c = template.RequestContext(request, locals())

  if format == 'html':
    t = loader.get_template('channel/templates/index.html')
    return http.HttpResponse(t.render(c))


def channel_index_signedout(request, format='html'):
  # for the Our Picks section of the sidebar
  ourpicks_channels = api.actor_get_channels_member(request.user, api.ROOT.nick)
  ourpicks_channels = api.channel_get_channels(request.user, ourpicks_channels)  
  ourpicks_channels = [x for x in ourpicks_channels.values() if x]

  area = 'channel'
  c = template.RequestContext(request, locals())

  if format == 'html':
    t = loader.get_template('channel/templates/index_signedout.html')
    return http.HttpResponse(t.render(c))


def channel_history(request, nick, format='html'):
  """ the page for a channel

  if the channel does not exist we go to create channel instead

  should let you join a channel or post to it if you already are a member
  also leave it if you are a member,
  display the posts to this channel and the member list if you are allowed
  to see them

  if you are an admin you should have the options to modify the channel
  """
  nick = clean.channel(nick)

  view = api.actor_lookup_nick(request.user, nick)
  if not view:
    return http.HttpResponseRedirect('/channel/create?channel=%s' % nick)

  admins = api.channel_get_admins(request.user, channel=view.nick)
  members = api.channel_get_members(request.user, channel=view.nick)

  handled = common_views.handle_view_action(
      request,
      {'channel_join': request.path,
       'channel_part': request.path,
       'channel_post': request.path,
       'entry_remove': request.path,
       'entry_remove_comment': request.path,
       'entry_mark_as_spam': request.path,
       'subscription_remove': request.path,
       'subscription_request': request.path,
       }
      )
  if handled:
    return handled

  privacy = 'public'

  user_can_post = False
  user_is_admin = False
  if not request.user:
    pass
  elif api.channel_has_admin(request.user, view.nick, request.user.nick):
    privacy = 'private'
    user_can_post = True
    user_is_admin = True
  elif api.channel_has_member(request.user, view.nick, request.user.nick):
    privacy = 'contacts'
    user_can_post = True

  per_page = CHANNEL_HISTORY_PER_PAGE
  offset, prev = util.page_offset(request)

  if privacy == 'public':
    inbox = api.inbox_get_actor_public(
        request.user,
        view.nick,
        limit=(per_page + 1),
        offset=offset)
  elif privacy == 'contacts':
    inbox = api.inbox_get_actor_contacts(
        request.user,
        view.nick,
        limit=(per_page + 1),
        offset=offset)
  elif privacy == 'private':
    inbox = api.inbox_get_actor_private(
        api.ROOT,
        view.nick,
        limit=(per_page + 1),
        offset=offset)

  # START inbox generation chaos
  # TODO(termie): refacccttttooorrrrr

  entries = api.entry_get_entries(request.user, inbox)
  # clear out deleted entries
  per_page = per_page - (len(inbox) - len(entries))
  entries, more = util.page_entries(request, entries, per_page)

  stream_keys = [e.stream for e in entries]
  actor_streams = api.stream_get_actor(request.user, view.nick)
  stream_keys += [s.key().name() for s in actor_streams]
  streams = api.stream_get_streams(request.user, stream_keys)

  contact_nicks = api.actor_get_contacts(request.user, view.nick)
  actor_nicks = (contact_nicks +
                 admins +
                 members +
                 [view.nick] +
                 [s.owner for s in streams.values()] +
                 [e.actor for e in entries])
  actors = api.actor_get_actors(request.user, actor_nicks)

  # here comes lots of munging data into shape
  contacts = [actors[x] for x in contact_nicks if actors[x]]
  streams = display.prep_stream_dict(streams, actors)
  entries = display.prep_entry_list(entries, streams, actors)
  admins = [actors[x] for x in admins if actors[x]]
  members = [actors[x] for x in members if actors[x]]

  # END inbox generation chaos

  presence = api.presence_get(request.user, view.nick)

  # for sidebar_members
  members_count = view.extra['member_count']
  members_more = members_count > CONTACTS_PER_PAGE

  # for sidebar_admins
  admins_count = view.extra['admin_count']
  admins_more = admins_count > CONTACTS_PER_PAGE

  # config for templates
  green_top = True
  sidebar_green_top = True
  selectable_icons = display.SELECTABLE_ICONS


  # for sidebar streams (copied from actor/views.py.  refactor)
  view_streams = dict([(x.key().name(), streams[x.key().name()])
                       for x in actor_streams])
  if request.user:
    # un/subscribe buttons are possible only, when logged in

    # TODO(termie): what if there are quite a lot of streams?
    for stream in view_streams.values():
      stream.subscribed = api.subscription_exists(
          request.user,
          stream.key().name(),
          'inbox/%s/overview' % request.user.nick
          )

  area = 'channel'
  c = template.RequestContext(request, locals())

  if format == 'html':
    t = loader.get_template('channel/templates/history.html')
    return http.HttpResponse(t.render(c))
  elif format == 'json':
    t = loader.get_template('channel/templates/history.json')
    r = util.HttpJsonResponse(t.render(c), request)
    return r
  elif format == 'atom':
    t = loader.get_template('channel/templates/history.atom')
    r = util.HttpAtomResponse(t.render(c), request)
    return r
  elif format == 'rss':
    t = loader.get_template('channel/templates/history.rss')
    r = util.HttpRssResponse(t.render(c), request)
    return r


def channel_item(request, nick, item=None, format='html'):
  nick = clean.channel(nick)
  view = api.actor_lookup_nick(request.user, nick)

  if not view:
    raise http.Http404()

  stream_ref = api.stream_get_presence(request.user, view.nick)

  entry = '%s/%s' % (stream_ref.key().name(), item)

  entry_ref = api.entry_get(request.user, entry)
  if not entry_ref:
    raise http.Http404()

  handled = common_views.handle_view_action(
      request,
      {'entry_add_comment': entry_ref.url(), 
       'entry_remove': view.url(),
       'entry_remove_comment': entry_ref.url(),
       'entry_mark_as_spam': entry_ref.url()
       }
      )
  if handled:
    return handled

  admins = api.channel_get_admins(request.user, channel=view.nick)
  user_is_admin = request.user and request.user.nick in admins

  comments = api.entry_get_comments(request.user, entry)

  actor_nicks = [entry_ref.owner, entry_ref.actor] + [c.actor for c in comments]
  actors = api.actor_get_actors(request.user, actor_nicks)

  # Creates a copy of actors with lowercase keys (Django #6904: template filter
  # dictsort sorts case sensitive), excluding channels and the currently
  # logged in user.
  participants = {}
  for k, v in actors.iteritems():
    if (v and
        not v.is_channel() and
        not (hasattr(request.user, 'nick') and request.user.nick == v.nick)):
      participants[k.lower()] = v

  # display munge
  entry = display.prep_entry(entry_ref,
                             { stream_ref.key().name(): stream_ref },
                             actors)
  comments = display.prep_comment_list(comments, actors)

  # config for template
  green_top = True
  sidebar_green_top = True

  # rendering
  c = template.RequestContext(request, locals())
  if format == 'html':
    t = loader.get_template('channel/templates/item.html')
    return http.HttpResponse(t.render(c))
  elif format == 'json':
    t = loader.get_template('actor/templates/item.json')
    r = http.HttpResponse(t.render(c))
    r['Content-type'] = 'text/javascript'
    return r


def channel_browse(request, format='html'):
  per_page = CHANNELS_PER_PAGE
  prev_offset, _ = util.page_offset_nick(request)

  # Use +1 to identify if there are more that need to be displayed.
  channel_list = api.channel_browse(request.user, (per_page+1), prev_offset)

  actors, more = util.page_actors(request, channel_list, per_page)
  offset_text = 'More'
  
  # for the Our Picks section of the sidebar
  ourpicks_channels = api.actor_get_channels_member(request.user, api.ROOT.nick)
  ourpicks_channels = api.channel_get_channels(request.user, ourpicks_channels)  
  ourpicks_channels = [x for x in ourpicks_channels.values() if x]

  area = 'channel'
  c = template.RequestContext(request, locals())

  # TODO(tyler): Other output formats.
  if format == 'html':
    t = loader.get_template('channel/templates/browse.html')
    return http.HttpResponse(t.render(c))

def channel_members(request, nick=None, format='html'):
  nick = clean.channel(nick)

  view = api.actor_lookup_nick(request.user, nick)

  if not view:
    raise exception.UserDoesNotExistError(nick, request.user)

  handled = common_views.handle_view_action(
      request,
      { 'actor_add_contact': request.path,
        'actor_remove_contact': request.path, })
  if handled:
    return handled

  per_page = CONTACTS_PER_PAGE
  offset, prev = util.page_offset_nick(request)

  follower_nicks = api.channel_get_members(request.user,
                                           view.nick,
                                           limit=(per_page + 1),
                                           offset=offset)
  actor_nicks = follower_nicks
  actors = api.actor_get_actors(request.user, actor_nicks)
  # clear deleted actors
  actors = dict([(k, v) for k, v in actors.iteritems() if v])
  per_page = per_page - (len(follower_nicks) - len(actors))

  whose = "%s's" % view.display_nick()

  # here comes lots of munging data into shape
  actor_tiles = [actors[x] for x in follower_nicks if x in actors]

  actor_tiles_count = view.extra.get('member_count', 0)
  actor_tiles, actor_tiles_more = util.page_actors(request,
                                                   actor_tiles,
                                                   per_page)

  area = 'channels'

  c = template.RequestContext(request, locals())

  if format == 'html':
    t = loader.get_template('channel/templates/members.html')
    return http.HttpResponse(t.render(c))


@decorator.login_required
def channel_settings(request, nick, page='index'):
  nick = clean.channel(nick)

  view = api.actor_lookup_nick(request.user, nick)

  if not view:
    # Channel doesn't exist, bounce the user back so they can create it.
    # If the channel was just deleted, don't.  This unfortunately, misses the
    # case where a user is attempting to delete a channel that doesn't
    # exist.
    return http.HttpResponseRedirect('/channel/%s' % nick)

  handled = common_views.handle_view_action(
      request,
      {
        'channel_update': request.path,
        'actor_remove' : '/channel',
      }
  )
  if page == 'photo' and not handled:
    handled = common_views.common_photo_upload(request, request.path, nick)
  if page == 'design' and not handled:
    handled = common_views.common_design_update(request, nick)

  if handled:
    return handled

  area = 'settings'
  avatars = display.DEFAULT_AVATARS
  actor_url = '/channel/%s' % nick

  if page == 'index':
    pass
  elif page == 'badge':
    badges = [{'id': 'badge-stream',
               'width': '200',
               'height': '300',
               'src': '/themes/%s/badge.swf' % settings.DEFAULT_THEME,
               'title': 'Stream',
               },
              {'id': 'badge-map',
               'width': '200',
               'height': '255',
               'src': '/themes/%s/badge-map.swf' % settings.DEFAULT_THEME,
               'title': 'Map',
               },
              {'id': 'badge-simple',
               'width': '200',
               'height': '200',
               'src': '/themes/%s/badge-simple.swf' % settings.DEFAULT_THEME,
               'title': 'Simple',
               },
              ]
  elif page == 'delete':
    pass
  elif page == 'design':
    pass
  elif page == 'details':
    pass
  elif page == 'photo':
    pass
  else:
    return common_views.common_404(request)

  # full_page adds the title of the sub-component.  Not useful if it's the
  # main settings page
  if page != 'index':
    full_page = page.capitalize()

  # rendering
  c = template.RequestContext(request, locals())
  t = loader.get_template('channel/templates/settings_%s.html' % page)
  return http.HttpResponse(t.render(c))
