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
from common import exception
from common import models
from common import user
from common import util
from common import validate
from common import display
from common import views as common_views

ENTRIES_PER_PAGE = 20
CONTACTS_PER_PAGE = 48

# This is a decorator to make it a bit easier to deal with the possibility
# the nick coming in via the subdomain
def alternate_nick(f):
  def _wrap(request, *args, **kw):
    if settings.WILDCARD_USER_SUBDOMAINS_ENABLED:
      # grab the nick from the subdomain
      if hasattr(request, 'subdomain'):
        kw['nick'] = request.subdomain
    return f(request, *args, **kw)
  _wrap.func_name = f.func_name
  return _wrap

@alternate_nick
def actor_history(request, nick=None, format='html'):
  nick = clean.nick(nick)
  view = api.actor_lookup_nick(request.user, nick)

  if not view:
    raise exception.UserDoesNotExistError(nick, request.user)

  called_subscribe, sub_ref = common_views.call_api_from_request(
      request, 'subscription_request')
  if called_subscribe:
    if sub_ref.state == 'subscribed':
      message = 'Subscribed.'
    else:
      message = 'Subscription requested.'
    return util.RedirectFlash(view.url(), message)

  handled = common_views.handle_view_action(
      request,
      { 'entry_remove': request.path,
        'entry_remove_comment': request.path,
        'entry_mark_as_spam': request.path,
        'subscription_remove': view.url(),
        'actor_add_contact': request.path,
        'actor_remove_contact': request.path,
        'post': request.path,
        'presence_set': request.path,
      }
  )
  if handled:
    return handled

  privacy = 'public'
  if request.user:
    if view.nick == request.user.nick:
      privacy = 'private'
    # ROOT because we care whether or not request.user is a contact of
    # the view user's, not whether the request.user can see the contacts
    elif api.actor_has_contact(api.ROOT, view.nick, request.user.nick):
      privacy = 'contacts'

  # we're going to hide a bunch of stuff if this user is private and we
  # aren't allowed to see
  user_is_private = False
  if view.privacy < models.PRIVACY_PUBLIC and privacy == 'public':
    user_is_private = True

  per_page = ENTRIES_PER_PAGE
  offset, prev = util.page_offset(request)

  if privacy == 'public':
    if user_is_private:
      inbox = []
    else:
      inbox = api.inbox_get_actor_public(request.user, view.nick,
                                         limit=(per_page + 1), offset=offset)
  elif privacy == 'contacts':
    inbox = api.inbox_get_actor_contacts(request.user, view.nick,
                                         limit=(per_page + 1), offset=offset)
  elif privacy == 'private':
    inbox = api.inbox_get_actor_private(request.user, view.nick,
                                        limit=(per_page + 1), offset=offset)

  # START inbox generation chaos
  # TODO(termie): refacccttttooorrrrr
  entries = api.entry_get_entries(request.user, inbox)
  per_page = per_page - (len(inbox) - len(entries))
  entries, more = util.page_entries(request, entries, per_page)

  stream_keys = [e.stream for e in entries]
  try:
    actor_streams = api.stream_get_actor(request.user, view.nick)
  except exception.ApiException:
    actor_streams = []
  stream_keys += [s.key().name() for s in actor_streams]
  streams = api.stream_get_streams(request.user, stream_keys)

  try:
    contact_nicks = api.actor_get_contacts(request.user, 
                                           view.nick, 
                                           limit=CONTACTS_PER_PAGE)
  except exception.ApiException:
    contact_nicks = []

  actor_nicks = (contact_nicks +
                 [view.nick] +
                 [s.owner for s in streams.values()] +
                 [e.owner for e in entries] +
                 [e.actor for e in entries])
  actors = api.actor_get_actors(request.user, actor_nicks)

  # here comes lots of munging data into shape
  contacts = [actors[x] for x in contact_nicks if actors[x]]
  streams = display.prep_stream_dict(streams, actors)
  entries = display.prep_entry_list(entries, streams, actors)

  # END inbox generation chaos

  # If not logged in, cannot write
  is_owner = request.user and view.nick == request.user.nick

  try:
    presence = api.presence_get(request.user, view.nick)
    presence_stream = api.stream_get_presence(request.user, view.nick)
    last_entry = api.entry_get_last(request.user, presence_stream.keyname())
    view.last_entry = last_entry
  except exception.ApiException:
    pass


  # for add/remove contact
  if request.user:
    user_is_contact = api.actor_has_contact(request.user,
                                            request.user.nick,
                                            view.nick)
    view.my_contact = user_is_contact
  else:
    user_is_contact = False

  # for sidebar streams
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


  # for sidebar_contacts
  contacts_count = view.extra.get('contact_count', 0)
  contacts_more = contacts_count > CONTACTS_PER_PAGE

  # Config for the template
  green_top = True
  sidebar_green_top = True
  selectable_icons = display.SELECTABLE_ICONS
  area = 'user'

  c = template.RequestContext(request, locals())

  if format == 'html':
    t = loader.get_template('actor/templates/history.html')
    return http.HttpResponse(t.render(c))
  elif format == 'json':
    t = loader.get_template('actor/templates/history.json')
    r = util.HttpJsonResponse(t.render(c), request)
    return r
  elif format == 'atom':
    t = loader.get_template('actor/templates/history.atom')
    r = util.HttpAtomResponse(t.render(c), request)
    return r
  elif format == 'rss':
    t = loader.get_template('actor/templates/history.rss')
    r = util.HttpRssResponse(t.render(c), request)
    return r

@decorator.login_required
@alternate_nick
def actor_invite(request, nick, format='html'):
  nick = clean.nick(nick)

  view = api.actor_lookup_nick(request.user, nick)
  if not view:
    raise exception.UserDoesNotExistError(nick, request.user)

  if view.nick != request.user.nick:
    # Bounce the user to their own page (avoids any confusion for the wrong
    # nick in the url).
    return http.HttpResponseRedirect(
        '%s/invite' % request.user.url())
  
  handled = common_views.handle_view_action(
      request,
      { 'invite_request_email': request.path, })
  if handled:
    return handled

  if request.user and request.user.nick == view.nick:
    whose = 'Your'
  else:
    whose = "%s's" % view.display_nick()

  c = template.RequestContext(request, locals())

  if format == 'html':
    t = loader.get_template('actor/templates/invite.html')
    return http.HttpResponse(t.render(c))

@alternate_nick
def actor_overview(request, nick, format='html'):
  nick = clean.nick(nick)

  view = api.actor_lookup_nick(request.user, nick)

  if not view:
    raise exception.UserDoesNotExistError(nick, request.user)

  if not request.user or view.nick != request.user.nick:
    # Instead of displaying the overview, redirect to the public-facing page
    return http.HttpResponseRedirect(view.url())

  handled = common_views.handle_view_action(
      request,
      { 
        'entry_remove': request.path,
        'entry_remove_comment': request.path,
        'entry_mark_as_spam': request.path,
        'presence_set': request.path,
        'settings_hide_comments': request.path,
        'post': request.path,
      }
  )
  if handled:
    return handled

  per_page = ENTRIES_PER_PAGE
  offset, prev = util.page_offset(request)

  inbox = api.inbox_get_actor_overview(request.user,  
                                       view.nick,
                                       limit=(per_page + 1), 
                                       offset=offset)

  # START inbox generation chaos
  # TODO(termie): refacccttttooorrrrr
  entries = api.entry_get_entries(request.user, inbox)
  
  if view.extra.get('comments_hide', 0):
    # TODO(tyler): This is certainly not the most eloquent way to filter
    # through entries to remove comments.
    entries = [x for x in entries if not x.stream.endswith('comments')]

  per_page = per_page - (len(inbox) - len(entries))
  entries, more = util.page_entries(request, entries, per_page)

  stream_keys = [e.stream for e in entries]
  actor_streams = api.stream_get_actor(request.user, view.nick)
  stream_keys += [s.key().name() for s in actor_streams]
  streams = api.stream_get_streams(request.user, stream_keys)

  contact_nicks = api.actor_get_contacts(request.user, 
                                         view.nick, 
                                         limit=CONTACTS_PER_PAGE)
  actor_nicks = (contact_nicks +
                 [view.nick] +
                 [s.owner for s in streams.values()] +
                 [e.owner for e in entries] +
                 [e.actor for e in entries])
  actors = api.actor_get_actors(request.user, actor_nicks)

  # here comes lots of munging data into shape
  # clear deleted contacts
  contacts = [actors[x] for x in contact_nicks if actors[x]]
  streams = display.prep_stream_dict(streams, actors)
  entries = display.prep_entry_list(entries, streams, actors)

  # END inbox generation chaos
  
  # Check for unconfirmed emails
  unconfirmeds = api.activation_get_actor_email(request.user, view.nick)
  if unconfirmeds:
    unconfirmed_email = unconfirmeds[0].content

  # If not logged in, cannot write
  is_owner = False
  try:
    is_owner = view.nick == request.user.nick
  except:
    pass
  presence = api.presence_get(request.user, view.nick)

  # for sidebar streams
  view_streams = dict([(x.key().name(), streams[x.key().name()])
                       for x in actor_streams])

  # for sidebar_contacts
  contacts_count = view.extra.get('contact_count', 0)
  contacts_more = contacts_count > CONTACTS_PER_PAGE

  # Config for the template
  green_top = True
  sidebar_green_top = True
  selectable_icons = display.SELECTABLE_ICONS

  area = 'home'

  # TODO(tyler/termie):  This conflicts with the global settings import.
  # Also, this seems fishy.  Do none of the settings.* items work in templates?
  import settings
  
  c = template.RequestContext(request, locals())

  if format == 'html':
    t = loader.get_template('actor/templates/overview.html')
    return http.HttpResponse(t.render(c))
  elif format == 'json':
    t = loader.get_template('actor/templates/overview.json')
    r = util.HttpJsonResponse(t.render(c), request)
    return r
  elif format == 'atom':
    t = loader.get_template('actor/templates/overview.atom')
    r = util.HttpAtomResponse(t.render(c), request)
    return r
  elif format == 'rss':
    t = loader.get_template('actor/templates/overview.rss')
    r = util.HttpRssResponse(t.render(c), request)
    return r
    

# The following section heavily commented for use in
# http://code.google.com/p/jaikuengine/wiki/ControllerBestPractices

# Views are named based on their app and whenever possible the url they are
# accessible at, in this case for legacy compatibility there is a requirement
# for using the word "presence" in the url but it is not very closely
# applicable to what the controller does so we have diverged

# All views are passed a `request`, it should always be named request

# Everything in the `actor` app needs to know which actor it is acting
# on, hence the `nick` argument.

# Most views should be presentable in 3-4 formats, 'html' being the default,
# other common formats are JSON, XML, ATOM
@alternate_nick
def actor_item(request, nick=None, item=None, format='html'):
  # The nick passed in the url looks ugly with the escaped @ in it and is
  # generally just shorter if we only use the lead part of the nick
  # however the entire system expects full nicks so we should expand this
  # as soon as possible
  nick = clean.nick(nick)

  # Most pages have the concept of a viewer and an actor being viewed,
  # in all cases the viewer is `request.user` and the actor being viewed
  # should be named `view`
  view = api.actor_lookup_nick(request.user, nick)

  if not view:
    raise exception.UserDoesNotExistError(nick, request.user)

  # With very few exceptions, whenever we are referring to a an
  # instance that is an entity from the datastore we append `_ref`
  # to the variable name to distinguish it from the variable that
  # is simply a string identifier.
  # In the code below `stream_ref` and `entry_ref` are both entity
  # references, while `entry` is simply the string key_name of an entry
  stream_ref = api.stream_get_presence(request.user, view.nick)
  if not stream_ref:
    raise http.Http404()

  if item == 'last':
    entry_ref = api.entry_get_last(request.user, stream_ref.keyname())
    return http.HttpResponseRedirect(entry_ref.url())
  else:
    entry = '%s/%s' % (stream_ref.key().name(), item)
    entry_ref = api.entry_get_safe(request.user, entry)

  # Most api calls will return None if the entity being looked up does
  # not exist so we usually want to verify the return values
  if not entry_ref:
    raise http.Http404()


  # When handling user actions the following pattern more or less applies
  # if 'parameter_unique_to_action' in request.(POST|GET|REQUEST):
  #   try:
  #     validate.nonce(request, 'nonce_action')
  #     validate.anything_else_that_is_related_to_ui_rather_than_call()
  #
  #     local_variable = request.(POST|GET|REQUEST).get('request_arg')
  #     # or
  #     params = util.query_dict_to_keywords(request.(POST|GET|REQUEST))
  #
  #     # Our goal is to have most of the logic for any action translate
  #     # directly into an api call on behalf of the requesting user
  #     # such that the api call is responsible for validating all input
  #     # and raising any applicable errors
  #     result = api.some_api_method(request.user,
  #                                  method_variable=local_variable,
  #                                  ...)
  #     # or
  #     result = api.some_api_method(request.user,  **params)
  #
  #     # All actions should issue a redirect with a success message
  #     return util.RedirectFlash('some_url', 'some success message')
  #   except:
  #     exception.handle_exception(request)
  #
  # When an exception occurs we expect the rest of the page to be able
  # to be processed normally as if no action had been taken, the error
  # handling section of the template should display the errors caught
  # by the exception.handle_exception() call
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

  comments = api.entry_get_comments(request.user, entry_ref.key().name())

  # To minimize the number of lookups to the datastore once we know
  # all the data we will be displaying on a page we attempt to make
  # a list of all the actors associated with that data so that we can
  # fetch them all at once
  actor_nicks = [entry_ref.owner, entry_ref.actor] + [c.actor for c in comments]
  actors = api.actor_get_actors(request.user, actor_nicks)
  
  # Creates a copy of actors with lowercase keys (Django #6904: template filter
  # dictsort sorts case sensitive), excluding the currently logged in user.
  participants = {}
  for k, v in actors.iteritems():
    if (v and
        not (hasattr(request.user, 'nick') and request.user.nick == v.nick)):
      participants[k.lower()] = v

  # Due to restrictions on Django's templating language most of the time
  # we will have to take an additional step of preparing all of our data
  # for display, this usually translates to attaching references to
  # actor or stream entities.
  # Functions that handle this preparation should be added to the
  # common.display module
  entry = display.prep_entry(entry_ref,
                             {stream_ref.key().name(): stream_ref}, actors)
  comments = display.prep_comment_list(comments, actors)

  # Additionally, to minimize more logic in the templates some variables
  # can be defined to configure the output, these are usually template specific
  # though some are common variables for anything that inherits from the
  # base templates
  green_top = True
  sidebar_green_top = True

  # The quickest way to make sure we are getting all of the things we care
  # about passed to the template without the temptation of making last minute
  # changes is just to pass `locals()` to the template context
  c = template.RequestContext(request, locals())

  # Ideally this is all that should be necessary to add additional output
  # formats, in practice it is yet to be seen whether additional data
  # preparation will be necessary before outputting in JSON or ATOM formats
  if format == 'html':

    # We always use the full path to the template to prevent naming conflicts
    # and difficult searches.
    t = loader.get_template('actor/templates/item.html')
    return http.HttpResponse(t.render(c))

  elif format == 'json':
    t = loader.get_template('actor/templates/item.json')
    r = http.HttpResponse(t.render(c))
    r['Content-type'] = 'text/javascript'
    return r


@alternate_nick
def actor_contacts(request, nick=None, format='html'):
  nick = clean.nick(nick)

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

  contact_nicks = api.actor_get_contacts(request.user, view.nick,
                                         limit=(per_page + 1), offset=offset)
  actor_nicks = contact_nicks
  actors = api.actor_get_actors(request.user, actor_nicks)
  # clear deleted actors
  actors = dict([(k, v) for k, v in actors.iteritems() if v])
  per_page = per_page - (len(contact_nicks) - len(actors))

  # TODO(termie): incorporate this into paging so we only fetch the range
  #               on this page
  # add some extra info so we can let the user do contextual actions
  # on these homeboys
  if request.user and request.user.nick == view.nick:
    # looking at self, find out who of these people follow me so
    # I can highlight them
    for actor in actors:
      if api.actor_is_follower(request.user, view.nick, actor):
        actors[actor].my_follower = True
      actors[actor].my_contact = True
      actors[actor].rel = 'contact'
    whose = 'Your'
  elif request.user:
    my_contacts_nicks = api.actor_get_contacts(request.user, request.user.nick)
    for f in my_contacts_nicks:
      try:
        actors[f].my_contact = True
      except:
        pass
    for x in actors:
      actors[x].rel = 'contact'
    whose = "%s's" % view.display_nick()

  # here comes lots of munging data into shape
  actor_tiles = [actors[x] for x in contact_nicks if x in actors]

  actor_tiles_count = view.extra.get('contact_count', 0)
  actor_tiles, actor_tiles_more = util.page_actors(request,
                                                   actor_tiles,
                                                   per_page)

  area = 'people'

  c = template.RequestContext(request, locals())

  if format == 'html':
    t = loader.get_template('actor/templates/contacts.html')
    return http.HttpResponse(t.render(c))
  elif format == 'json':
    t = loader.get_template('actor/templates/contacts.json')
    r = http.HttpResponse(t.render(c))
    r['Content-type'] = 'text/javascript'
    return r



@alternate_nick
def actor_followers(request, nick=None, format='html'):
  nick = clean.nick(nick)

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

  follower_nicks = api.actor_get_followers(request.user,
                                           view.nick,
                                           limit=(per_page + 1),
                                           offset=offset)
  actor_nicks = follower_nicks
  actors = api.actor_get_actors(request.user, actor_nicks)
  # clear deleted actors
  actors = dict([(k, v) for k, v in actors.iteritems() if v])
  per_page = per_page - (len(follower_nicks) - len(actors))

  # TODO(termie): incorporate this into paging so we only fetch the range
  #               on this page
  # add some extra info so we can let the user do contextual actions
  # on these homeboys
  if request.user and request.user.nick == view.nick:
    for actor in actors:
      if api.actor_is_contact(request.user, view.nick, actor):
        actors[actor].my_contact = True
    whose = 'Your'
  else:
    whose = "%s's" % view.display_nick()

  # here comes lots of munging data into shape
  actor_tiles = [actors[x] for x in follower_nicks if x in actors]

  actor_tiles_count = view.extra.get('follower_count', 0)
  actor_tiles, actor_tiles_more = util.page_actors(request,
                                                   actor_tiles,
                                                   per_page)

  area = 'people'

  c = template.RequestContext(request, locals())

  if format == 'html':
    t = loader.get_template('actor/templates/followers.html')
    return http.HttpResponse(t.render(c))

@alternate_nick
def actor_settings(request, nick, page='index'):
  """ just a static page that links to the rest"""
  nick = clean.nick(nick)

  view = api.actor_lookup_nick(api.ROOT, nick)
  if not api.actor_owns_actor(request.user, view):
    raise exception.ApiException(exception.PRIVACY_ERROR,
                                 'Operation not allowed')

  handled = common_views.handle_view_action(
      request,
      {
        'activation_activate_mobile': view.url('/settings/mobile'),
        'activation_request_email': view.url('/settings/email'),
        'activation_request_mobile': view.url('/settings/mobile'),
        'settings_change_notify': view.url('/settings/notifications'),
        'settings_change_privacy': request.path,
        'settings_update_account': view.url('/settings/profile'),
        'actor_remove': '/logout',
        #'oauth_remove_consumer': request.path,
        #'oauth_remove_access_token': request.path
      }
  )
  if handled:
    return handled



  # TODO(tyler/termie):  This conflicts with the global settings import.
  # Also, this seems fishy.  Do none of the settings.* items work in templates?
  import settings

  # TODO(tyler): Merge this into handle_view_action, if possible
  if 'password' in request.POST:
    try:
      validate.nonce(request, 'change_password')

      password = request.POST.get('password', '')
      confirm = request.POST.get('confirm', '')

      validate.password_and_confirm(password, confirm, field = 'password')

      api.settings_change_password(request.user, view.nick, password)
      response = util.RedirectFlash(view.url() + '/settings/password',
                                    'Password updated')
      request.user.password = util.hash_password(request.user.nick, password)
      # TODO(mikie): change when cookie-auth is changed
      user.set_user_cookie(response, request.user)
      return response
    except:
      exception.handle_exception(request)

  if page == 'feeds':
    try:
      if not settings.FEEDS_ENABLED:
        raise exception.DisabledFeatureError('Feeds are currently disabled')
    except:
      exception.handle_exception(request)

  if page == 'photo':
    redirect_to = view.url() + '/settings/photo'
    handled = common_views.common_photo_upload(request, redirect_to)
    if handled:
      return handled


  area = 'settings'
  full_page = page.capitalize()

  if page == 'mobile':
    full_page = 'Mobile Number'

    mobile = api.mobile_get_actor(request.user, view.nick)
    sms_notify = view.extra.get('sms_notify', False)
    
  elif page == 'im':
    full_page = 'IM Address'
    im_address = api.im_get_actor(request.user, view.nick)
    im_notify = view.extra.get('im_notify', False)
  elif page == 'index':
    email = api.email_get_actor(request.user, view.nick)
    email_notify = view.extra.get('email_notify', False)
    im_address = api.im_get_actor(request.user, view.nick)
    im_notify = view.extra.get('im_notify', False)
  elif page == 'feeds':
    full_page = 'Web Feeds'
  elif page == 'email':
    full_page = 'Email Address'
    email_notify = view.extra.get('email_notify', False)

    # check if we already have an email
    email = api.email_get_actor(request.user, view.nick) 

    # otherwise look for an unconfirmed one
    if not email:
      unconfirmeds = api.activation_get_actor_email(api.ROOT, view.nick)
      if unconfirmeds:
        unconfirmed_email = unconfirmeds[0].content

  elif page == 'design':
    handled = common_views.common_design_update(request, view.nick)
    if handled:
      return handled
    full_page = 'Look and Feel'

  elif page == 'notifications':
    email = api.email_get_actor(request.user, view.nick)
    email_notify = view.extra.get('email_notify', False)
    im_address = api.im_get_actor(request.user, view.nick)
    im_notify = view.extra.get('im_notify', False)
    mobile = api.mobile_get_actor(request.user, request.user.nick)
    sms_notify = view.extra.get('sms_notify', False)

    sms_confirm = sms_notify and not view.extra.get('sms_confirmed', False)
    # TODO(termie): remove this once we can actually receive sms
    sms_confirm = False
  elif page == 'profile':
    # check if we already have an email
    email = api.email_get_actor(request.user, view.nick) 

    # otherwise look for an unconfirmed one
    if not email:
      unconfirmeds = api.activation_get_actor_email(api.ROOT, view.nick)
      if unconfirmeds:
        unconfirmed_email = unconfirmeds[0].content

  elif page == 'photo':
    avatars = display.DEFAULT_AVATARS
    small_photos = api.image_get_all_keys(request.user, view.nick, size='f')

    # TODO(tyler): Fix this avatar nonsense!
    own_photos = [{
        'path' : small_photo.key().name(),
        'name' : small_photo.key().name()[len('image/'):-len('_f.jpg')],
      } for small_photo in small_photos
    ]

  elif page == 'privacy':
    PRIVACY_PUBLIC = api.PRIVACY_PUBLIC
    PRIVACY_CONTACTS = api.PRIVACY_CONTACTS
  elif page == 'jsbadge':
    full_page = 'Javascript Badges'
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

  elif page in ['password', 'delete']:
    # Catch for remaining pages before we generate a 404.
    pass

  else:
    return common_views.common_404(request)

  # rendering
  c = template.RequestContext(request, locals())
  t = loader.get_template('actor/templates/settings_%s.html' % page)
  return http.HttpResponse(t.render(c))

def actor_settings_redirect(request):
  if not request.user:
    return http.HttpResponseRedirect(
        '/login?redirect_to=%s' % request.get_full_path())
  nick = clean.nick(request.user.nick)
  view = api.actor_lookup_nick(request.user, nick)
  return http.HttpResponseRedirect(view.url() + request.get_full_path())
