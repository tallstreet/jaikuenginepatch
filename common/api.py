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

import random
import re
import datetime
import logging

from cleanliness import cleaner

from django import template
from django.conf import settings

from google.appengine.ext import db
from google.appengine.api import urlfetch
from google.appengine.api import images

from common.models import Stream, StreamEntry, InboxEntry, Actor, Relation
from common.models import Subscription, Invite, OAuthConsumer, OAuthRequestToken
from common.models import OAuthAccessToken, Image, Activation
from common.models import KeyValue, Presence
from common.models import AbuseReport
from common.models import Task
from common.models import PRIVACY_PRIVATE, PRIVACY_CONTACTS, PRIVACY_PUBLIC

from common import clean
from common import clock
from common import context_processors
from common import exception
from common import imageutil
from common import mail
from common import memcache
from common import models
from common import normalize
from common import patterns
from common import properties
from common import throttle
from common import util
from common import validate
from common.protocol import sms
from common.protocol import xmpp

NO_ACCESS = 'none'
READ_ACCESS = 'read'
WRITE_ACCESS = 'write'
DELETE_ACCESS = 'delete'
ADMIN_ACCESS = 'admin'

ACCESS_LEVELS = [NO_ACCESS,
                 READ_ACCESS,
                 WRITE_ACCESS,
                 DELETE_ACCESS,
                 ADMIN_ACCESS]

ROOT = Actor(nick=settings.ROOT_NICK, type='user')
ROOT.access_level = ADMIN_ACCESS

# Max length of a message. Conciseness is a virtue.
# UIs should prevent posting longer messages. API will truncate
# posts longer than this.
MAX_POST_LENGTH = 140

# How many contacts we are willing to count to update an actor's
# contact_count or follower_count properties
CONTACT_COUNT_THRESHOLD = 100

# Maximum number of channels a user is allowed to admin at a time
MAX_ADMINS_PER_ACTOR = 48

# The default length of a task's visibility lock in seconds
DEFAULT_TASK_EXPIRE = 10

# The maximum number of followers to process per task iteration of inboxes
MAX_FOLLOWERS_PER_INBOX = 100

MAX_NOTIFICATIONS_PER_TASK = 100
# The maximum number of followers we can notify per task iteration

# The first notification type to handle
FIRST_NOTIFICATION_TYPE = 'im'

AVATAR_IMAGE_SIZES = { 'u': (30, 30),
                       't': (50, 50),
                       'f': (60, 60),
                       'm': (175, 175),
                       }

# Wrap utcnow so that it can be mocked in tests. We can't replace the function
# in the datetime module because it's an extension, not a python module.
utcnow = lambda: clock.utcnow()

RE_NS_DOMAIN = settings.NS_DOMAIN.replace('.', r'\.')

channel_post_re = re.compile(
    r'^(?P<channel>#[a-zA-Z][a-zA-Z0-9]{%d,%d}(?:@%s)?)'
    r':?\s+' # separator
    r'(?P<message>.*)' # message
    % (clean.NICK_MIN_LENGTH - 1, clean.NICK_MAX_LENGTH - 1, RE_NS_DOMAIN)
    )

smashed_title_re = re.compile(r'(?:(?:^|\s+)(\w))')

# little helper for code reuse
def _item_from_args_kw(f, allowed, args, kw):
  """ attempt to fetch an identifying key from the list of args and kw,
      
      allowed - list of allowable kw key names
      args - list of args
      kw - dict of key-value args
  """
  x = None
  for possible in allowed:
    x = kw.get(possible)
    if x:
      break

  if not x:
    x = args[0]
  return f(ROOT, x)

def _actor_from_args_kw(allowed, args, kw):
  return _item_from_args_kw(actor_get, allowed, args, kw)

def _entry_from_args_kw(allowed, args, kw):
  return _item_from_args_kw(entry_get, allowed, args, kw)

def _stream_from_args_kw(allowed, args, kw):
  return _item_from_args_kw(stream_get, allowed, args, kw)


# Better Access Control
def has_access(actor_ref, access_level):
  if not actor_ref:
    return False

  # TODO(termie): I don't really like that the default access is full access
  #               but changing that in any way makes testing much more
  #               verbose, requiring us to set access levels every time we
  #               fetch an actor to use. Some work can probably be done to
  #               put the site into some testing mode where the default
  #               access level for testing is DELETE_ACCESS at which point
  #               this can become NO_ACCESS again
  test_access = getattr(actor_ref, 'access_level', DELETE_ACCESS)
  if ACCESS_LEVELS.index(access_level) <= ACCESS_LEVELS.index(test_access):
    return True
  return False

def actor_owns_actor(actor_ref, other_ref):
  if not actor_ref or not other_ref:
    return False

  # actors own themselves
  if actor_ref.nick == other_ref.nick:
    return True
  
  # admins own anything
  if has_access(actor_ref, ADMIN_ACCESS):
    return True
  
  # if this is a channel, it is owned by its admins
  if (other_ref.is_channel() 
      and channel_has_admin(ROOT, other_ref.nick, actor_ref.nick)
      ):
    return True

  # well, we tried.
  return False  

def actor_owns_stream(actor_ref, stream_ref):
  if not stream_ref:
    return False

  # streams are owned by whoever owns the actor that owns a stream
  stream_owner_ref = actor_get_safe(ROOT, stream_ref.owner)
  if not stream_owner_ref:
    # this stream has no owner, the owner is deleted, something like that
    # we shouldn't ever really be getting here
    return False
  return actor_owns_actor(actor_ref, stream_owner_ref)

def actor_owns_entry(actor_ref, entry_ref):
  if not entry_ref:
    return False

  # owned by whoever owns the actor whom wrote the entry
  entry_actor_ref = actor_get_safe(ROOT, entry_ref.actor)
  if not entry_actor_ref:
    # this entry has no author, the author is deleted, something like that
    # we shouldn't ever really be getting here
    return False
  if actor_owns_actor(actor_ref, entry_actor_ref):
    return True

  # owned by whoever owns the actor whom owns the stream the entry is in
  entry_owner_ref = actor_get_safe(ROOT, entry_ref.owner)
  if not entry_owner_ref:
    # this stream has no owner, the owner is deleted, something like that
    # we shouldn't ever really be getting here
    return False
  if actor_owns_actor(actor_ref, entry_owner_ref):
    return True

  # if this is a comment we have to check for the entry as well
  # this is recursive, but should be okay since we can't comment on comments
  if entry_ref.entry:
    entry_parent_ref = entry_get_safe(ROOT, entry_ref.entry)
    if actor_owns_entry(actor_ref, entry_parent_ref):
      return True

  return False

def actor_can_view_actor(actor_ref, other_ref):
  """ actor_ref can view other_ref """
  if not other_ref:
    return False

  # if other is public
  if other_ref.is_public():
    return True

  # if we're not public we better have an actor_ref
  if not actor_ref:
    return False

  # if we are the owner
  if actor_owns_actor(actor_ref, other_ref):
    return True

  # other_ref is restricted
  if other_ref.is_restricted():
    # and we are a contact
    if (not other_ref.is_channel() 
        and actor_has_contact(ROOT, other_ref.nick, actor_ref.nick)
        ):
      return True
    # is a channel and we are a member (admin covered above by owner)
    if (other_ref.is_channel()
        and channel_has_member(ROOT, other_ref.nick, actor_ref.nick)
        ):
      return True

  return False

def actor_can_view_stream(actor_ref, stream_ref):
  if not stream_ref:
    return False

  # if stream is public
  if stream_ref.is_public():
    return True

  if actor_owns_stream(actor_ref, stream_ref):
    return True

  if stream_ref.is_restricted():
    stream_owner_ref = actor_get_safe(ROOT, stream_ref.owner)
    if actor_can_view_actor(actor_ref, stream_owner_ref):
      return True

  # special case the comments stream, because it is private but comments take
  # on the privacy of the entries they are on
  # this allows anybody to see that the comments stream exists while giving
  # no specific access to any actual comments held therein
  # unfortunately some of the imported data has type == 'comment' and some
  # type == 'comments'.
  if stream_ref.type == 'comment' or stream_ref.type == 'comments':
    return True

  return False

def actor_can_view_entry(actor_ref, entry_ref):
  if not entry_ref:
    return False

  if actor_owns_entry(actor_ref, entry_ref):
    return True

  # if not a comment inherit the visibility of the stream
  if not entry_ref.entry:
    stream_ref = stream_get_safe(ROOT, entry_ref.stream)
    if actor_can_view_stream(actor_ref, stream_ref):
      return True

  # if this is a comment we want to check the parent entry's stream
  if entry_ref.entry:
    entry_parent_ref = entry_get_safe(ROOT, entry_ref.entry)
    if actor_can_view_entry(actor_ref, entry_parent_ref):
      return True

  return False

# Better Access Control Decorators
def access_required(access_level):
  def _decorator(f):
    def _wrap(api_user, *args, **kw):
      if not has_access(api_user, access_level):
        raise exception.ApiException(
            exception.PERMISSION_ERROR,
            'You need %s access or above to use this method' % access_level)
      return f(api_user, *args, **kw)
    _wrap.func_name = f.func_name
    _wrap.meta = append_meta(f, '%s_required' % access_level)
    return _wrap
  return _decorator

write_required = access_required(WRITE_ACCESS)
delete_required = access_required(DELETE_ACCESS)
admin_required = access_required(ADMIN_ACCESS)

def append_meta(f, key, value=None):
  if not hasattr(f, 'meta'):
    f.meta = []
  f.meta.append((key, value))
  return f.meta

def owner_required(f):
  def _wrap(api_user, *args, **kw):
    actor_ref = _actor_from_args_kw(['nick', 'owner', 'channel'], args, kw)

    if not actor_owns_actor(api_user, actor_ref):
      # TODO(termie): pretty obtuse message...
      raise exception.ApiException(exception.PRIVACY_ERROR,
                                   'Operation not allowed')

    # everything checks out, call the original function
    return f(api_user, *args, **kw)

  _wrap.func_name = f.func_name
  _wrap.meta = append_meta(f, 'owner_required')
  return _wrap

def owner_required_by_target(f):
  def _wrap(api_user, *args, **kw):
    # TODO(termie): I don't really like that this looks at the second
    #               arg, it feels hacky.
    target = kw.get('target')
    if target is None:
      target = args[1]
    nick = util.get_user_from_topic(target)

    actor_ref = actor_get_safe(ROOT, nick)
    if not actor_ref:
      raise exception.ApiException(0x00, 'Actor does not exist: %s' % nick)

    if not actor_owns_actor(api_user, actor_ref):
      # TODO(termie): pretty obtuse message...
      raise exception.ApiException(exception.PRIVACY_ERROR,
                                   'Operation not allowed')

    # everything checks out, call the original function
    return f(api_user, *args, **kw)

  _wrap.func_name = f.func_name
  _wrap.meta = append_meta(f, 'owner_required_by_target')
  return _wrap

def owner_required_by_entry(f):
  def _wrap(api_user, *args, **kw):
    entry_ref = _entry_from_args_kw(['entry', 'comment'], args, kw)

    if not actor_owns_entry(api_user, entry_ref):
      # TODO(termie): pretty obtuse message...
      raise exception.ApiException(exception.PRIVACY_ERROR,
                                   'Operation not allowed')

    # everything checks out, call the original function
    return f(api_user, *args, **kw)

  _wrap.func_name = f.func_name
  _wrap.meta = append_meta(f, 'owner_required_by_entry')
  return _wrap

# TODO(termie): this could probably have a better name
def viewable_required(f):
  """ assert that the calling user is allowed to view this """
  def _wrap(api_user, *args, **kw):
    if not has_access(api_user, ADMIN_ACCESS):
      actor_ref = _actor_from_args_kw(['channel', 'nick', 'owner'], args, kw)
      
      if not actor_can_view_actor(api_user, actor_ref):
        # TODO(termie): pretty obtuse message...
        raise exception.ApiException(exception.PRIVACY_ERROR,
                                     'Operation not allowed')

    # everything checks out, call the original function
    return f(api_user, *args, **kw)

  _wrap.func_name = f.func_name
  _wrap.meta = append_meta(f, 'viewable_required')
  return _wrap  

def viewable_required_by_entry(f):
  def _wrap(api_user, *args, **kw):
    if not has_access(api_user, ADMIN_ACCESS):
      entry_ref = _entry_from_args_kw(['entry', 'comment'], args, kw)
      if not actor_can_view_entry(api_user, entry_ref):
        # TODO(termie): pretty obtuse message...
        raise exception.ApiException(exception.PRIVACY_ERROR,
                                     'Operation not allowed')

    # everything checks out, call the original function
    return f(api_user, *args, **kw)

  _wrap.func_name = f.func_name
  _wrap.meta = append_meta(f, 'viewable_required_by_entry')
  return _wrap  

def viewable_required_by_stream(f):
  def _wrap(api_user, *args, **kw):
    if not has_access(api_user, ADMIN_ACCESS):
      stream_ref = _stream_from_args_kw(['stream'], args, kw)
      if not actor_can_view_stream(api_user, stream_ref):
        # TODO(termie): pretty obtuse message...
        raise exception.ApiException(exception.PRIVACY_ERROR,
                                     'Operation not allowed')

    # everything checks out, call the original function
    return f(api_user, *args, **kw)

  _wrap.func_name = f.func_name
  _wrap.meta = append_meta(f, 'viewable_required_by_stream')
  return _wrap 

public_owner_or_contact = viewable_required
public_owner_or_member = viewable_required
public_owner_or_contact_by_entry = viewable_required_by_entry
public_owner_or_contact_by_stream = viewable_required_by_stream

# Throttling

def throttled(**decokw):
  def _decorator(f):
    def _wrap(api_user, *args, **kw):
      throttle.throttle(api_user, f.func_name, **decokw)
      return f(api_user, *args, **kw)
    _wrap.func_name = f.func_name
    _wrap.meta = append_meta(f, 'throttled', decokw)
    return _wrap
  return _decorator


def catch_image_error(f):
  """Decorator that catches app engine image errors and translates them to
  ApiException"""
  def _wrap(*args, **kw):
    return exception.handle_image_error(f, *args, **kw)
  _wrap.func_name = f.func_name
  _wrap.meta = append_meta(f, 'handle_image_error')
  return _wrap


# CALLS

#######
#######
#######

@admin_required
def abuse_get_entry(api_user, entry):
  entry_ref = entry_get(api_user, entry)

  key_name = AbuseReport.key_from(entry=entry_ref.keyname())
  abuse_ref = AbuseReport.get_by_key_name(key_name)
  return abuse_ref

@write_required
@owner_required  # this is only over the reporter, not the entry
def abuse_report_entry(api_user, nick, entry):
  """ a user report of an entry as spam
  
  should probably do something interesting but for now we're just 
  going to keep track of it
  """

  entry_ref = entry_get(api_user, entry)
  reporter_ref = actor_get(api_user, nick)

  # XXX begin transaction
  abuse_ref = abuse_get_entry(ROOT, entry)
  if abuse_ref:
    abuse_ref.reports = list(set(abuse_ref.reports + [reporter_ref.nick]))
    abuse_ref.count = len(abuse_ref.reports)
  else:
    params = {'entry': entry_ref.keyname(),
              'actor': entry_ref.actor,
              'count': 1, 
              'reports': [reporter_ref.nick],
              }
    abuse_ref = AbuseReport(**params)
  abuse_ref.put()
  
  # TODO(termie): if we cross some sort of threshold we should probably
  #               mark a user as an abuser and prevent them from posting
  

  # XXX end transaction
  
  return abuse_ref


#######
#######
#######

@owner_required
def activation_activate_email(api_user, nick, code):
  activation_ref = activation_get_code(api_user, nick, 'email', code)
  if not activation_ref:
    raise exception.ApiException(0x00, 'Invalid code')

  existing_ref = actor_lookup_email(ROOT, activation_ref.content)
  if existing_ref:
    raise exception.ApiException(
        0x00, 'That email address has already been activated')

  # XXX begin transaction
  actor_ref = actor_get(api_user, nick)

  relation_ref = email_associate(ROOT, actor_ref.nick, activation_ref.content)
  activation_ref.delete()

  # XXX end transaction
  return relation_ref

@owner_required
def activation_activate_mobile(api_user, nick, code):
  activation_ref = activation_get_code(api_user, nick, 'mobile', code)
  if not activation_ref:
    raise exception.ApiException(0x00, 'Invalid code')

  existing_ref = actor_lookup_mobile(ROOT, activation_ref.content)
  if existing_ref:
    raise exception.ApiException(
        0x00, 'That mobile number has already been activated')

  # XXX begin transaction
  actor_ref = actor_get(api_user, nick)

  relation_ref = mobile_associate(ROOT, actor_ref.nick, activation_ref.content)
  activation_ref.delete()

  # XXX end transaction
  return relation_ref

@admin_required
def activation_create(api_user, nick, type, content):
  activation_ref = Activation(
      actor=nick,
      content=content,
      code=util.generate_uuid()[:4],
      type=type,
      )
  activation_ref.put()
  return activation_ref

@admin_required
def activation_create_email(api_user, nick, email):
  validate.email(email)
  validate.email_not_activated(email)
  return activation_create(api_user, nick, 'email', email)

@admin_required
def activation_create_mobile(api_user, nick, mobile):
  clean.mobile(mobile)

  if actor_lookup_mobile(api_user, mobile):
    raise exception.ApiException(0x00, 'Mobile number already in use')

  return activation_create(api_user, nick, 'mobile', mobile)

@admin_required
def activation_get(api_user, nick, type, content):
  key_name = Activation.key_from(actor=nick, type=type, content=content)
  return Activation.get_by_key_name(key_name)

@owner_required
def activation_get_actor_email(api_user, nick):
  query = Activation.gql('WHERE type = :1 AND actor = :2',
                         'email',
                         nick)

  activations = list(query.run())
  return activations

def activation_get_by_email(api_user, email):
  query = Activation.gql('WHERE type = :1 AND content = :2',
                         'email',
                         email)

  activations = list(query.run())
  return activations

@owner_required
def activation_get_actor_mobile(api_user, nick):
  query = Activation.gql('WHERE type = :1 AND actor = :2',
                         'mobile',
                         nick)

  activations = list(query.run())
  return activations

@owner_required
def activation_get_code(api_user, nick, type, code):
  query = Activation.gql('WHERE type = :1 AND actor = :2 AND code = :3',
                         type,
                         nick,
                         code)

  activation_ref = query.get()
  return activation_ref

@admin_required
def activation_get_email(api_user, nick, email):
  return activation_get(api_user, nick, 'email', email)

@admin_required
def activation_get_mobile(api_user, nick, mobile):
  return activation_get(api_user, nick, 'mobile', mobile)

@throttled(minute=2, hour=5, day=10)
@owner_required
def activation_request_email(api_user, nick, email):
  nick = clean.nick(nick)
  email = normalize.email(email)
  validate.email(email)

  actor_ref = actor_get(api_user, nick)

  # can request an activation for an email that already exists
  existing_ref = actor_lookup_email(ROOT, email)
  if existing_ref:
    raise exception.ApiException(0, "That email address is already in use")

  # check whether they've already tried to activate this email
  # if they have send them the same code
  # TODO(tyler): Abstract into activation_get_or_create
  activation_ref = activation_get_email(ROOT, nick, email)
  if not activation_ref:
    old_activations = activation_get_actor_email(ROOT, nick)
    for old_activation_ref in old_activations:
      old_activation_ref.delete()

    activation_ref = activation_create_email(ROOT, nick, email)

  subject, message, html_message = mail.email_confirmation_message(api_user,
      activation_ref.code)
  email_send(ROOT, email, subject, message, html_message=html_message)
  return activation_ref

@throttled(minute=2, hour=5, day=10)
@owner_required
def activation_request_mobile(api_user, nick, mobile):
  mobile = clean.mobile(mobile)

  actor_ref = actor_get(api_user, nick)

  # can request an activation for an email that already exists
  existing_ref = actor_lookup_mobile(ROOT, mobile)
  if existing_ref:
    raise exception.ApiException(0, "That mobile number is already in use")

  # check whether they've already tried to activate this email
  # if they have send them the same code
  # TODO(tyler): Abstract into activation_get_or_create
  activation_ref = activation_get_mobile(ROOT, nick, mobile)
  if not activation_ref:
    old_activations = activation_get_actor_mobile(ROOT, nick)
    for old_activation_ref in old_activations:
      old_activation_ref.delete()

    activation_ref = activation_create_mobile(ROOT, nick, mobile)

  message = "Your activation code is %s" % activation_ref.code
  sms_send(ROOT, api_user.nick, mobile, message)
  return activation_ref


#######
#######
#######
@throttled(minute=50, hour=200, day=300, month=500)
@write_required
@owner_required
def actor_add_contact(api_user, owner, target):
  """Adds a one-way relationshp of type 'contact' from owner to target.

  May be called multiple times for the same owner and target and should
  always ensure the same ending conditions.

  PARAMS:
    * owner - the nick of the follower
    * target - the nick of the followed

  RETURNS: rel_ref

  A relation_ref has the following attributes:
    * owner: nick of the relationship owner
    * relation: the type of the relation; always 'contact' in this case
    * target: nick of the actor related to the owner

  EXAMPLE API RETURN:

  ::

    {'status': 'ok',
     'rv': {'relation': {'owner': 'test@example.com',
                         'relation': 'contact',
                         'target': 'root@example.com'
                         }
            }
     }


  """
  owner = clean.nick(owner)
  target = clean.nick(target)

  owner_ref = actor_get(api_user, owner)
  target_ref = actor_get(api_user, target)

  if not owner_ref:
    raise exception.ApiException(0, 'Actor does not exist: %s' % owner)

  if not target_ref:
    raise exception.ApiException(0, 'Actor does not exist: %s' % target)

  existing_rel_ref = actor_has_contact(ROOT, owner, target)

  # XXX start transaction

  if not existing_rel_ref:
    # Add the relationship
    relation = 'contact'
    rel_ref = Relation(owner=owner_ref.nick, relation=relation,
                       target=target_ref.nick,
                       )
    rel_ref.put()
  else:
    rel_ref = existing_rel_ref

  # We're doing some fancy stuff here to keep the counts very precise
  # for people with < CONTACT_COUNT_THRESHOLD contacts or followers,
  # but less important for those with more than that when a datastore
  # error has occurred between creating the relationship and adding the count

  if existing_rel_ref:
    if owner_ref.extra.get('contact_count', 0) < CONTACT_COUNT_THRESHOLD:
      # using ROOT because this is an admin only function and doesn't
      # the return value is not given to the calling user
      contact_count = actor_count_contacts(ROOT, owner_ref.nick)
      owner_ref.extra['contact_count'] = contact_count
    if owner_ref.extra.get('follower_count', 0) < CONTACT_COUNT_THRESHOLD:
      # using ROOT because this is an admin only function and doesn't
      # the return value is not given to the calling user
      follower_count = actor_count_followers(ROOT, target_ref.nick)
      target_ref.extra['follower_count'] = follower_count
  else:
    # Increase the counts for each
    owner_ref.extra.setdefault('contact_count', 0)
    owner_ref.extra['contact_count'] += 1
    owner_ref.put()

    target_ref.extra.setdefault('follower_count', 0)
    target_ref.extra['follower_count'] += 1
    target_ref.put()

  # Subscribe owner to all of target's streams
  streams = stream_get_actor(ROOT, target)
  for stream in streams:
    sub = subscription_request(api_user,
                               topic=stream.key().name(),
                               target='inbox/%s/overview' % owner
                              )

  owner_streams = stream_get_actor(api_user, owner)
  for stream in owner_streams:
    sub_ref = subscription_get(ROOT,
                               stream.key().name(),
                               'inbox/%s/overview' % (target)
                              )
    if sub_ref and sub_ref.state == 'pending':
      sub_ref.state = 'subscribed'
      sub_ref.put()

  # Add contact's recent posts to user's stream.
  try:
    # ROOT because this is an admin only operation for the moment.
    inbox_copy_entries(ROOT, target, owner)
  except:
    # Private stream, couldn't add.
    pass
  # XXX end transaction

  if not existing_rel_ref:
    _notify_new_contact(owner_ref, target_ref)

  return ResultWrapper(rel_ref, relation=rel_ref)

@write_required
@owner_required
def actor_add_contacts(api_user, owner, targets):
  """ actor_add_contact for each of targets """
  o = {}
  try:
    for target in targets:
      o[target] = actor_add_contact(api_user, owner, target)
  except exception.ApiException:
    o[target] = None
  return o


@admin_required
def actor_count_contacts(api_user, nick):
  nick = clean.user(nick)
  query = Relation.gql('WHERE owner = :1 AND relation = :2',
                       nick,
                       'contact')
  return query.count()

@admin_required
def actor_count_followers(api_user, nick):
  nick = clean.user(nick)
  query = Relation.gql('WHERE target = :1 AND relation = :2',
                       nick,
                       'contact')
  return query.count()

def actor_is_follower(api_user, nick, potential_follower):
  """Determine if one is a follower.
  PARAMETERS:
    potential_follower - stalker.
  RETURNS: boolean
  """
  nick = clean.user(nick)
  potential_follower = clean.user(potential_follower)
  key_name = Relation.key_from(relation='contact',
                               owner=potential_follower,
                               target=nick)
  rel_ref = Relation.get_by_key_name(key_name)
  return rel_ref and True

def actor_is_contact(api_user, nick, potential_contact):
  """Determine if one is a contact.
  PARAMETERS:
    potential_contact - stalkee.
  RETURNS: boolean
  """
  nick = clean.user(nick)
  potential_contact = clean.user(potential_contact)
  key_name = Relation.key_from(relation='contact',
                               owner=nick,
                               target=potential_contact)
  rel_ref = Relation.get_by_key_name(key_name)
  return rel_ref and True
  

def actor_get(api_user, nick):
  """Returns an actor by the given nick.

  PARAMS:

    * nick - the nick of the actor

      * Example - ``jaiku`` for ``jaiku`` user, or ``#jaiku``
        for ``#jaiku`` channel

  RETURNS: actor_ref

  An actor_ref has the following attributes:

    * avatar_updated_at - timestamp of the last update to the avatar;
      `more info on timestamp`_

    * deleted_at - always null (otherwise you couldn't get to it!)

    * extra - optional attributes, see description in the section below

    * nick - full nick of user or channel

      * Example - ``jaiku@jaiku.com`` for the ``jaiku`` user or
        ``#jaiku@jaiku.com`` for the ``#jaiku`` channel
    * privacy - actor's privacy setting:

      * 2 = actor's jaikus are shown to contacts only

      * 3 = actor's jaikus are public

    * type - either 'channel' or 'user'

  The 'extra' attribute is another object that contains the following *optional*
  attributes:

    * contact_count - applicable to users only

    * follower_count - applicable to users only

    * icon - partial path to actor's avatar image; `more info on icon`_

    * description - applicable to channels only

    * member_count - applicable to channels only

    * admin_count - applicable to channels only

    * given_name - applicable to users only

    * family_name - applicable to users only

  EXAMPLE API RETURN:

  ::

    {'status': 'ok',
     'rv': {'actor': {'avatar_updated_at': '2009-01-01 00:00:00',
                      'nick': 'test@example.com',
                      'privacy': 3,
                      'type': 'user',
                      'extra': {'deleted_at': null,
                                'follower_count': 7,
                                'follower_count': 14,
                                'icon': 'default/animal_8',
                                'given_name': 'Test',
                                'family_name': 'User'
                                }
                      }
            }
     }

  .. _more info on timestamp: /api/docs/response_timestamp
  .. _more info on icon: /api/docs/response_icon

  """
  nick = clean.nick(nick)
  if not nick:
    raise exception.ApiException(0x00, "Invalid nick")

  not_found_message = 'Actor not found: %s' % nick

  key_name = Actor.key_from(nick=nick)
  actor_ref = Actor.get_by_key_name(key_name)
  
  if not actor_ref:
    raise exception.ApiNotFound(not_found_message)
    
  if actor_ref.is_deleted():
    raise exception.ApiDeleted(not_found_message)
  
  if actor_can_view_actor(api_user, actor_ref):
    return ResultWrapper(actor_ref, actor=actor_ref)

  # TODO(termie): do we care about permissions here?
  #               the receiver of this instance can make modifications
  #               but this is currently necessary to update the 
  #               follower / contact counts
  return ResultWrapper(actor_ref, actor=actor_ref.to_api_limited())

# depends on actor_get privacy
def actor_get_actors(api_user, nicks):
  o = {}
  nicks = list(set(nicks))
  if not nicks:
    return o

  for nick in nicks:
    try:
      actor = actor_get(api_user, nick)
    except exception.ApiException:
      actor = None
    except exception.ValidationError:
      logging.warn('Validation error for nick: %s' % nick)
      actor = None
    o[nick] = actor

  return o

@public_owner_or_contact
def actor_get_channels_admin(api_user, nick, limit=48, offset=None):
  """returns the channels the given actor is a member of"""
  nick = clean.nick(nick)
  query = Relation.gql('WHERE target = :1 AND relation = :2 AND owner > :3',
                       nick,
                       'channeladmin',
                       offset)
  rv = query.fetch(limit)
  return [x.owner for x in rv]

@public_owner_or_contact
def actor_get_channels_member(api_user, nick, limit=48, offset=None):
  """returns the channels the given actor is a member of"""
  query = Relation.gql('WHERE target = :1 AND relation = :2 AND owner > :3',
                       nick,
                       'channelmember',
                       offset)
  rv = query.fetch(limit)
  return [x.owner for x in rv]

@public_owner_or_contact
def actor_get_contacts(api_user, nick, limit=48, offset=None):
  """returns the contacts for the given actor if current_actor can view them"""
  query = Relation.gql('WHERE owner = :1 AND relation = :2 AND target > :3',
                       nick,
                       'contact',
                       offset)
  results = query.fetch(limit)
  return [x.target for x in results]

@owner_required
def actor_get_contacts_since(api_user, nick, limit=30, since_time=None):
  """returns the contacts for the given actor if current_actor can view them"""
  query = Relation.gql('WHERE owner = :1 AND relation = :2 AND target > :3',
                       nick,
                       'contact',
                       offset)
  results = query.fetch(limit)
  return [x.target for x in results]

@owner_required
def actor_get_contacts_avatars_since(api_user, nick, limit=30, since_time=None):
  """Returns the contacs of the actor by the given nick.

  An actor is always considered as her own contact.
  If the ``since_time`` parameter is set, only contacts whose avatars were
  updated afterwards will be included.

  PARAMS:
    * nick - the nick of the actor whose contacts are to be returned
    * limit - the number of contacts to return; defaults to 30
    * since_time - for filtering results by avatar's last update time

  ``since_time`` needs to be in one of the following formats::

      '%Y-%m-%d %H:%M:%S'     # '2006-10-25 14:30:59'
      '%Y-%m-%d %H:%M'        # '2006-10-25 14:30'
      '%Y-%m-%d'              # '2006-10-25'
      '%m/%d/%Y %H:%M:%S'     # '10/25/2006 14:30:59'
      '%m/%d/%Y %H:%M'        # '10/25/2006 14:30'
      '%m/%d/%Y'              # '10/25/2006'
      '%m/%d/%y %H:%M:%S,     # '10/25/06 14:30:59'
      '%m/%d/%y %H:%M'        # '10/25/06 14:30'
      '%m/%d/%y'              # '10/25/06'

  RETURNS: A list of actor_ref. See `actor_get`_ for actor_ref format.

  .. _actor_get: /api/docs/method_actor_get
  """
  limit = int(limit)
  if since_time:
    since_time = clean.datetime(since_time)
    # we have to fetch as many as possible because of the since_time filter
    contacts = actor_get_contacts(api_user, nick, limit=1000)
  else:
    # excludes self there
    contacts = actor_get_contacts(api_user, nick, limit=(limit - 1))
  contacts.append(nick)
  contacts_ref = actor_get_actors(api_user, contacts)
  results = []
  for contact_ref in contacts_ref.values():
    if not contact_ref:
      continue
    if not since_time or contact_ref.avatar_updated_at > since_time:
      results.append(contact_ref)
    if len(results) >= limit:
      break

  return ResultWrapper(results, contacts=results)

@public_owner_or_contact
def actor_get_followers(api_user, nick, limit=48, offset=None):
  """returns the followers for the given actor if current_actor can view them"""
  query = Relation.gql('WHERE target = :1 AND relation = :2 AND owner > :3',
                       nick,
                       'contact',
                       offset)
  results = query.fetch(limit)
  return [x.owner for x in results]

def actor_get_safe(api_user, nick):
  try:
    return actor_get(api_user, nick)
  except exception.ApiException:
    return None

@public_owner_or_contact
def actor_has_contact(api_user, owner, target):
  key_name = Relation.key_from(relation='contact', owner=owner, target=target)
  return Relation.get_by_key_name(key_name)

def actor_lookup_email(api_user, email):
  """ Lookup an actor based on an email address,
  useful for determining if an email address is available
  PARAMETERS:
    email - email alias
  RETURNS: actor_ref
  """
  query = Relation.gql("WHERE target = :1 AND relation = 'email'",
                       email)
  for rel_ref in query:
    actor_ref = actor_get_safe(api_user, rel_ref.owner)
    if actor_ref:
      return actor_ref
  return None

def actor_lookup_im(api_user, im):
  query = Relation.gql('WHERE relation = :1 AND target = :2',
                       'im_account',
                       im)
  rel_ref = query.get()
  if not rel_ref:
    return None
  else:
    return actor_get(api_user, rel_ref.owner)

def actor_lookup_mobile(api_user, mobile):
  mobile = clean.mobile(mobile)
  query = Relation.gql("WHERE target = :1 AND relation = 'mobile'",
                       mobile)
  for rel_ref in query:
    actor_ref = actor_get_safe(api_user, rel_ref.owner)
    if actor_ref:
      return actor_ref
  return None

def actor_lookup_nick(api_user, nick):
  """ lookup actor based on normalized version of the nick """
  actor_ref = actor_get_safe(api_user, nick)
  if actor_ref:
    return actor_ref

  nick = clean.normalize_nick(clean.nick(nick))
  query = Actor.gql('WHERE normalized_nick = :1',
                    nick)
  actor_ref = query.get()
  if not actor_ref:
    return None
  return actor_get_safe(api_user, actor_ref.nick)

@delete_required
@owner_required
def actor_remove(api_user, nick):
  """Mark the specified actor for deletion."""
  actor_ref = actor_get(api_user, nick)

  if actor_ref:
    actor_ref.mark_as_deleted()
    return True

  return False

@delete_required
@owner_required
def actor_remove_contact(api_user, owner, target):
  owner_ref = actor_get(api_user, owner)
  target_ref = actor_get(api_user, target)

  # XXX start transaction
  # Delete the relationship
  key_name = Relation.key_from(relation='contact', 
                               owner=owner_ref.nick,
                               target=target_ref.nick)
  rel = Relation.get_by_key_name(key_name)

  if not rel:
    raise exception.ApiException(
        0, 'Cannot remove a relationship that does not exist')

  rel.delete()

  # Decrease the counts for each
  owner_ref.extra.setdefault('contact_count', 1)
  owner_ref.extra['contact_count'] -= 1
  owner_ref.put()

  target_ref.extra.setdefault('follower_count', 1)
  target_ref.extra['follower_count'] -= 1
  target_ref.put()

  # Unsubscribe owner from all of target's streams
  streams = stream_get_actor(ROOT, target)
  for stream in streams:
    sub = subscription_remove(ROOT,
                              topic=stream.key().name(),
                              target='inbox/%s/overview' % owner)

  # If owner is private mark all subscriptions to her streams as pending
  if owner_ref.privacy < PRIVACY_PUBLIC:
    streams = stream_get_actor(api_user, owner)
    for stream in streams:
      sub_ref = subscription_get(ROOT,
                                 topic=stream.key().name(),
                                 target='inbox/%s/overview' % target)
      if sub_ref:
        sub_ref.state = "pending"
        sub_ref.put()

  # XXX end transaction
  return rel

@admin_required
def actor_update_intermediate_password(api_user, nick, password):
  actor_ref = actor_get(api_user, nick)
  actor_ref.password = util.hash_password(nick, password)
  actor_ref.put()
  return actor_ref

#######
#######
#######

@owner_required
def avatar_clear_actor(api_user, nick):
  actor_ref = actor_get(ROOT, nick)
  actor_ref.extra['icon'] = util.DEFAULT_AVATAR_PATH
  actor_ref.avatar_updated_at = utcnow()
  actor_ref.put()
  return True

@owner_required
def avatar_set_actor(api_user, nick, path):
  """sets the avatar path for a given user"""
  validate.avatar_path(path)

  actor_ref = actor_get(ROOT, nick)
  actor_ref.extra['icon'] = path
  actor_ref.avatar_updated_at = utcnow()
  actor_ref.put()

  return True

@throttled(minute=5, hour=30)
@owner_required
@catch_image_error
def avatar_upload(api_user, nick, content):
  """ accept uploaded binary content, save an original and
  make a few smaller sizes, assign the proper fields to the user
  """
  nick = clean.nick(nick)
  resized = {'original': content}

  # Crop to a square
  jpeg = images.crop(content,
                     0.0, 0.0, 1.0, 1.0,
                     output_encoding=images.JPEG)
  original_size = imageutil.size_from_jpeg(jpeg)
  if original_size and original_size[0] != original_size[1]:
    dimension = min(original_size)
    crop_to = _crop_to_square(original_size, (dimension, dimension))
    content = images.crop(content, output_encoding=images.JPEG,
                          *crop_to)

  # note: we only support JPEG format at the moment
  for size, dimensions in AVATAR_IMAGE_SIZES.items():
    resized[size] = images.resize(content, output_encoding=images.JPEG,
                                  *dimensions)

  path_uuid = util.generate_uuid()

  # XXX begin transaction
  for img_size, img_data in resized.iteritems():
    path = 'avatar_%s_%s' % (path_uuid, img_size)

    # TODO: Check for hash collisions before uploading (!!)
    img_ref = image_set(api_user,
                        nick,
                        path=path,
                        content=img_data,
                        format='jpg',
                        size=img_size)
  # XXX end transaction

  # TODO(termie): this returns somewhat differently than background_upload below,
  return '%s/avatar_%s' % (nick, path_uuid)

#######
#######
#######

@owner_required
def background_clear_actor(api_user, nick):
  actor_ref = actor_get(ROOT, nick)
  actor_ref.extra.pop('bg_image', '')
  actor_ref.extra.pop('bg_color', '')
  actor_ref.extra.pop('bg_repeat', '')
  actor_ref.put()
  return True

@owner_required
def background_set_actor(api_user, nick, path=None, color=None, repeat=None):
  """sets the backgorund info for a given user"""
  path = clean.bg_image(path)
  color = clean.bg_color(color)
  repeat = clean.bg_repeat(repeat)

  actor_ref = actor_get(ROOT, nick)
  if path:
    actor_ref.extra['bg_image'] = path
  if color:
    actor_ref.extra['bg_color'] = color
  if repeat:
    actor_ref.extra['bg_repeat'] = repeat
  actor_ref.put()

  return True

@throttled(minute=5, hour=30)
@owner_required
@catch_image_error
def background_upload(api_user, nick, content):
  """ accept uploaded binary content, save an original and
  make a few smaller sizes, assign the proper fields to the user
  """
  nick = clean.nick(nick)

  # XXX begin transaction
  img = images.Image(content)

  # note: only supporting JPEG format
  #img_data = img.execute_transforms(output_encoding=images.JPEG)
  img_data = images.horizontal_flip(content, output_encoding=images.JPEG)
  img_data = images.horizontal_flip(img_data, output_encoding=images.JPEG)

  path_uuid = util.generate_uuid()
  path = 'bg_%s' % (path_uuid)

  # TODO: Check for hash collisions before uploading (!!)
  img_ref = image_set(api_user, 
                      nick, 
                      path=path, 
                      format='jpg', 
                      content=content)
  # XXX end transaction


  # TODO(termie): this returns somewhat differently than avatar_upload above,
  return '%s/bg_%s.jpg' % (nick, path_uuid)

#######
#######
#######

def channel_browse(api_user, limit, offset_channel_nick=''):
  """Return all channels.
  PARAMETERS:
    limit - Number of results to retrieve
    offset_channel_nick - Retrieve channels with nick > this value.
  """
  # Sort by nick, so that filtering works.
  query = Actor.gql('WHERE type = :1 AND deleted_at = :2 and nick > :3 '
                    'ORDER BY nick',
                    'channel',
                    None,
                    offset_channel_nick)

  # Limit to the range specified:
  if offset_channel_nick:
    logging.info('offset: ' + offset_channel_nick)
  results = query.fetch(limit)

  return results

def channel_browse_recent(api_user, limit=48, offset=None):
  pass

@throttled(minute=2, hour=10, month=50)
@write_required
def channel_create(api_user, **kw):
  channel_nick = clean.channel(kw.get('channel'))
  creator_nick = kw.get('nick')

  params = {'nick': channel_nick,
            'normalized_nick': channel_nick.lower(),
            'privacy': kw.get('privacy', PRIVACY_PUBLIC),
            'type': 'channel',
            'password': '',
            'extra': {'description': kw.get('description', ''),
                      'member_count': 0,
                      'admin_count': 0,
                      },
            }

  creator_ref = actor_get(api_user, creator_nick)

  if not actor_owns_actor(api_user, creator_ref):
    raise exception.ApiException(
        0x00, "Not allowed to act on behalf of this user")

  try:
    existing_ref = channel_get(ROOT, channel_nick)
  except exception.ApiDeleted:
    existing_ref = True
  except exception.ApiNotFound:
    existing_ref = False

  if existing_ref:
    raise exception.ApiException(
        0x00, 'Name of the channel is already in use: %s' % channel_nick)

  if creator_ref.is_channel():
    raise exception.ApiException(0x00, 'Channels cannot create other channels')
  
  admin_channels = actor_get_channels_admin(api_user, creator_ref.nick)
  if len(admin_channels) >= MAX_ADMINS_PER_ACTOR:
    raise exception.ApiException(
        0x00, 'Only allowed to admin %d channels' % MAX_ADMINS_PER_ACTOR)


  # also create a list of administrators and members
  # TODO allow some of these to be specified as parameters

  admins = [creator_ref.nick]
  for admin in admins:
    params['extra']['admin_count'] += 1

  # XXX start transaction
  channel_ref = Actor(**params)
  channel_ref.put()

  relation = 'channeladmin'
  rel_ref = Relation(owner=channel_ref.nick,
                     relation=relation,
                     target=creator_ref.nick,
                     )
  rel_ref.put()

  # create the presence stream for the channel
  stream_ref = stream_create_presence(api_user,
                                      channel_ref.nick,
                                      read_privacy=PRIVACY_PUBLIC,
                                      write_privacy=PRIVACY_CONTACTS)

  channel_join(api_user, creator_nick, channel_nick)
  # XXX end transaction

  return channel_ref

@public_owner_or_member
def channel_get(api_user, channel):
  """Retrieve the specified channel, if it has not been deleted.
  PAREMTETRS:
    api_user - (the usual)
    channel - Nick of channel to retrieve
  RETURNS:  Channel object
  THROWS: ApiExceptioon
  """

  not_found_message = 'Channel not found: %s' % channel
  channel = clean.channel(channel)
  
  key_name = Actor.key_from(nick=channel)
  channel_ref = Actor.get_by_key_name(key_name)
  
  if not channel_ref:
    raise exception.ApiNotFound(not_found_message)

  if channel_ref.is_deleted():
    raise exception.ApiDeleted(not_found_message)

  return channel_ref

@public_owner_or_member
def channel_get_admins(api_user, channel, limit=24):
  query = Relation.gql('WHERE owner = :1 AND relation = :2',
                       channel,
                       'channeladmin')
  return [a.target for a in query.fetch(limit)]

# depends on channel_get's privacy
def channel_get_channels(api_user, channels):
  """Retrieve the specified channels, filtering out those which have been
     deleted.
  PARAMETERS:
    api_user - (the usual)
    channels - [nick]  - List of channel nicks, will be keys in the dictionary
                         returned
  RETURNS: { channel_nick : channel_obj }
           Where channel_obj may be None if the channel does not exist.
           channel_nick are the keys passed as a parameter.
  """
  channel_refs = {}
  channels = list(set(channels))
  if not channels:
    return channel_refs

  for nick in channels:
    channel = channel_get_safe(api_user, nick)

    # Will be set to None if the channel doesn't exist (or was deleted)
    channel_refs[nick] = channel

  return channel_refs

@public_owner_or_member
def channel_get_members(api_user, channel, limit=24, offset=None):
  query = Relation.gql('WHERE owner = :1 AND relation = :2 AND target > :3',
                       channel,
                       'channelmember',
                       offset)
  return [a.target for a in query.fetch(limit)]

def channel_get_safe(api_user, channel):
  """Retrieve the specified channel, if it has not been deleted.
  PAREMTETRS:
    api_user - (the usual)
    channel - Nick of channel to retrieve
  RETURNS:  Channel object or None
  """
  try:
    channel_ref = channel_get(api_user, channel)
  except exception.ApiException:
    return None
  return channel_ref

@public_owner_or_member
def channel_has_admin(api_user, channel, nick):
  key_name = Relation.key_from(relation='channeladmin', 
                               owner=channel, 
                               target=nick)
  admin_ref = Relation.get_by_key_name(key_name)
  if admin_ref:
    return True
  return False

@public_owner_or_member
def channel_has_member(api_user, channel, nick):
  key_name = Relation.key_from(relation='channelmember',
                               owner=channel,
                               target=nick)
  member_ref = Relation.get_by_key_name(key_name)
  if member_ref:
    return True
  return False

@throttled(minute=10, hour=50, day=100, month=200)
@owner_required
def channel_join(api_user, nick, channel):
  channel_ref = channel_get(api_user, channel)
  actor_ref = actor_get(api_user, nick)

  if channel_has_member(api_user, channel_ref.nick, actor_ref.nick):
    raise exception.ApiException(0x00, "already a member")

  # XXX start transaction
  relation = 'channelmember'
  rel = Relation(owner=channel_ref.nick, 
                 relation=relation,
                 target=actor_ref.nick,
                 )
  rel.put()

  # TODO probably a race-condition
  channel_ref.extra['member_count'] += 1
  channel_ref.put()

  streams = stream_get_actor(ROOT, channel)
  for stream in streams:
    sub = subscription_request(api_user,
                               topic=stream.key().name(),
                               target='inbox/%s/overview' % actor_ref.nick)
  # XXX end transaction

  return rel

@owner_required
def channel_part(api_user, nick, channel):
  # XXX start transaction
  channel_ref = channel_get(api_user, channel)
  actor_ref = actor_get(api_user, nick)

  if not channel_has_member(api_user, channel_ref.nick, actor_ref.nick):
    raise exception.ApiException(0x00, "not a member")
  
  key_name = Relation.key_from(relation='channelmember',
                               owner=channel_ref.nick,
                               target=actor_ref.nick)
  rel_ref = Relation.get_by_key_name(key_name)

  rel_ref.delete()

  channel_ref.extra['member_count'] -= 1
  channel_ref.put()

  # Unsubscribe owner from all of target's streams
  streams = stream_get_actor(ROOT, channel)
  for stream in streams:
    sub = subscription_remove(ROOT,
                              topic=stream.key().name(),
                              target='inbox/%s/overview' % actor_ref.nick)
  # XXX end transaction

  return rel_ref

@throttled(minute=10, hour=100, day=300, month=1000)
@write_required
@owner_required
def channel_post(api_user, **kw):
  # grab the params we're interested in
  message = kw.get('message', kw.get('title', '')) # legacy compat
  location = kw.get('location', '')
  icon = clean.icon(kw.get('icon', 0))
  uuid = kw.get('uuid', util.generate_uuid())
  channel = kw.get('channel', None)
  nick = kw.get('nick', None)

  validate.length(message, 0, MAX_POST_LENGTH)
  validate.location(location)
  validate.user_nick(nick)
  validate.uuid(uuid)

  channel = clean.channel(channel)

  # check whether the channel exists, we're probably going to make
  # it if it doesn't
  channel_ref = channel_get_safe(api_user, channel)
  actor_ref = actor_get(api_user, nick)

  if not channel_ref:
    channel_ref = channel_create(api_user, nick=nick, channel=channel)

  # join the channel if we aren't a member, if this fails we can't post
  if not channel_has_member(api_user, channel_ref.nick, actor_ref.nick):
    channel_join(api_user, actor_ref.nick, channel_ref.nick)

  # we've decided this is a presence update
  stream = stream_get_presence(api_user, channel)

  values = {
    'stream': stream.key().name(),
    'uuid': uuid,
    'owner': stream.owner,
    'actor': actor_ref.nick,
    'extra': {
      'title': message,
      'location': location,
      'icon': icon,
    }
  }

  # XXX start transaction
  #presence = _set_presence(**values)
  entry = _add_entry(stream, new_values=values)
  subscribers = _subscribers_for_entry(stream, entry)
  inboxes = _add_inboxes_for_entry(subscribers, stream, entry)
  _notify_subscribers_for_entry(subscribers, actor_ref, stream, entry)
  # XXX end transaction

  return entry

@owner_required
def channel_update(api_user, channel, **kw):
  allowed_attributes = ['external_url',
                        'description',
                        ]

  channel_ref = channel_get(api_user, channel)

  
  for k, v in kw.iteritems():
    if k not in allowed_attributes:
      continue

    if k == 'external_url' and v:
      v = clean.url(v)

    channel_ref.extra[k] = v

  channel_ref.put()
  return channel_ref

#######
#######
#######

@admin_required
def email_associate(api_user, nick, email):
  actor_ref = actor_get(api_user, nick)

  # XXX start transaction
  if actor_lookup_email(api_user, email):
    raise exception.ApiException(0x00, 'Email alias already in use')

  # clear old email addresses
  # TODO(termie): support multiple email addresses
  old_query = Relation.gql('WHERE owner = :1 AND relation = :2',
                           actor_ref.nick,
                           'email')
  for rel_ref in old_query:
    rel_ref.delete()

  relation_ref = Relation(owner=actor_ref.nick,
                          relation='email',
                          target=email,
                          )
  relation_ref.put()
  # XXX end transaction

  return relation_ref

@owner_required
def email_get_actor(api_user, nick):
  nick = clean.nick(nick)
  query = Relation.gql('WHERE owner = :1 AND relation = :2',
                       nick,
                       'email')
  rel_ref = query.get()
  if rel_ref:
    return rel_ref.target
  return None

# To prevent circular dependency from common.mail to common.api.admin_requred
# we use these simple wrapper functions for email sending.
@admin_required
def email_mass_send(api_user, message_tuples):
  mail.mass_send(message_tuples)

@admin_required
def email_send(api_user, email, subject, message, on_behalf=None, html_message=None):
  mail.send(email, subject, message, on_behalf=on_behalf, html_message=html_message)

#######
#######
#######

@write_required
@owner_required
@public_owner_or_contact_by_entry
def entry_add_comment(api_user, _task_ref=None, **kw):
  """ Add a comment to given entry

  PARAMS:

    * _task_ref - admin-only, task to resume
    * content - the text content of the commment
    * stream - the stream in which the entry this comment is on resides
    * entry - the entry this comment is on
    * uuid - a unique identifier for this comment
    * nick - the actor making the comment

  RETURNS: comment_ref

  EXAMPLE API RETURN:

  ::
  
    {'status': 'ok',
     'rv': {'comment': {'stream': 'stream/test@example.com/comments',
                        'uuid': '1234567890abcdef',
                        'entry': 'stream/root@example.com/presence/12345',
                        'owner': 'root@example.com',
                        'actor': 'test@example.com',
                        'extra': {'content': 'a comment!',
                                  'entry_stream': 'stream/root@example.com/presence',
                                  'entry_title': 'please comment on me',
                                  'entry_actor': 'root@example.com',
                                  'entry_uuid': '12345',
                                  }
                        }
            }
     }

  """

  content = kw.get('content', '')
  stream = kw.get('stream')
  entry = kw.get('entry')
  uuid = kw.get('uuid', util.generate_uuid())
  nick = clean.nick(kw.get('nick', ''))

  try:
    validate.length(content, 1, settings.MAX_COMMENT_LENGTH)
    validate.stream(stream)
    validate.entry(entry)
    validate.uuid(uuid)
  except exception.ValidationError, e:
    raise exception.ApiException(0x00, e.user_message)

  if settings.QUEUE_ENABLED:
    task_ref = _task_ref
    if not task_ref:
      kw['uuid'] = uuid
      task_ref = task_get_or_create(api_user,
                                    nick,
                                    'entry_add_comment',
                                    uuid,
                                    kw=kw)

  actor_ref = actor_get(api_user, nick)
  comment_stream_ref = stream_get_comment(api_user, actor_ref.nick)
  stream_ref = stream_get(api_user, stream)
  entry_ref = entry_get(api_user, entry)

  values = {"stream": comment_stream_ref.key().name(),
            "uuid": uuid,
            "entry": entry_ref.key().name(),
            "owner": stream_ref.owner,
            "actor": actor_ref.nick,
            "extra": {"content": content,
                      "entry_stream": stream_ref.key().name(),
                      "entry_stream_type": stream_ref.type,
                      "entry_title": entry_ref.extra.get('title', None),
                      "entry_actor": entry_ref.actor,
                      "entry_uuid": entry_ref.uuid,
                      },
            }

  if settings.QUEUE_ENABLED:
    try:
      comment_ref = _process_new_entry_with_progress(
          task_ref, 
          actor_ref, 
          new_stream_ref=comment_stream_ref,
          entry_stream_ref=stream_ref,
          entry_ref=entry_ref,
          new_values=values
          )
    except exception.ApiException:
      # Something is wrong, bail out and delete the task
      task_ref.delete()
      raise
  else:
    comment_ref = _add_entry(comment_stream_ref, 
                             new_values=values, 
                             entry_ref=entry_ref)
    subscribers = _subscribers_for_comment(comment_stream_ref, stream_ref,
                                           entry_ref, comment_ref)
    inboxes = _add_inboxes_for_entry(subscribers, comment_stream_ref,
                                     comment_ref)





    _notify_subscribers_for_comment(actor_ref, comment_ref, entry_ref)
  return ResultWrapper(comment_ref, comment=comment_ref)

def entry_add_comment_with_entry_uuid(api_user, **kw):
  """For DJabberd"""
  entry_uuid = kw.pop('entry_uuid')
  entry_ref = entry_get_uuid(api_user, entry_uuid)
  if not entry_ref:
    raise exception.ApiException(
        0x00,
        'No entry with uuid %s' % entry_uuid)
  kw['stream'] = entry_ref.stream
  kw['entry'] = entry_ref.keyname()
  return entry_add_comment(api_user, **kw)

@public_owner_or_contact_by_entry
def entry_get(api_user, entry):
  entry_ref = StreamEntry.get_by_key_name(entry)

  not_found_message = 'Entry not found: %s' % entry
  if not entry_ref:
    raise exception.ApiNotFound(not_found_message)
  
  if entry_ref.is_deleted():
    raise exception.ApiDeleted(not_found_message)
  
  try:
    # if this is a comment ensure that the parent exists
    if entry_ref.entry:
      # A comment
      parent_entry = entry_get(api_user, entry_ref.entry)
    
    # ensure the author exists
    actor_get(api_user, entry_ref.actor)

    # and the stream
    stream_get(api_user, entry_ref.stream)

    # and the owner
    actor_get(api_user, entry_ref.owner)
  except exception.ApiDeleted:
    raise exception.ApiDeleted(not_found_message)
  except exception.ApiNotFound:
    raise exception.ApiNotFound(not_found_message)

  return entry_ref

@public_owner_or_contact_by_entry
def entry_get_comments(api_user, entry):
  entry_ref = entry_get_safe(api_user, entry)
  if not entry_ref:
    return None

  query = InboxEntry.gql('WHERE inbox = :1 ORDER BY created_at',
                         entry_ref.key().name() + '/comments')
  comment_keys = [c.stream_entry_keyname() for c in query]
  return entry_get_entries(api_user, comment_keys)

# Relies on ACLs on the called functions
def entry_get_comments_with_entry_uuid(api_user, entry_uuid):
  entry_ref = entry_get_uuid(api_user, entry_uuid)
  if not entry_ref:
    return None

  query = InboxEntry.gql('WHERE inbox = :1 ORDER BY created_at',
                         entry_ref.key().name() + '/comments')
  comment_keys = [c.stream_entry_keyname() for c in query]
  comments = entry_get_entries(api_user, comment_keys)
  return ResultWrapper(comments, comments=comments, entry=entry_ref)

def entry_get_entries(api_user, entries):
  """Turn a list of entry keys to a list of entries,
  maintaining the order.
  The list only contains values where entries
  (and their parent entities) exist.
  """
  out = list()
  if not entries:
    return out
  entries_dict = entry_get_entries_dict(api_user, entries)

  for entry_key in entries:
    entry = entries_dict.get(entry_key, None)
    if entry:
      out.append(entry)
  return out

def entry_get_entries_dict(api_user, entries):
  """Turn a list of entry keys to a dictionary of entries.
  The dictionary only contains values for keys where entries
  (and their parent entities) exist.
  """
  out = {}
  if not entries:
    return out

  entries = list(set(entries))
  for entry in entries:
    entry_ref = entry_get_safe(api_user, entry)
    if entry_ref:
      out[entry] = entry_ref

  return out

def entry_get_inbox_since(api_user, inbox, limit=30, since_time=None):
  inbox = inbox_get_entries_since(
      api_user, inbox, limit=limit, since_time=since_time)
  entries = entry_get_entries(api_user, inbox)
  return ResultWrapper(entries, entries=entries)

def entry_get_inbox(api_user, inbox, limit=30, offset=None):
  inbox = inbox_get_entries_since(api_user, inbox, limit=limit, offset=offset)
  return entry_get_entries(api_user, inbox)

@owner_required
def entry_get_actor_overview(api_user, nick, limit=30, offset=None):
  """ Get entries for a user's overview

  PARAMS:
    * nick - the actor for whom to fetch the overview
    * limit - how many entries to fetch, max 100
    * offset - a datetime before which to retrieve entries

  RETURNS: [entry_ref1, entry_ref2, ...]


  """
  nick = clean.nick(nick)
  inbox = 'inbox/%s/overview' % nick
  return entry_get_inbox(api_user, inbox, limit=limit, offset=offset)
  
@owner_required
def entry_get_actor_overview_since(api_user, nick, limit=30, since_time=None):
  """ Get entries for a user's overview since a certain time

  This is a useful call if you are trying to periodically poll to keep
  up to date as it is more efficient for you to only get the updates since
  some time near the last time you get an entry.

  PARAMS:
    * nick - the actor for whom to fetch the overview
    * limit - how many entries to fetch, max 100
    * since_time - a datetime after which to retrieve entries

  RETURNS: [entry_ref1, entry_ref2, ...]


  """

  nick = clean.nick(nick)
  inbox = 'inbox/%s/overview' % nick
  return entry_get_inbox_since(
      api_user, inbox, limit=limit, since_time=since_time)

@public_owner_or_contact_by_stream
def entry_get_last(api_user, stream):
  """ Queries the StreamEntry entities to find the last StreamEntry
  for the given stream.
  """
  query = StreamEntry.gql('WHERE stream = :1 ORDER BY created_at DESC',
                          stream)
  entry_ref = query.get()
  if not entry_ref:
    return None
  return entry_get(api_user, entry_ref.key().name())

def entry_get_uuid(api_user, uuid):
  """ Queries the StreamEntry entities to find the StreamEntry corresponding to
  given uuid.
  """
  entry_ref = StreamEntry.gql("WHERE uuid = :1", uuid).get()
  if not entry_ref:
    return None
  if not actor_can_view_entry(api_user, entry_ref):
    raise exception.ApiException(exception.PRIVACY_ERROR,
                                 'You are not allowed to view this entry')
  return entry_get(api_user, entry_ref.key().name())

def entry_get_safe(api_user, entry):
  """Like entry_get, but returns None for entries you don't have rights to see
  rather than throwing an exception.
  """
  try:
    entry_ref = entry_get(api_user, entry)
  except exception.ApiException:
    return None
  return entry_ref

@write_required
def entry_mark_as_spam(api_user, entry):
  """ TODO(termie): helper call so that I don't have to drastically change some old
      apis in template code """
  return abuse_report_entry(api_user, api_user.nick, entry)

@delete_required
@owner_required_by_entry
def entry_remove(api_user, entry):
  entry_ref = StreamEntry.get_by_key_name(entry)
  if not entry_ref:
    raise exception.ApiException(0x00, "Invalid post, not found")
  if entry_ref.entry:
    raise exception.ApiException(0x00, "Cannot call entry_remove on a comment")
  entry_ref.mark_as_deleted()

@delete_required
@owner_required_by_entry
def entry_remove_comment(api_user, comment):
  # XXX start transaction
  comment_ref = StreamEntry.get_by_key_name(comment)
  if not comment_ref:
    raise exception.ApiException(0x00, "Invalid comment, not found")
  if not comment_ref.entry:
    raise exception.ApiException(
        0x00,
        "Cannot call entry_remove_comment on something that is not a comment")
  entry_ref = entry_get(api_user, comment_ref.entry)
  entry_ref.extra.setdefault('comment_count', 0)
  if entry_ref.extra['comment_count'] > 0:
    entry_ref.extra['comment_count'] -= 1

  entry_ref.put()
  comment_ref.mark_as_deleted()
  # XXX end transaction

#######
#######
#######

@owner_required
def keyvalue_get(api_user, nick, keyname):
  if not keyname:
    return None
  nick = clean.nick(nick)
  key_name = KeyValue.key_from(actor=nick, keyname=keyname)
  return KeyValue.get_by_key_name(key_name)

@owner_required
def keyvalue_prefix_list(api_user, nick, keyname):
  if not keyname:
    return ResultWrapper(keyvalues, keyvalues=None)
  nick = clean.nick(nick)
  key_name_lower = unicode(keyname)
  key_name_upper = key_name_lower + "\xEF\xBF\xBD".decode('utf-8')
  keyvalues = KeyValue.gql(u"WHERE actor = :1 AND keyname >= :2 AND keyname < :3",
                           nick,
                           key_name_lower,
                           key_name_upper).fetch(1000)
  return ResultWrapper(keyvalues, keyvalues=keyvalues)

@write_required
@owner_required
def keyvalue_put(api_user, nick, keyname, value):
  if not nick:
    return None
  if not keyname:
    return None
  nick = clean.nick(nick)
  params = {'actor': nick,
            'keyname': keyname,
            'value': value,
            }

  keyvalue = KeyValue(**params)
  keyvalue.put()

  return keyvalue

#######
#######
#######

@admin_required
def im_associate(api_user, nick, im):
  actor_ref = actor_get(ROOT, nick)

  rel_ref = Relation(owner=nick,
                     relation='im_account',
                     target=im,
                     )
  rel_ref.put()
  return rel_ref

@admin_required
def im_disassociate(api_user, nick, im):
  actor_ref = actor_get(ROOT, nick)

  key_name = Relation.key_from(relation='im_account',
                               owner=nick,
                               target=im)
  rel_ref = Relation.get_by_key_name(key_name)
  rel_ref.delete()
  return

@owner_required
def im_get_actor(api_user, nick):
  """Given a nick, retrieve the IM alias (or None)

  RETURNS: xmpp.JID()
  """
  nick = clean.nick(nick)
  query = Relation.gql('WHERE owner = :1 AND relation = :2',
                       nick,
                       'im_account')
  rel_ref = query.get()
  if rel_ref:
    return xmpp.JID.from_uri(rel_ref.target)
  return None

#######
#######
#######

def image_get(api_user, nick, path, format='jpg'):
  keyname = 'image/%s/%s.%s' % (nick, path, format)
  image_ref = Image.get_by_key_name(keyname)
  
  # LEGACY COMPAT
  if not image_ref:
    actor_ref = actor_get(ROOT, nick)
    image_ref = Image.get_by_key_name(keyname,
                                      parent=actor_ref.key())
  return image_ref

@public_owner_or_contact
def image_get_all_keys(api_user, nick, size):
  """Given an actor, retrieve keynames"""
  query = Image.gql('WHERE actor = :1 AND size = :2', nick, size)
  return list(query.run())

@public_owner_or_contact
def image_set(api_user, nick, path, content, format='jpg', size=None):
  nick = clean.nick(nick)
  params = {'key_name': 'image/%s/%s.%s' % (nick, path, format),
            'actor': 'actor/%s' % nick,
            'content': db.Blob(content),
            }
  if size is not None:
    params['size'] = size

  image_ref = Image(**params)
  image_ref.put()
  return image_ref

#######
#######
#######

@admin_required
def inbox_copy_entries(api_user, target, nick, limit=5):
  """Add recent inbox entries from user (target) to user (nick)'s inbox.
  """
  target = clean.nick(target)
  nick = clean.nick(nick)
  limit = clean.limit(limit)
  inbox = 'inbox/%s/public' % target
  query = InboxEntry.Query().filter('inbox =', inbox).order('-created_at')
  results = query.fetch(limit=limit)
  for entry in results:
    inbox_item = 'inbox/%s/overview' % nick
    if inbox_item not in entry.inbox:
      entry.inbox.append(inbox_item)
    entry.put()
  return

@public_owner_or_contact
def inbox_get_actor_contacts(api_user, nick, limit=5, offset=None, 
                             stream_type=None):
  nick = clean.nick(nick)
  inbox = 'inbox/%s/contacts' % nick
  return inbox_get_entries(api_user, inbox, limit, offset, stream_type)

@owner_required
def inbox_get_actor_overview(api_user, nick, limit=5, offset=None, 
                             stream_type=None):
  nick = clean.nick(nick)
  inbox = 'inbox/%s/overview' % nick
  return inbox_get_entries(api_user, inbox, limit, offset, stream_type)

@owner_required
def inbox_get_actor_private(api_user, nick, limit=5, offset=None, 
                            stream_type=None):
  nick = clean.nick(nick)
  inbox = 'inbox/%s/private' % nick
  return inbox_get_entries(api_user, inbox, limit, offset)

def inbox_get_actor_public(api_user, nick, limit=5, offset=None, 
                           stream_type=None):
  nick = clean.nick(nick)
  inbox = 'inbox/%s/public' % nick
  return inbox_get_entries(api_user, inbox, limit, offset, stream_type)

def inbox_get_entries(api_user, inbox, limit=30, offset=None, 
                      stream_type=None):
  limit = clean.limit(limit)
  query = InboxEntry.Query().filter('inbox =', inbox).order('-created_at')
  if offset is not None:
    offset = clean.datetime(offset)
    query.filter('created_at <=', offset)
  if stream_type is not None:
    query.filter('stream_type =', stream_type)

  results = query.fetch(limit=limit)
  return [x.stream_entry_keyname() for x in results]

def inbox_get_entries_since(api_user, inbox, limit=30, since_time=None, 
                            stream_type=None):
  limit = clean.limit(limit)
  query = InboxEntry.Query().filter('inbox =', inbox).order('created_at')
  if since_time is not None:
    since_time = clean.datetime(since_time)
    query.filter('created_at >=', since_time)

  if stream_type is not None:
    query.filter('stream_type =', stream_type)

  results = query.fetch(limit=limit)
  return [x.stream_entry_keyname() for x in results]

def inbox_get_explore(api_user, limit=30, offset=None):
  inbox = 'inbox/%s/explore' % ROOT.nick
  return inbox_get_entries(api_user, inbox, limit, offset)

#######
#######
#######

@owner_required
def invite_accept(api_user, nick, code):
  invite_ref = invite_get(ROOT, code)
  for_actor = invite_ref.for_actor

  # XXX begin transaction
  if util.is_channel_nick(for_actor):
    channel_join(ROOT, nick, for_actor)
  else:
    actor_add_contact(ROOT, nick, for_actor)
    actor_add_contact(ROOT, for_actor, nick)
  invite_ref.delete()
  # XXX end transaction

def invite_get(api_user, code):
  key_name = Invite.key_from(code=code)
  invite_ref = Invite.get_by_key_name(key_name)
  if not invite_ref:
    raise exception.ApiException(0x00, "Invalid invite code")
  return invite_ref

@owner_required
def invite_reject(api_user, nick, code):
  invite_ref = invite_get(ROOT, code)
  invite_ref.delete()

@throttled(minute=50, hour=200, day=300, month=500)
@owner_required
def invite_request_email(api_user, nick, email):
  """Create an invitation for the actor, and handle notification.
  PARAMETERS:
    nick - the usual
    email - Email address for new user
  RETURNS: Reference to the added invite
  """
  validate.email(email)
  # TODO(termie): check to make sure this user doesn't already
  #               exist and the invite doesn't
  #               if either do we'll do something different

  code = util.generate_uuid()
  from_actor_ref = actor_get(api_user, nick)

  invite_ref = Invite(
      code=code,
      email=email,
      from_actor=from_actor_ref.nick,
      for_actor=from_actor_ref.nick,
      # to_actor omitted, we are inviting an email address not an actor
  )

  invite_ref.put()

  subject, message, html_message = mail.email_invite(from_actor_ref,
                                                     invite_ref.code)
  email_send(ROOT, email, subject, message, html_message=html_message)

  return invite_ref

#######
#######
#######

@throttled(minute=10, hour=20, day=50)
def login_forgot(api_user, nick_or_email):
  # This call should be made when the user is not logged in, so pass ROOT for
  # api_user to all subsequent calls.

  if patterns.EMAIL_COMPILED.match(nick_or_email):
    # This is an email address.  
    # Does it map to a user? (confirmed email)
    actor_ref = actor_lookup_email(ROOT, nick_or_email)
    
    # Is it an unconfirmed email, and does it map to exactly one user?
    if not actor_ref:
      activations = activation_get_by_email(ROOT, nick_or_email)
      if not activations:
        raise exception.ApiException(
            0x00, 'Email does not match any accounts')
      if len(activations) != 1:
        raise exception.ApiException(
            0x00, 'Email matches more than one account')
      actor_ref = actor_get(ROOT, activations[0].actor)
  else: 
    actor_ref = actor_lookup_nick(ROOT, nick_or_email)
    if not actor_ref:
      raise exception.ApiNotFound('User not found: %s' % nick_or_email) 
    
  # Get the user's email.  First, has it been confirmed?
  email = email_get_actor(ROOT, actor_ref.nick)

  if not email:
    # Do they have any unconfirmed emails?
    activation_refs = activation_get_actor_email(ROOT, actor_ref.nick)
    
    if not activation_refs:
      raise exception.ApiException(
          0x00, 'This user does not have an email address!')
    elif len(activation_refs) != 1:
      raise exception.ApiException(
          0x00, 'This email address maps to multiple users!')
    
    # At this point, we have an unconfirmed email address which maps to exactly
    # one user.
    email = activation_refs[0].content

  # Add a 'please reset this password' item to the DB.
  activation_ref = activation_create(ROOT, actor_ref.nick, 'password_lost', 
                                      email)

  # The code itself is boring.
  code = util.hash_generic(activation_ref.code)
  
  # Inform the user about their thoughtlessness.
  (subject, message, html_message) = mail.email_lost_password(actor_ref, email, code)
  mail.send(email, subject, message, html_message=html_message)

def login_reset(api_user, email, hash):
  actor_ref = actor_lookup_email(ROOT, email)

  # Is it an unconfirmed email, and does it map to exactly one user?
  if not actor_ref:
    activations = activation_get_by_email(ROOT, email)
    if not activations:
      raise exception.ApiException(
          0x00, 'Email does not match any accounts')
    if len(activations) != 1:
      raise exception.ApiException(
          0x00, 'Email matches more than one account')
    actor_ref = actor_get(ROOT, activations[0].actor)

  if not actor_ref:
    raise exception.ApiException(
        0x00, 'This email alias doesn\'t match a user.')

  activation_ref = activation_get(ROOT, actor_ref.nick, 'password_lost', email)

  # The user didn't lose their password
  if not activation_ref:
    raise exception.ApiException(0x00, 'Invalid request')
  
  # The hash doesn't match
  if util.hash_generic(activation_ref.code) != hash:
    raise exception.ApiException(0x00, 'Invalid request, hash does not match')

  # Generate a new password
  password = util.generate_password()
  
  # Update our records
  password_hash = util.hash_password(actor_ref.nick, password)
  actor_ref.password = password_hash
  actor_ref.put()
  activation_ref.delete()
  
  return password, actor_ref.nick

#######
#######
#######

@admin_required
def mobile_associate(api_user, nick, mobile):
  actor_ref = actor_get(api_user, nick)

  # XXX start transaction
  if actor_lookup_mobile(api_user, mobile):
    raise exception.ApiException(0x00, 'Mobile number already in use')

  # clear old mobile numbers
  # TODO(termie): support multiple mobile numners
  old_query = Relation.gql('WHERE owner = :1 AND relation = :2',
                           actor_ref.nick,
                           'mobile')
  for rel_ref in old_query:
    rel_ref.delete()

  relation_ref = Relation(
      owner=actor_ref.nick,
      relation='mobile',
      target=mobile,
      )

  relation_ref.put()
  # XXX end transaction

  return relation_ref

@admin_required
def mobile_confirm_doubleoptin(api_user, nick):
  actor_ref = actor_get(api_user, nick)
  if actor_ref.extra.get('sms_double_opt_in', None):
    del actor_ref.extra['sms_double_opt_in']
  actor_ref.put()
  return actor_ref

@admin_required
def mobile_disassociate(api_user, nick, mobile):
  actor_ref = actor_get(ROOT, nick)

  key_name = Relation.key_from(relation='mobile',
                               owner=nick,
                               target=mobile)
  rel_ref = Relation.get_by_key_name(key_name)
  rel_ref.delete()
  return

@owner_required
def mobile_get_actor(api_user, nick):
  nick = clean.nick(nick)
  query = Relation.gql('WHERE owner = :1 AND relation = :2',
                       nick,
                       'mobile')
  rel_ref = query.get()
  if rel_ref:
    return rel_ref.target
  return None

#######
#######
#######

def oauth_authorize_request_token(api_user, key, actor, perms="read"):
  # TODO validate perms
  # TODO privacy
  token_ref = oauth_get_request_token(api_user, key)
  token_ref.authorized = 1
  token_ref.actor = actor
  token_ref.perms = perms
  token_ref.put()

@admin_required
def oauth_generate_access_token(api_user, consumer_key, request_token_key):
  consumer_ref = oauth_get_consumer(api_user, consumer_key)
  if not consumer_ref:
    raise Exception("bad consumer")
  request_token_ref = oauth_get_request_token(ROOT, request_token_key)
  if not request_token_ref.authorized:
    raise Exception("unauthorized token")

  params = {"key_": util.generate_uuid(),
            "secret": util.generate_uuid(),
            "consumer": consumer_ref.key_,
            "actor": request_token_ref.actor,
            "perms": request_token_ref.perms,
            }

  token_ref = OAuthAccessToken(**params)
  token_ref.put()
  return token_ref

@admin_required
def oauth_get_root_consumer_access_token(api_user, nick):
  query = OAuthAccessToken.gql('WHERE actor = :1 AND consumer = :2',
                               nick, settings.ROOT_CONSUMER_KEY)
  existing = query.get()
  if existing:
    return existing

  params = {"key_": util.generate_uuid(),
            "secret": util.generate_uuid(),
            "consumer": settings.ROOT_CONSUMER_KEY,
            "actor": nick,
            "perms": "write",
            }

  token_ref = OAuthAccessToken(**params)
  token_ref.put()
  return token_ref


@owner_required
def oauth_generate_consumer(api_user, nick):
  nick = clean.nick(nick)
  # TODO(termie): not doing anything fancy yet, all keys are the same types
  # TODO(termie): validation
  #     not too many keys
  key_ = util.generate_uuid()

  params = {'key_': key_,
            'secret': util.generate_uuid(),
            'actor': nick,
            'status': 'active',
            'type': 'desktop',
            'commercial': 0,
            }

  token_ref = OAuthConsumer(**params)
  token_ref.put()
  return token_ref

@owner_required
def oauth_consumer_delete(api_user, nick, consumer_key):
  """Removes the oauth consumer key"""
  consumer_ref = oauth_get_consumer(api_user, consumer_key)
  if not consumer_ref:
    raise Exception("bad consumer")
  consumer_ref.delete()

@owner_required
def oauth_consumer_update(api_user, nick, consumer_key, app_name,
                          consumer_type='desktop'):
  consumer_type = clean.oauth_type(consumer_type)
  consumer_ref = oauth_get_consumer(api_user, consumer_key)
  if not consumer_ref:
    raise Exception("bad consumer")

  consumer_ref.app_name = app_name
  consumer_ref.type = consumer_type
  consumer_ref.put()
  return consumer_ref

@admin_required
def oauth_generate_request_token(api_user, consumer_key):
  consumer_ref = oauth_get_consumer(api_user, consumer_key)
  if not consumer_ref:
    raise Exception("bad consumer")
  params = {"key_": util.generate_uuid(),
            "secret": util.generate_uuid(),
            "consumer": consumer_ref.key_,
            "authorized": 0,
            }

  token_ref = OAuthRequestToken(**params)
  token_ref.put()
  return token_ref

def oauth_revoke_access_token(api_user, key):
  # ROOT for now, we're checking access a little down the line here
  token_ref = oauth_get_access_token(ROOT, key)

  if not token_ref:
    raise exception.ApiException(0x00, "Token does not exist")

  # Verify that this token belongs to the specified user.
  if token_ref.actor != api_user.nick:
    raise exception.ApiException(0x00, "Token does not belong to actor")

  token_ref.delete()

@admin_required
def oauth_get_access_token(api_user, key):
  key_name = OAuthAccessToken.key_from(key_=key)
  return OAuthAccessToken.get_by_key_name(key_name)

@owner_required
def oauth_get_actor_consumers(api_user, nick):
  nick = clean.nick(nick)

  query = OAuthConsumer.gql('WHERE actor = :1 ORDER BY created_at', nick)
  return list(query.run())

@owner_required
def oauth_get_actor_tokens(api_user, nick):
  nick = clean.nick(nick)

  query = OAuthAccessToken.gql(
      'WHERE actor = :1 ORDER BY created_at', nick)
  return list(query.run())

# TODO(termie): owner_required_by_consumer_key ?
def oauth_get_consumer(api_user, key):
  key_name = OAuthConsumer.key_from(key_=key)
  key_ref = OAuthConsumer.get_by_key_name(key_name)
  if not key_ref:
    return None

  actor_ref = actor_get(ROOT, key_ref.actor)
  if not actor_owns_actor(api_user, actor_ref):
    raise exception.ApiException(exception.PRIVACY_ERROR,
                                 'Only allowed to view your own API keys')
  return key_ref

@admin_required
def oauth_get_request_token(api_user, key):
  key_name = OAuthRequestToken.key_from(key_=key)
  return OAuthRequestToken.get_by_key_name(key_name)

#######
#######
#######


@write_required
@owner_required
def post(api_user, _task_ref=None, **kw):
  """ Post a new entry
  
  This will attempt to infer if you are attempting to post to a
  channel (prefixing the message with #channel)

  PARAMS:
    * message - the title of your entry
    * location - free form location for this entry
    * icon - the web icon for this icon
    * nick - the actor posting this entry
    * uuid - a unique identifier for this entry
  
  RETURNS: entry_ref

  
  
  """
  # grab the params we're interested in
  message = kw.get('message', '').strip()
  location = kw.get('location', '')
  icon = clean.icon(kw.get('icon', 0))
  generated = kw.get('generated', 0)
  uuid = kw.get('uuid', util.generate_uuid())
  nick = clean.nick(kw.get('nick', ''))
  extra = {}
  # Thumbnails are not yet shown on the site but are supported by the mobile
  # client.
  thumbnail_url = kw.get('thumbnail_url', None)
  if thumbnail_url:
    extra['thumbnail_url'] = clean.url(thumbnail_url)

  channel_post_match = channel_post_re.search(message)
  if channel_post_match:
    match_dict = channel_post_match.groupdict()
    channel = match_dict['channel']
    message = match_dict['message']
    new_kw = kw.copy()
    new_kw['channel'] = channel
    new_kw['message'] = message
    new_kw['extra'] = extra
    return channel_post(api_user, **new_kw)

  if len(message) > MAX_POST_LENGTH:
    message = message[:MAX_POST_LENGTH]

  try:
    validate.length(message, 1, MAX_POST_LENGTH)
    validate.location(location)
    validate.uuid(uuid)
  except exception.ValidationError, e:
    raise exception.ApiException(0x00, e.user_message)

  if generated:
    # TODO(termie): update the presence, yo
    # update presence only
    return
  
  if settings.QUEUE_ENABLED:
    task_ref = _task_ref
    if not task_ref:
      kw['uuid'] = uuid
      task_ref = task_get_or_create(api_user,
                                    nick,
                                    'post',
                                    uuid,
                                    kw=kw)


  # we've decided this is a presence update
  stream_ref = stream_get_presence(api_user, nick)
  actor_ref = actor_get(api_user, nick)
  extra['title'] = message
  extra['location'] = location
  extra['icon'] = icon

  values = {
    'stream': stream_ref.key().name(),
    'uuid': uuid,
    'owner': stream_ref.owner,
    'actor': actor_ref.nick,
    'extra': extra
  }

  if settings.QUEUE_ENABLED:
    try:
      entry_ref = _process_new_entry_with_progress(
          task_ref, actor_ref, stream_ref, values)
    except exception.ApiException:
      # Something is wrong, bail out and delete the task
      task_ref.delete()
      raise
  else:
    # XXX start transaction
    #presence = _set_presence(**values)
    entry_ref = _add_entry(stream_ref, new_values=values)
    subscribers = _subscribers_for_entry(stream_ref, entry_ref)
    inboxes = _add_inboxes_for_entry(subscribers, stream_ref, entry_ref)
    _notify_subscribers_for_entry(subscribers, 
                                  actor_ref, 
                                  stream_ref, 
                                  entry_ref)
    # XXX end transaction

  return entry_ref

#######
#######
#######

@public_owner_or_contact
def presence_get(api_user, nick, at_time=None):
  """returns the presence for the given actor if the current can view"""
  nick = clean.nick(nick)
  if not at_time:
    # Get current presence
    key_name = 'presence/%s/current' % nick
    presence = Presence.get_by_key_name(key_name)
    if not presence:
      # We did not always create presence from posts
      presence_stream = stream_get_presence(api_user, nick)
      latest_post = StreamEntry.gql(
          'WHERE stream = :1 ORDER BY created_at DESC',
          presence_stream.key().name()).get()
      if latest_post:
        presence = Presence(actor=nick,
                            uuid=latest_post.uuid,
                            updated_at=latest_post.created_at,
                            extra={'presenceline': {
                                'description': latest_post.extra['title'],
                                'since': latest_post.created_at}})
  else:
    presence = Presence.gql(
        u"WHERE actor = :1 AND updated_at <= :2 ORDER BY updated_at DESC",
        nick, at_time).get()
  return ResultWrapper(presence, presence=presence)

def presence_get_safe(api_user, nick, at_time=None):
  try:
    return presence_get(api_user, nick, at_time)
  except exception.ApiException:
    return None

def presence_get_actors(api_user, nicks):
  """returns the presence for the nicks given"""
  o = {}
  nicks = list(set(nicks))
  if not nicks:
    return o

  for nick in nicks:
    o[nick] = presence_get_safe(api_user, nick)
  return ResultWrapper(o, actors=o)

@owner_required
def presence_get_contacts(api_user, nick, since_time=None, limit=200):
  """returns the presence for the given actor's contacts"""
  nick = clean.nick(nick)
  limit = clean.limit(limit, 200)
  if since_time:
    since_time = clean.datetime(since_time)
  o = []
  # This isn't really general-purpose as it will limit us to as many contacts
  # as can be fetched in one go.
  # TODO(mikie): make this api paged.
  # The reason we still want it is that the mobile client wants as much
  # presence as possible but can't handle more than 200 contacts anyway.
  contacts = actor_get_contacts(api_user, nick, limit=limit)
  contacts.append(nick)
  presences = presence_get_actors(api_user, contacts)
  for nick, presence in presences.items():
    if presence:
      if not since_time or presence.updated_at > since_time:
        actor_ref = actor_get(api_user, nick)
        presence.extra['given_name'] = actor_ref.extra.get('given_name', '')
        presence.extra['family_name'] = actor_ref.extra.get('family_name', '')
        o.append(presence)

  return ResultWrapper(o, contacts=o)

@throttled(minute=30, hour=1200, day=4000, month=20000)
@write_required
@owner_required
def presence_set(api_user, nick, **kw):
  """Presence has three timestamp-like fields:

  updated_at is the moment we got the data and can be used to pull 'changed
  since' presence based on a timestamp the caller has previously received.

  uuid is the identifier for this set of data. It can be used to distinguish
  between data you've already seen from new data even if updated_at is close to
  propagation delay.

  senders_timestamp (in extra) is the time the data was created in the
  originating system. It should be used for deciding or displaying freshness.
  """

  nick = clean.nick(nick)
  updated_at  = utcnow()
  uuid = kw.pop('uuid', util.generate_uuid())
  previous_presence = presence_get(api_user, nick)

  extra = {}
  if previous_presence:
    extra = previous_presence.extra
  extra.update(kw)

  validate.user_nick(nick)
  validate.presence_extra(extra)
  params = {'actor': nick,
            'updated_at': updated_at,
            'uuid': uuid,
            'extra': extra,
            'key_name': 'presence/%s/current' % nick}
  presence = Presence(**params)
  presence.put()
  # TODO(tyler): Clean this so an API call doesn't fill the DB.
  params['key_name'] = 'presence/%s/history/%s' % (nick, updated_at)
  presence_history = Presence(**params)
  presence_history.put()
  return ResultWrapper(presence, presence=presence)


#######
#######
#######

@owner_required
def task_create(api_user, nick, action, action_id, args=None, kw=None, 
                progress=None, expire=None):
  if args is None:
    args = []
  if kw is None:
    kw = {}
  
  key_name = Task.key_from(actor=nick, action=action, action_id=action_id)

  if expire:
    locked = memcache.client.add(key_name, 'owned', time=expire)
    if not locked:
      raise exception.ApiLocked("Lock could not be acquired: %s" % key_name)

  task_ref = Task(actor=nick,
                  action=action,
                  action_id=action_id,
                  expire=None,
                  args=args,
                  kw=kw,
                  progress=progress
                  )
  task_ref.put()
  return task_ref

@owner_required
def task_get(api_user, nick, action, action_id, expire=DEFAULT_TASK_EXPIRE):
  """ attempts to acquire a lock on a queue item for (default) 10 seconds """
  
  key_name = Task.key_from(actor=nick, action=action, action_id=action_id)

  # TODO(termie): this could probably be a Key.from_path action
  q = Task.get_by_key_name(key_name)
  if not q:
    raise exception.ApiNotFound(
        'Could not find task: %s %s %s' % (nick, action, action_id))

  locked = memcache.client.add(key_name, 'owned', time=expire)
  if not locked: 
    raise exception.ApiLocked("Lock could not be acquired: %s" % key_name)

  return q

@owner_required
def task_get_or_create(api_user, nick, action, action_id, args=None, 
                       kw=None, progress=None, expire=DEFAULT_TASK_EXPIRE):
  try:
    task_ref = task_get(api_user, nick, action, action_id, expire)
  except exception.ApiNotFound:
    task_ref = task_create(api_user, 
                           nick, 
                           action, 
                           action_id, 
                           args, 
                           kw, 
                           progress, 
                           expire=expire)
  return task_ref
    

#@throttled(minute=30, hour=1200, day=4000, month=20000)
@owner_required
def task_process_actor(api_user, nick):
  nick = clean.nick(nick)
  return task_process_any(ROOT, nick)
 
@admin_required   
def task_process_any(api_user, nick=None):
  # Basing this code largely off of pubsubhubbub's queueing approach
  # Hard-coded for now, these will get moved up
  work_count = 1
  sample_ratio = 10
  lock_ratio = 4
  lease_period = DEFAULT_TASK_EXPIRE
  sample_size = work_count * sample_ratio

  if nick:
    query = Task.gql('WHERE actor = :1 ORDER BY created_at',
                     nick)
  else:
    query = Task.gql('ORDER BY created_at')
  
  work_to_do = query.fetch(sample_size)
  if not work_to_do:
    raise exception.ApiNoTasks('No tasks')

  # From pubsububhub:
  # Attempt to lock more work than we actually need to do, since there likely
  # will be conflicts if the number of workers is high or the work_count is
  # high. If we've acquired more than we can use, we'll just delete the memcache
  # key and unlock the work. This is much better than an iterative solution,
  # since a single locking API call per worker reduces the locking window.
  possible_work = random.sample(work_to_do,
                                min(len(work_to_do), 
                                    lock_ratio * work_count)
                                )
  work_map = dict([(str(w.key().name()), w) for w in possible_work])
  try_lock_map = dict((k, 'owned') for k in work_map)
  not_set_keys = set(memcache.client.add_multi(try_lock_map, time=lease_period))
  if len(not_set_keys) == len(try_lock_map):
    return
  
  locked_keys = [k for k in work_map if k not in not_set_keys]
  reset_keys = locked_keys[work_count:]
  if reset_keys and not memcache.client.delete_multi(reset_keys):
    logging.warning('Could not reset acquired work for model %s: %s',
                    'Task', reset_keys)

  work = [work_map[k] for k in locked_keys[:work_count]]
  
  for task_ref in work:
    logging.info("Processing task: %s %s %s p=%s", 
                  task_ref.actor,
                  task_ref.action, 
                  task_ref.action_id,
                  task_ref.progress
                  )

    try:
      actor_ref = actor_get(ROOT, task_ref.actor)

      method_ref = PublicApi.get_method(task_ref.action)

      rv = method_ref(actor_ref, 
                      _task_ref = task_ref, 
                      *task_ref.args, 
                      **task_ref.kw)

    except exception.ApiDeleted:
      logging.warning('Owner or target of task has been deleted. Removing task.')
      task_ref.delete()
      return

  return
  

@owner_required
def task_remove(api_user, nick, action, action_id):
  key_name = Task.key_from(actor=nick, action=action, action_id=action_id)
  
  q = Task.get_by_key_name(key_name)
  if not q:
    raise exception.ApiNotFound(
        'Could not find task: %s %s %s' % (nick, action, action_id))

  # clear up any residual locks
  q.delete()
  memcache.client.delete(key_name)

  return True

@owner_required
def task_update(api_user, nick, action, action_id, progress=None, unlock=True):
  """ update the progress for a task and possibly unlock it """
  key_name = Task.key_from(actor=nick, action=action, action_id=action_id)

  q = Task.get_by_key_name(key_name)
  if not q:
    raise exception.ApiNotFound(
        'Could not find task: %s %s %s' % (nick, action, action_id))
  
  q.progress = progress
  q.put()

  if unlock:
    memcache.client.delete(key_name)

  return q



#######
#######
#######

# TODO(termie): STUB
@admin_required
def sms_receive(api_user, **kw):
  pass

@admin_required
def sms_send(api_user, on_behalf, mobile, message):
  # TODO(termie): do filtering, throttling, and whatnot based on on_behalf
  sms_connection = sms.SmsConnection()
  sms_connection.send_message([mobile], message)

#######
#######
#######

@owner_required
def settings_change_notify(api_user, nick, **kw):
  actor_ref = actor_get(api_user, nick)

  # Convert to boolean
  email_notifications = kw.get('email', False) and True
  actor_ref.extra['email_notify'] = email_notifications

  im_notifications = kw.get('im', False) and True
  actor_ref.extra['im_notify'] = im_notifications

  sms_notifications = kw.get('sms', False) and True
  actor_ref.extra['sms_notify'] = sms_notifications

  actor_ref.put()
  return actor_ref

@owner_required
def settings_change_password(api_user, nick, new_password):
  validate.password(new_password)
  actor_ref = actor_get(api_user, nick)
  actor_ref.password = util.hash_password(actor_ref.nick, new_password)
  actor_ref.put()
  return actor_ref

@throttled(minute=2, hour=5, day=10)
@owner_required
def settings_change_privacy(api_user, nick, privacy):
  privacy = int(privacy)

  # XXX start transaction
  actor_ref = actor_get(api_user, nick)
  actor_ref.privacy = privacy
  actor_ref.put()

  # update all the related streams and subscriptions
  streams = stream_get_actor(api_user, nick)
  for s in streams:
    if s.type != 'comments':
      s.read = privacy
      s.put()
  # XXX end transaction

@owner_required
def settings_hide_comments(api_user, hide_comments, nick):
  actor_ref = actor_get(api_user, nick)

  actor_ref.extra['comments_hide'] = hide_comments == '1'
  actor_ref.put()

  # TODO(tyler): It seems odd to return actor_ref from these functions...
  return actor_ref

@owner_required
def settings_update_account(api_user, nick, **kw):
  # note: the only thing we care about at this point is full_name
  params = {'given_name': kw.get('given_name', kw.get('first_name', '')),
            'family_name': kw.get('family_name', kw.get('last_name', ''))}
  validate.name(params['given_name'], "Your First Name", 'given_name')
  validate.name(params['family_name'], "Your Last Name", 'family_name')

  actor_ref = actor_get(api_user, nick)
  actor_ref.extra.update(params)
  actor_ref.put()

  return actor_ref

#TODO
@owner_required
def settings_update_email(api_user, nick, email):
  pass

#######
#######
#######

@throttled(minute=3, hour=20, day=30, month=40)
@write_required
@owner_required
def stream_create(api_user, **kw):
  # TODO make sure user is allowed to do this
  # TODO make sure this stream doesn't already exist
  # TODO(mikie): inherit privacy from actor?
  # TODO(tyler): Safety-check kw (so it doesn't blindly pass to extra)
  params = {"owner": kw.get('owner'),
            'title': kw.get('title', ''),
            'type': kw.get('type', 'presence'),
            'read': kw.get('read', PRIVACY_PUBLIC),
            'write': kw.get('write', PRIVACY_PRIVATE),
            'extra': kw.get('extra', {}),
            'slug': kw.get('slug', util.generate_uuid())
            }

  stream_ref = Stream(**params)
  stream_ref.put()
  return stream_ref

@write_required
@owner_required
def stream_create_comment(api_user, nick):
  """ create a default comments stream for the supplied actor """
  actor_ref = actor_get(api_user, nick)

  comments_params = {"owner": actor_ref.nick,
                     "title": "comments",
                     "type": "comment",
                     "slug": "comments",
                     "read": PRIVACY_PRIVATE,
                     "write": PRIVACY_PRIVATE,
                     "extra": {},
                     "slug": "comments",
                     }

  comments_stream_ref = stream_create(api_user, **comments_params)
  return comments_stream_ref

@write_required
@owner_required
def stream_create_presence(api_user, nick, read_privacy=PRIVACY_PUBLIC,
                           write_privacy=PRIVACY_PRIVATE):
  actor_ref = actor_get(api_user, nick)

  presence_params = {"owner": actor_ref.nick,
                     "title": "presence",
                     "type": "presence",
                     "slug": "presence",
                     "read": read_privacy,
                     "write": write_privacy,
                     "extra": {},
                     "slug": "presence",
                     }

  presence_stream_ref = stream_create(api_user, **presence_params)
  return presence_stream_ref

@public_owner_or_contact_by_stream
def stream_get(api_user, stream):
  stream_ref = Stream.get_by_key_name(stream)
  
  not_found_message = 'Stream not found: %s' % stream

  if not stream_ref:
    raise exception.ApiNotFound(not_found_message)

  if stream_ref.is_deleted():
    raise exception.ApiDeleted(not_found_message)

  try:
    # ensure the stream owner exists
    actor_get(api_user, stream_ref.owner)
  except exception.ApiDeleted:
    raise exception.ApiDeleted(not_found_message)
  except exception.ApiNotFound:
    raise exception.ApiNotFound(not_found_message)
  
  return stream_ref

@public_owner_or_contact
def stream_get_actor(api_user, nick):
  query = Stream.gql('WHERE owner = :1', nick)
  return list(query.run())

@public_owner_or_contact
def stream_get_comment(api_user, nick):
  """ stream/nick/comments """
  nick = clean.nick(nick)
  key_name = Stream.key_from(owner=nick, slug='comments')
  comment_stream = Stream.get_by_key_name(key_name)
  if not comment_stream:
    raise exception.ApiException(0x00, 'Stream not found')
  return comment_stream

@public_owner_or_contact
def stream_get_presence(api_user, nick):
  """ Queries the Stream entities to find the Stream corresponding to
  api_user's presence stream.

  The returned value should be the "stream/<nick>/presence" stream.
  """
  nick = clean.nick(nick)
  key_name = Stream.key_from(owner=nick, slug='presence')
  presence_stream = Stream.get_by_key_name(key_name)
  if not presence_stream:
    raise exception.ApiException(0x00, 'Stream not found')
  return presence_stream

# depends on stream_get's privacy
def stream_get_streams(api_user, streams):
  o = {}
  if not streams:
    return o

  streams = list(set(streams))
  for stream in streams:
    stream_ref = stream_get_safe(api_user, stream)
    if stream_ref:
      o[stream] = stream_ref

  return o

def stream_get_safe(api_user, stream):
  """stream_get that returns None on privacy exceptions"""
  try:
    stream_ref = stream_get(api_user, stream)
  except exception.ApiException:
    return None
  return stream_ref

def stream_is_private(api_user, stream):
  stream_ref = stream_get(ROOT, stream)
  if stream_ref.read < PRIVACY_PUBLIC:
    return True
  return False

#######
#######
#######

@owner_required_by_target
def subscription_exists(api_user, topic, target):
  key_name = Subscription.key_from(topic=topic, target=target)
  sub_ref = Subscription.get_by_key_name(key_name)
  if not sub_ref:
    return False
  return True

@owner_required_by_target
def subscription_get(api_user, topic, target):
  key_name = Subscription.key_from(topic=topic, target=target)
  sub_ref = Subscription.get_by_key_name(key_name)
  return sub_ref

@admin_required
def subscription_get_topic(api_user, topic, limit=100, offset=None):
  """ returns the subscriptions for the given topic (usually a stream)

  """
  # TODO(termie): this will mean when paging that people with lower nicknames
  #               tend to receive things first, I'd prefer to order by
  #               created_at but that will take a couple mods in other places
  query = Subscription.Query().order('target').filter('topic =', topic)
  if offset is not None:
    query.filter('target >', offset)
  return query.fetch(limit)

@owner_required_by_target
def subscription_is_active(api_user, topic, target):
  key_name = Subscription.key_from(topic=topic, target=target)
  sub_ref = Subscription.get_by_key_name(key_name)
  if not sub_ref:
    return False

  # if the stream is contacts-only check the state
  if stream_is_private(ROOT, topic) and sub_ref.state != "subscribed":
    return False
  return True

@delete_required
@owner_required_by_target
def subscription_remove(api_user, topic, target):
  key_name = Subscription.key_from(topic=topic, target=target)
  sub_ref =  Subscription.get_by_key_name(key_name)
  if not sub_ref:
    return
  sub_ref.delete()
  return sub_ref

@throttled(minute=50, hour=200, day=1000, month=2000)
@write_required
@owner_required_by_target
def subscription_request(api_user, topic, target):
  target_nick = util.get_user_from_topic(target)
  topic_nick = util.get_user_from_topic(topic)

  if topic_nick is None:
    raise exception.ApiException(0, 'Subscription topic must include username')

  target_ref = actor_get(api_user, target_nick)
  topic_ref = actor_get(api_user, topic_nick)

  # TODO(termie): We'd also like to support blocking subscription requests
  #               and should probably make a state similar to 'rejected',
  #               though, XEP-0060 sect 4.2. doesn't have a 'rejected' state
  #               so returning one might confuse pub-sub folk

  if actor_can_view_actor(target_ref, topic_ref):
    state = 'subscribed'
  else:
    state = 'pending'
  # TODO(termie) send an error back and set 'unconfigured' state appropriately

  # if the subscription already exists we probably don't have to do anything
  existing_ref = subscription_get(api_user, topic, target)
  if existing_ref:
    # if they were in a pending state but are for some reason now
    # allowed to complete the subscripton upgrade, but don't downgrade
    # if the reverse is true as the subscripton may have been confirmed
    # by the topic's actor
    if existing_ref.state == 'pending' and state == 'subscribed':
      existing_ref.state = state
      existing_ref.put()
    return existing_ref

  sub_ref = Subscription(topic=topic,
                         subscriber=target_ref.nick,
                         target=target,
                         state=state,
                         )
  sub_ref.put()
  return sub_ref

#TODO
def subscription_set_notify(api_user, topic, nick, target, notify):
  """ changes the notification settings for a given subscription """
  pass

#######
#######
#######

@admin_required
def user_cleanup(api_user, nick):
  """ attempts to fx any users that have been left in an unstable state
  """
  actor_ref = actor_get(api_user, nick)
  if not actor_ref.normalized_nick:
    actor_ref.normalized_nick = actor_ref.nick.lower()
    actor_ref.put()

  try:
    presence_stream_ref = stream_get_presence(api_user, actor_ref.nick)
  except exception.ApiException:
    stream_create_presence(api_user,
                           actor_ref.nick,
                           read_privacy=actor_ref.privacy)

  try:
    comment_stream_ref = stream_get_comment(api_user, actor_ref.nick)
  except exception.ApiException:
    stream_create_comment(api_user, actor_ref.nick)

@admin_required
def user_create(api_user, **kw):
  nick = kw.get('nick')
  nick = clean.nick(nick)
  params = {
    'nick': nick,
    'normalized_nick': nick.lower(),
    'privacy': kw.get('privacy', PRIVACY_PUBLIC),
    'type': 'user',
    'password': kw.get('password', ''),
    'extra': {
      'given_name': kw.get('given_name', kw.get('first_name', '')),
      'family_name': kw.get('family_name', kw.get('last_name', '')),
      'sms_double_opt_in': True,
    },
  }

  # validate
  validate.not_banned_name(params['nick'])
  validate.privacy(params['privacy'])
  validate.password(params['password'])
  validate.name(params['extra']['given_name'], "Your First Name", 'given_name')
  validate.name(params['extra']['family_name'], "Your Last Name", 'family_name')

  params['password'] = util.hash_password(params['nick'], params['password'])

  try:
    existing_ref = actor_lookup_nick(ROOT, nick)
  except exception.ApiDeleted:
    existing_ref = True
  except exception.ApiException:
    existing_ref = False

  if existing_ref:
    raise exception.ValidationError(
        'Screen name %s is already in use.' % util.display_nick(nick))

  # Create the user
  actor = Actor(**params)
  actor.put()

  # Create the streams
  presence_stream = stream_create_presence(api_user,
                                           actor.nick,
                                           read_privacy=params['privacy'])
  comments_stream = stream_create_comment(api_user, actor.nick)

  # Add the contact
  rel = actor_add_contact(actor, actor.nick, ROOT.nick)

  return actor

@admin_required
def user_create_root(api_user):
  nick = ROOT.nick
  params = {'nick': nick,
            'normalized_nick': nick.lower(),
            'privacy': PRIVACY_PUBLIC,
            'type': 'user',
            'password': None,
            'extra': {}
            }

  try:
    existing_ref = actor_lookup_nick(ROOT, nick)
  except exception.ApiDeleted:
    existing_ref = True
  except exception.ApiException:
    existing_ref = False

  if existing_ref:
    raise exception.ValidationError(
        'Screen name %s is already in use.' % util.display_nick(nick))

  # Create the user
  actor = Actor(**params)
  actor.put()

  # Create the streams
  presence_stream = stream_create_presence(api_user,
                                           actor.nick,
                                           read_privacy=params['privacy'])
  comments_stream = stream_create_comment(api_user, actor.nick)

  # Add the contact
  rel = actor_add_contact(actor, actor.nick, ROOT.nick)

  return actor

@admin_required
def user_authenticate(api_user, nick, nonce, digest):
  actor_ref = actor_get(api_user, nick)

  logging.info("nonce %s digest %s password %s"%(nonce, digest,
                                                 actor_ref.password))

  if digest == util.sha1(nonce + actor_ref.password):
    return oauth_get_root_consumer_access_token(api_user, nick)
  elif (settings.MANAGE_PY and
        digest == util.sha1(nonce + util.sha1(actor_ref.password))):
    return oauth_get_root_consumer_access_token(api_user, nick)
  else:
    return PrimitiveResultWrapper(False)


#######
#######
#######

# Helper class
class PublicApi(object):
  methods = {"post": post,
             "actor_add_contact": actor_add_contact,
             "actor_get": actor_get,
             "actor_get_contacts_avatars_since":
                 actor_get_contacts_avatars_since,
             "entry_add_comment": entry_add_comment,
             "entry_get_actor_overview": entry_get_actor_overview,
             "entry_get_actor_overview_since": entry_get_actor_overview_since,
             }

  # Private methods are externally accessible but whose design has not been
  # finalized yet and may change in the future.
  private_methods = {"entry_add_comment_with_entry_uuid":
                         entry_add_comment_with_entry_uuid,
                     "entry_get_comments_with_entry_uuid":
                         entry_get_comments_with_entry_uuid,
                     "keyvalue_put": keyvalue_put,
                     "keyvalue_get": keyvalue_get,
                     "keyvalue_prefix_list": keyvalue_prefix_list,
                     "presence_get": presence_get,
                     "presence_set": presence_set,
                     "presence_get_contacts": presence_get_contacts,
                     }

  root_methods = {"user_authenticate": user_authenticate,
                  "task_process_actor": task_process_actor
                  }


  @classmethod
  def get_method(cls, name, api_user=None):
    if api_user and api_user.nick == ROOT.nick and name in cls.root_methods:
      return cls.root_methods[name]
    if name in cls.methods:
      return cls.methods[name]
    if name in cls.private_methods:
      return cls.private_methods[name]
    return None

class ResultWrapper(object):
  def __init__(self, raw, **kw):
    self.__dict__['raw'] = raw
    self.__dict__['kw'] = kw

  def __getattr__(self, attr):
    return getattr(self.raw, attr)

  def __setattr__(self, attr, value):
    return setattr(self.raw, attr, value)

  def __nonzero__(self):
    return bool(self.raw)

  def __len__(self):
    return len(self.raw)

  def to_api(self):
    o = {}
    for k, v in self.kw.iteritems():
      if v is None:
        o[k] = {}
      else:
        o[k] = models._to_api(v)
    return o

  def __eq__(self, other):
    # support comparing to other ResultWrappers
    if isinstance(other, self.__class__):
      return self.raw == other.raw
    else:
      return self.raw == other

  def __cmp__(self, other):
    # support comparing to other ResultWrappers
    if isinstance(other, self.__class__):
      return self.raw.__cmp__(other.raw)
    else:
      return self.raw.__cmp__(other)

class PrimitiveResultWrapper(object):
  """ ResultWrapper to be used by boolean responses """
  def __init__(self, primitive):
    self.value = primitive
  
  def to_api(self):
    return self.value

  

# BACKEND

# new squeuel
def _process_new_entry_with_progress(task_ref, actor_ref, new_stream_ref,
                                     new_values, entry_ref=None, 
                                     entry_stream_ref=None):
  """ this is probably one of the more complex pieces of machinery in the
  entire codebase so we'll be being very liberal with comments
    
  task_ref - the task we are currently processing
  actor_ref - the actor who created the new entry
  new_stream_ref - the stream in which the new entry is to be created
  new_values - the values for the new entruy
  entry_ref - if this is a new comment, the entry the new comment is on
  entry_stream_ref - if this is a new comment, the stream of the entry the
                     new comment is on

  """
  #logging.info("Processing task: %s %s %s p=%s", 
  #              task_ref.actor,
  #              task_ref.action, 
  #              task_ref.action_id,
  #              task_ref.progress
  #              )

  # stages: entry - make the entry
  #         iterate inboxes   
  #           actor inboxes
  #           follower inboxes
  #         iterate notifications

  # First we need to figure out which stage we are in based on progress
  progress = task_ref.progress


  # FIRST STAGE: make the entry and initial inbox
  #              we'll also try to make the first set of followers
  if not progress:
    throttle.throttle(
        actor_ref, task_ref.action, minute=10, hour=100, day=500, month=5000)

    # every step of the way we try to do things in a way that will
    # degrade best upon failure of any part, if these first three
    # additions don't go through then there isn't really any entry
    # and the user isn't going to see much until the queue picks
    # it up
    new_entry_ref = _add_entry(new_stream_ref, 
                               new_values, 
                               entry_ref=entry_ref)

    # We're going to need this list all over so that we can remove it from 
    # the other inbox results we get after we've made the first one
    initial_inboxes = _who_cares_web_initial(actor_ref, 
                                             new_entry_ref, 
                                             entry_ref)

    # these are the most important first inboxes, they get the entry to show
    # up for the user that made them and anybody who directly views the
    # author's history
    initial_inboxes_ref = _add_inbox(new_stream_ref, 
                                     new_entry_ref,
                                     initial_inboxes,
                                     shard='owner')
    
    # we've accomplished something useful, bump our progress
    # if this times out the above actions should all handle themselves well
    # we leave the task locked because we hope to still get some more done     
    try:
      task_ref = task_update(ROOT, 
                             task_ref.actor, 
                             task_ref.action, 
                             task_ref.action_id,
                             progress='inboxes:',
                             unlock=False)
    except exception.Error:
      exception.log_exception()


    # Next up will be the inboxes for the overviews of the first bunch
    # of subscribers
    follower_inboxes, more = _who_cares_web(new_entry_ref, 
                                            progress=progress,
                                            skip=initial_inboxes)
    
    last_inbox = _paged_add_inbox(follower_inboxes,
                                  new_stream_ref,
                                  new_entry_ref)

    if not more:
      # We don't have any more followers to add inboxes for but
      # we don't really expect to be able to get the notifications
      # out in this pass also so we're going to let the queue
      # handle them
      next_progress = 'notifications:'
    else:
      # Mark where we are and let the queue handle the rest
      next_progress = 'inboxes:%s' % last_inbox

    # Bump the task and chill out, unlock it for the next eager hands
    try:
      task_ref = task_update(ROOT, 
                             task_ref.actor,
                             task_ref.action,
                             task_ref.action_id,
                             progress=next_progress,
                             unlock=True)
    except exception.Error:
      exception.log_exception()


  # SECOND STAGE: more inboxes!
  elif progress.startswith('inboxes:'):
    # we'll need to get a reference to the entry that has already been created
    entry_keyname = StreamEntry.key_from(**new_values)
    new_entry_ref = entry_get(ROOT, entry_keyname)

    # We're going to need this list all over so that we can remove it from 
    # the other inbox results we get after we've made the first one
    initial_inboxes = _who_cares_web_initial(actor_ref, 
                                             new_entry_ref, 
                                             entry_ref)
    
    my_progress = progress[len('inboxes:'):]
    
    # More followers! Over and over. Like a monkey with a miniature cymbal.
    follower_inboxes, more = _who_cares_web(new_entry_ref, 
                                            progress=my_progress,
                                            skip=initial_inboxes)
    
    last_inbox = _paged_add_inbox(follower_inboxes,
                                  new_stream_ref,
                                  new_entry_ref)
    
    # if that was all of them, bump us up to notifications stage
    if more and last_inbox:
      next_progress = 'inboxes:%s' % last_inbox
    else:
      next_progress = 'notifications:'
    
    try:
      task_ref = task_update(ROOT, 
                             task_ref.actor,
                             task_ref.action,
                             task_ref.action_id,
                             progress=next_progress,
                             unlock=True)
    except exception.Error:
      exception.log_exception()

  # THIRD STAGE: notifications!
  elif progress.startswith('notifications:'):    
    # We'll need to get a reference to the entry that has already been created
    entry_keyname = StreamEntry.key_from(**new_values)
    new_entry_ref = entry_get(ROOT, entry_keyname)

    
    my_progress = progress[len('notifications:'):]
    

    # SUBSTAGES! Oh my!
    if not my_progress:
      my_progress = 'im:'
    
    if my_progress.startswith('im:'):
      my_progress = my_progress[len('im:'):]
      notification_type = 'im'
      next_notification_type = 'sms'
      
      initial_inboxes = _who_cares_im_initial(actor_ref, 
                                              new_entry_ref, 
                                              entry_ref)

      follower_inboxes, more = _who_cares_im(new_entry_ref, 
                                             progress=my_progress,
                                             skip=initial_inboxes)

      # The first time through we'll want to include the initial inboxes, too
      if not my_progress:
        follower_inboxes = initial_inboxes + follower_inboxes

    elif my_progress.startswith('sms:'):
      my_progress = my_progress[len('sms:'):]
      notification_type = 'sms'
      next_notification_type = 'email'

      initial_inboxes = _who_cares_sms_initial(actor_ref, 
                                               new_entry_ref, 
                                               entry_ref)

      follower_inboxes, more = _who_cares_sms(new_entry_ref, 
                                              progress=my_progress,
                                              skip=initial_inboxes)

      # The first time through we'll want to include the initial inboxes, too
      if not my_progress:
        follower_inboxes = initial_inboxes + follower_inboxes

    elif my_progress.startswith('email:'):
      my_progress = my_progress[len('email:'):]
      notification_type = 'email'
      next_notification_type = None
        
      initial_inboxes = _who_cares_email_initial(actor_ref,
                                                 new_entry_ref,
                                                 entry_ref)

      follower_inboxes, more = _who_cares_email(new_entry_ref, 
                                                progress=my_progress,
                                                skip=initial_inboxes)

      # The first time through we'll want to include the initial inboxes, too
      if not my_progress:
        follower_inboxes = initial_inboxes + follower_inboxes
 
    # Back to things that happen regardless of notification type
    last_inbox = None
    if follower_inboxes:
      last_inbox = follower_inboxes[-1]

    # We update the task first so that we don't accidentally send duplicate
    # notifications, it's not ideal but best we can do for now
    if more or next_notification_type:
      if more and last_inbox:
        next_progress = 'notifications:%s:%s' % (notification_type,
                                                 last_inbox)
      else:
        next_progress = 'notifications:%s:' % (next_notification_type)
      
      try:
        task_ref = task_update(ROOT, 
                               task_ref.actor,
                               task_ref.action,
                               task_ref.action_id,
                               progress=next_progress,
                               unlock=True)
      except exception.Error:
        exception.log_exception()

    # That's it! I can hardly believe it.
    else:
      task_remove(ROOT,
                  task_ref.actor, 
                  task_ref.action, 
                  task_ref.action_id
                  )
    
    # perform the notifications
    _notify_subscribers_for_entry_by_type(notification_type,
                                          follower_inboxes,
                                          actor_ref,
                                          new_stream_ref,
                                          new_entry_ref,
                                          entry_ref=entry_ref,
                                          entry_stream_ref=entry_stream_ref
                                          )
  return new_entry_ref

# TODO(termie): what a mess.
def _add_entry(new_stream_ref, new_values, entry_ref=None):
  """Adds an entry to a stream and returns the created StreamEntry object.  """
  # TODO should probably check for previous entries to prevent dupes here

  # TODO check url for feed entries
  # TODO check content for comments
  # TODO check title for basic entries

  # for presence updates, this looks like 'stream/<nick>/presence/NNNN'
  key_name = StreamEntry.key_from(**new_values)

  if entry_get_uuid(ROOT, new_values['uuid']):
    raise exception.ApiException(
        0x00, "Duplicate entry, uuid %s already used" % new_values['uuid'])
    
  # Now the key is uuid and this check duplicates the above, but we will change
  # the key to use the slug later.
  try:
    existing = entry_get(ROOT, key_name)
  except exception.ApiDeleted:
    existing = True
  except exception.ApiException:
    existing = False

  if existing:
    raise exception.ApiException(0x00, "Duplicate entry, key %s already used" %
                                 key_name)

  new_entry_ref = StreamEntry(**new_values)
  _set_location_if_necessary(new_entry_ref)
  new_entry_ref.put()

  # TODO(termie): this can pretty easily get out of sync, we should probably
  #               do something like what we do with follower counts
  if new_entry_ref.is_comment():
    entry_ref.extra.setdefault('comment_count', 0)
    entry_ref.extra['comment_count'] += 1
    entry_ref.put()

    # subscribe the author of the comment to future comments on this entry
    # NOTE: using ROOT because if a user has already commented on this entry
    #       then they can see it to subscribe
    subscripton_ref = subscription_request(
        ROOT,
        topic=entry_ref.keyname(),
        target='inbox/%s/overview' % new_entry_ref.actor
        )
  else:
    if not new_entry_ref.is_channel():
      presence_set(ROOT,
                   new_entry_ref.actor,
                   presenceline={
                     'description': new_entry_ref.extra['title'],
                     'since': new_entry_ref.created_at})

  return new_entry_ref

def _set_location_if_necessary(entry_ref):
  if 'location' in entry_ref.extra and entry_ref.extra['location']:
    return # location is already included
  presence = presence_get_safe(ROOT, entry_ref.actor)
  if not presence:
    return
  if 'location' in presence.extra and presence.extra['location']:
    entry_ref.extra['location'] = presence.extra['location']

def _add_inbox(stream_ref, entry_ref, inboxes, shard):
  #logging.info('add_inbox %s|%s: %s', entry_ref.keyname(), shard, inboxes)
  values = {"stream": entry_ref.stream,
            "stream_type": stream_ref.type,
            "uuid": entry_ref.uuid,
            "created_at": entry_ref.created_at,
            "inbox": inboxes,
            "shard": shard,
            }
  if entry_ref.entry:
    values['entry'] = entry_ref.entry
  inbox_ref = InboxEntry(**values)
  inbox_ref.put()
  return inbox_ref
 
def _who_cares_web(entry_ref, progress=None, limit=None, skip=None):
  """ figure out who wants to see this on the web 
  
  From the who_cares diagram we want

  Cs - comments on entries you wrote IGNORE already covered by initial_inboxes
  Cx - comments entries you've commented on
  Uu - user updates
  Uc - channel updates
  Cu - use comments
  
  Twisting that around in terms of subscribers:
  
  subscribers to the stream for this item: entry_ref.stream (Uu, Uc, Cu)
  if this is a comment, subscribers to the entry: entry_ref.entry (Cx)

  """
  limit = limit is None and MAX_FOLLOWERS_PER_INBOX or limit
  
  topic_keys = [entry_ref.stream]
  if entry_ref.is_comment():
    topic_keys.append(entry_ref.entry)
    entry_stream_ref = stream_get(ROOT, entry_ref.extra.get('entry_stream'))
    actor_ref = actor_get(ROOT, entry_ref.actor)
    is_restricted = (entry_stream_ref.is_restricted() or 
                     actor_ref.is_restricted())
  else:
    stream_ref = stream_get(ROOT, entry_ref.stream)
    is_restricted = stream_ref.is_restricted()

  targets, more = _paged_targets_for_topics(topic_keys,
                                            is_restricted,
                                            progress=progress,
                                            limit=limit)
  if skip:
    targets = [t for t in targets if t not in skip]

  return targets, more

def _who_cares_web_initial(actor_ref, new_entry_ref, entry_ref=None):
  inboxes = []

  # actor-private
  # actor-overview
  # If this is a comment
  #   entry-comments
  #   entry-actor-overview
  #   If actor is public
  #     If not on a channel stream
  #       If on a public stream
  #         actor-contacts
  #         actor-public
  #
  # If this is not a comment
  #   If this is on a channel
  #     channel-private
  #     channel-contacts
  #     If channel is public:
  #       channel-public
  #   If not channel
  #     actor-contacts
  #     If actor is public
  #       actor-public
  #       root-explore

  inboxes.append('inbox/%s/private' % new_entry_ref.actor)
  inboxes.append('inbox/%s/overview' % new_entry_ref.actor)
  if new_entry_ref.is_comment():
    inboxes.append('%s/comments' % new_entry_ref.entry)
    inboxes.append('inbox/%s/overview' % entry_ref.actor)
    if actor_ref.is_public():
      if not new_entry_ref.is_channel():
        inboxes.append('inbox/%s/contacts' % new_entry_ref.actor)
        inboxes.append('inbox/%s/public' % new_entry_ref.actor)
  else:
    if new_entry_ref.is_channel():
      inboxes.append('inbox/%s/private' % new_entry_ref.owner)
      inboxes.append('inbox/%s/contacts' % new_entry_ref.owner)
      channel_ref = actor_get(ROOT, new_entry_ref.owner)
      if channel_ref.is_public():
        inboxes.append('inbox/%s/public' % new_entry_ref.owner)
    else:
      inboxes.append('inbox/%s/contacts' % new_entry_ref.actor)
      if actor_ref.is_public():
        inboxes.append('inbox/%s/public' % new_entry_ref.actor)
        inboxes.append('inbox/%s/explore' % ROOT.nick)

  return inboxes

def _who_cares_im(entry_ref, progress=None, limit=None, skip=None):
  """ who cares about im? the same people as the web! """
  limit = limit is None and MAX_NOTIFICATIONS_PER_TASK or limit
  return _who_cares_web(entry_ref, progress=progress, limit=limit, skip=skip)

def _who_cares_im_initial(actor_ref, new_entry_ref, entry_ref):
  return _who_cares_web_initial(actor_ref, new_entry_ref, entry_ref)

def _who_cares_email(entry_ref, progress=None, limit=None, skip=None):
  """ figure out who wants to get an email about this
  
  From the who_cares diagram we want

  Cs - comments on entries you wrote IGNORE already covered by initial_inboxes
  Cx - comments entries you've commented on
 
  Twisting that around in terms of subscribers:
  
  if this is a comment, subscribers to the entry: entry_ref.entry (Cx)

  """
  limit = limit is None and MAX_NOTIFICATIONS_PER_TASK or limit


  if not entry_ref.is_comment():
    return [], None

  topic_keys = []
  topic_keys.append(entry_ref.entry)
  entry_stream_ref = stream_get(ROOT, entry_ref.extra.get('entry_stream'))
  is_restricted = entry_stream_ref.is_restricted()

  targets, more = _paged_targets_for_topics(topic_keys,
                                            is_restricted,
                                            progress=progress,
                                            limit=limit)

  # we always want to skip the actor who made this action
  # (unless we make that a setting in the future)
  if not skip:
    skip = []
  skip.append('inbox/%s/overview' % entry_ref.actor)

  targets = [t for t in targets if t not in skip]

  return targets, more

def _who_cares_email_initial(actor_ref, new_entry_ref, entry_ref=None):
  # If is a comment and not by the author of the entry it is on
  #   entry-actor-overview (Cs)
  if new_entry_ref.is_comment() and new_entry_ref.actor != entry_ref.actor:
    return ['inbox/%s/overview' % entry_ref.actor]

  return []

def _who_cares_sms(entry_ref, progress=None, limit=None, skip=None):
  """ figure out who wants to get an sms about this
  
  From the who_cares diagram we want

  Cs - comments on entries you wrote IGNORE already covered by initial_inboxes
  Cx - comments entries you've commented on
  Uu - user updates
  Uc - channel updates
 
  Twisting that around in terms of subscribers:
  
  if not a comment, subscribers to the stream for this item: 
      entry_ref.stream (Uu, Uc, -Cu)
  if this is a comment, subscribers to the entry: entry_ref.entry (Cx)

  """
  limit = limit is None and MAX_NOTIFICATIONS_PER_TASK or limit
  
  topic_keys = []
  if entry_ref.is_comment():
    topic_keys.append(entry_ref.entry)
    entry_stream_ref = stream_get(ROOT, entry_ref.extra.get('entry_stream'))
    actor_ref = actor_get(ROOT, entry_ref.actor)
    is_restricted = (entry_stream_ref.is_restricted() or 
                     actor_ref.is_restricted())
  else:
    topic_keys = [entry_ref.stream]
    stream_ref = stream_get(ROOT, entry_ref.stream)
    is_restricted = stream_ref.is_restricted()

  targets, more = _paged_targets_for_topics(topic_keys,
                                            is_restricted,
                                            progress=progress,
                                            limit=limit)

  # we always want to skip the actor who made this action
  # (unless we make that a setting in the future)
  if not skip:
    skip = []
  skip.append('inbox/%s/overview' % entry_ref.actor)

  targets = [t for t in targets if t not in skip]

  return targets, more

def _who_cares_sms_initial(actor_ref, new_entry_ref, entry_ref=None):
  # If is a comment and not by the author of the entry it is on
  #   entry-actor-overview (Cs)
  if new_entry_ref.is_comment() and new_entry_ref.actor != entry_ref.actor:
    return ['inbox/%s/overview' % entry_ref.actor]

  return []

def _paged_targets_for_topics(topic_keys, is_restricted=True, progress=None,
                              limit=MAX_FOLLOWERS_PER_INBOX):

  # If you're a little worried about how this works, hopefully this
  # horrible little diagram will help ease your fears (or find out how
  # we are doing it wrong and help us fix it)
  #
  # Example Time!
  #       We fetch the subscription targets for both the comments stream
  #       as well as for the entry, example:
  #       
  # ...............    ...............    ...............
  # limit = 4          limit = 4          limit = 4
  # progress = None    progress = D       progress = H
                      
                  
  # full data          full data          full data    
  # stream   entry     stream   entry     stream   entry 
  # ------   -----     ------   -----     ------   ----- 
  #   A                  A                  A            
  #   B        B         B        B         B        B   
  #   C                  C                  C            
  #   D        D         D        D         D        D   
  #   E        E         E        E         E        E   
  #   F                  F                  F            
  #            G                  G                  G   
  #            H                  H                  H   
  #   I                  I                  I            
  #   J                  J                  J            
                    
                    
  # fetched data      fetched data        fetched data 
  # stream   entry    stream   entry      stream   entry 
  # ------   -----    ------   -----      ------   ----- 
  #   A                 E        E          I            
  #   B        B        F                   J        
  #   C                          G                      
  #   D        D                 H                    
  #  ---                I                            
  #   E        E        J                          
  #   F                                                 
  #            G                                       
  #           ---                                    
  #            H                                       
  #   I                                                 
  #   J                                                 
                                                       
  # merged  more       merged  more       merged  more   
  # ------  -----      ------  -----      ------  -----  
  #   A     yes          E     yes          I     yes    
  #   B                  F                  J            
  #   C                  G                              
  #   D                  H                              

  subs = []
  for topic in topic_keys:
    subs += subscription_get_topic(ROOT,
                                   topic,
                                   limit=limit +1,
                                   offset=progress)

  # unique and sort
  targets = sorted(list(set([s.target for s in subs])))
  #logging.info('targets! %s', targets)

  # paging
  more = False
  if len(targets) > limit:
    more = True
    targets = targets[:limit]
  
  # Alright, we've handled all that stuff described in the note above
  # now we need to filter out the subscriptions that aren't subscribed 
  if is_restricted:
    good_targets = [s.target for s in subs if (s.is_subscribed())]
    targets = sorted(list(set(targets).intersection(set(good_targets))))

  return targets, more

def _paged_add_inbox(inboxes, stream_ref, entry_ref):
  if inboxes:
    last_inbox = inboxes[-1]
    # TODO(termie): maybe we should come up with a better shard identifier?
    #               theoretically, upon replay of this item the last item
    #               could change (a subscriber goes away) and we duplicate
    #               the inbox entry
    inbox_ref = _add_inbox(stream_ref, 
                           entry_ref, 
                           inboxes,
                           shard=last_inbox)

    return last_inbox
  return None

# half squewl
def _notify_subscribers_for_entry_by_type(notification_type, inboxes,
                                          actor_ref, new_stream_ref, 
                                          new_entry_ref, entry_ref=None,
                                          entry_stream_ref=None):

  # TODO(termie): this is not the most efficient way to do this at all
  #               it'd be nice if the subscription encoded the information
  #               about whether there should be im or sms delivery
  #               so that we at least have a smaller subset to work with
  
  if notification_type == 'im':
    _notify_im_for_entry(inboxes,
                         actor_ref,
                         new_stream_ref,
                         new_entry_ref,
                         entry_ref=entry_ref,
                         entry_stream_ref=entry_stream_ref)
  elif notification_type == 'sms':
    _notify_sms_for_entry(inboxes,
                          actor_ref,
                          new_stream_ref,
                          new_entry_ref,
                          entry_ref=entry_ref,
                          entry_stream_ref=entry_stream_ref)
  elif notification_type == 'email':
    _notify_email_for_entry(inboxes,
                            actor_ref,
                            new_stream_ref,
                            new_entry_ref,
                            entry_ref=entry_ref,
                            entry_stream_ref=entry_stream_ref)
  
def _notify_email_for_entry(inboxes, actor_ref, new_stream_ref, new_entry_ref,
                            entry_ref=None, entry_stream_ref=None):

  if not new_entry_ref.is_comment():
    return

  subscribers = [util.get_user_from_topic(inbox) for inbox in inboxes]
  subscribers = list(set(subscribers))
  subscribers_ref = actor_get_actors(ROOT, subscribers)
  subscribers_ref = [v for k, v in subscribers_ref.iteritems() if v]
  
  _notify_email_subscribers_for_comment(subscribers_ref, 
                                        actor_ref,
                                        new_entry_ref,
                                        entry_ref)

def _notify_im_for_entry(inboxes, actor_ref, new_stream_ref, new_entry_ref,
                         entry_ref=None, entry_stream_ref=None):
  subscribers = [util.get_user_from_topic(inbox) for inbox in inboxes]
  subscribers = list(set(subscribers))
  subscribers_ref = actor_get_actors(ROOT, subscribers)
  subscribers_ref = [v for k, v in subscribers_ref.iteritems() if v]
  
  # TODO(termie): merge these
  if new_entry_ref.is_comment():
    _notify_im_subscribers_for_comment(subscribers_ref,
                                       actor_ref,
                                       new_entry_ref,
                                       entry_ref)
  else:
    _notify_im_subscribers_for_entry(subscribers_ref,
                                     actor_ref,
                                     new_stream_ref,
                                     new_entry_ref)

def _notify_sms_for_entry(inboxes, actor_ref, new_stream_ref, new_entry_ref,
                          entry_ref=None, entry_stream_ref=None):

  subscribers = [util.get_user_from_topic(inbox) for inbox in inboxes]
  subscribers = list(set(subscribers))
  subscribers_ref = actor_get_actors(ROOT, subscribers)
  subscribers_ref = [v for k, v in subscribers_ref.iteritems() if v]
  
  mobile_numbers = []
  for subscriber_ref in subscribers_ref:
    if not subscriber_ref.extra.get('sms_notify'):
      continue
    mobile = mobile_get_actor(ROOT, subscriber_ref.nick)
    if not mobile:
      continue
    mobile_numbers.append(mobile)
  if not mobile_numbers:
    return
  
  sms_connection = sms.SmsConnection()
  
  if new_entry_ref.is_comment():
    template = '%s^%s: %s'
    title = entry_ref.title()
    firsts = smashed_title_re.findall(title)
    smashed_title = ''.join(firsts[:6])
    content = new_entry_ref.extra.get('content', '')
    if len(content) > 200:
      content = content[:20] + '...'
    message = template % (actor_ref.display_nick(), smashed_title, content)
    reply_key = entry_ref.keyname()
  else:
    template = '%s: %s'
    content = new_entry_ref.title()
    if len(content) > 200:
      content = content[:20] + '...'
    message = template % (actor_ref.display_nick(), content)
    reply_key = new_entry_ref.keyname()

  sms_connection.send_message(mobile_numbers, message)

  _reply_add_cache_sms(actor_ref, subscribers_ref, reply_key)



# old skewl
def _subscribers_for_entry(stream_ref, entry_ref):
  """
  Computes the list of streams that should be updated when a post is made.
  Returns the list.
  """
  # the users subscribed to the stream this entry is going to
  subscribers = subscription_get_topic(ROOT, stream_ref.key().name())

  if stream_is_private(ROOT, stream_ref.key().name()):
    # LEGACY COMPAT: the 'or' in there is for legacy compat
    subscribers = [s.target for s in subscribers
                     if (s.state == 'subscribed' or s.state == None)]
  else:
    subscribers = [s.target for s in subscribers]

  # the explore page if this isn't a comment
  if stream_ref.type != 'comment' and not stream_ref.owner.startswith('#'):
    subscribers.append('inbox/%s/explore' % ROOT.nick)

  # the views of the entry owner
  if stream_ref.read > PRIVACY_CONTACTS:
    subscribers.append('inbox/%s/public' % entry_ref.owner)
  if stream_ref.read > PRIVACY_PRIVATE:
    subscribers.append('inbox/%s/contacts' % entry_ref.owner)
  subscribers.append('inbox/%s/private' % entry_ref.owner)
  subscribers.append('inbox/%s/overview' % entry_ref.owner)
  subscribers = list(set(subscribers))
  return subscribers

def _subscribers_for_comment(comments_stream_ref, stream_ref,
                             entry_ref, comment_ref):
  # the users subscribed to the user's comment stream
  subscribers = subscription_get_topic(ROOT, comments_stream_ref.key().name())

  if stream_is_private(ROOT, stream_ref.key().name()):
    # LEGACY COMPAT: the 'or' in there is for legacy compat
    subscribers = [s.target for s in subscribers
                     if (s.state == 'subscribed' or s.state == None)]
  else:
    subscribers = [s.target for s in subscribers]

  # the users subscribed to this entry (commenters)
  entry_subscribers = subscription_get_topic(ROOT, entry_ref.key().name())
  subscribers += [s.target
                  for s in entry_subscribers
                  if s.state == 'subscribed']

  # the entry this is on
  subscribers.append(entry_ref.key().name() + "/comments")

  # the views of this commenter, only if entry is public
  if (comments_stream_ref.read > PRIVACY_CONTACTS and
      stream_ref.read > PRIVACY_CONTACTS):
    subscribers.append('inbox/%s/public' % comment_ref.actor)
  if (comments_stream_ref.read > PRIVACY_PRIVATE and
      stream_ref.read > PRIVACY_CONTACTS):
    subscribers.append('inbox/%s/contacts' % comment_ref.actor)

  # the private views of the commenter
  subscribers.append('inbox/%s/private' % comment_ref.actor)
  subscribers.append('inbox/%s/overview' % comment_ref.actor)

  # the overview of the entry owner (for channels) and actor
  subscribers.append('inbox/%s/overview' % entry_ref.owner)
  subscribers.append('inbox/%s/overview' % entry_ref.actor)
  subscribers = list(set(subscribers))
  return subscribers

def _add_inboxes_for_entry(inboxes, stream_ref, entry_ref):
  values = {"stream": entry_ref.stream,
            "stream_type": stream_ref.type,
            "uuid": entry_ref.uuid,
            "created_at": entry_ref.created_at,
            "inbox": inboxes,
            "shard": inboxes[-1],
            }
  if entry_ref.entry:
    values['entry'] = entry_ref.entry

  inbox_entry = InboxEntry(**values)
  inbox_entry.put()
  return inbox_entry

def _notify_subscribers_for_entry(inboxes, actor_ref, stream_ref,
                                  entry_ref):
  subscribers = [util.get_user_from_topic(inbox) for inbox in inboxes]
  subscribers = list(set(subscribers))
  subscribers_ref = actor_get_actors(ROOT, subscribers)
  subscribers_ref = [v for k, v in subscribers_ref.iteritems() if v]

  _notify_im_subscribers_for_entry(subscribers_ref,
                                   actor_ref,
                                   stream_ref,
                                   entry_ref)

def _notify_subscribers_for_comment(actor_ref, comment_ref, entry_ref):
  # get the list of subscribers to this entry (owner and commenters)
  inboxes = ['inbox/%s/overview' % entry_ref.actor]
  entry_subscribers = subscription_get_topic(ROOT, entry_ref.key().name())
  inboxes += [s.target
              for s in entry_subscribers
              if s.state == 'subscribed']
  subscribers = [util.get_user_from_topic(inbox) for inbox in inboxes]
  subscribers = list(set(subscribers))
  subscribers_ref = actor_get_actors(ROOT, subscribers)
  subscribers_ref = [v for k, v in subscribers_ref.iteritems() if v]

  _notify_email_subscribers_for_comment(subscribers_ref,
                                        actor_ref,
                                        comment_ref,
                                        entry_ref)

  _notify_im_subscribers_for_comment(subscribers_ref,
                                     actor_ref,
                                     comment_ref,
                                     entry_ref)

def _notify_email_subscribers_for_comment(subscribers_ref, actor_ref,
                                          comment_ref, entry_ref):
  for subscriber_ref in subscribers_ref:
    if not subscriber_ref.extra.get('email_notify'):
      continue
    email = email_get_actor(ROOT, subscriber_ref.nick)
    if not email:
      continue
    if subscriber_ref.nick == actor_ref.nick:
      continue

    subject, message = mail.email_comment_notification(
        subscriber_ref,
        actor_ref,
        comment_ref,
        entry_ref)
    email_send(ROOT, email, subject, message)

def _notify_im_subscribers_for_comment(subscribers_ref, actor_ref,
                                       comment_ref, entry_ref):
  xmpp_connection = xmpp.XmppConnection()

  im_aliases = []
  for subscriber_ref in subscribers_ref:
    if not subscriber_ref.extra.get('im_notify'):
      continue
    im = im_get_actor(ROOT, subscriber_ref.nick)
    if not im:
      continue
    im_aliases.append(im)
  if not im_aliases:
    return

  # We're effectively duplicationg common.display.prep_comment here
  comment_ref.owner_ref = actor_get(ROOT, entry_ref.owner)
  comment_ref.actor_ref = actor_ref
  comment_ref.entry_ref = entry_ref
  entry = comment_ref
  entries = [entry]

  context = {'entry': entry,
             'entries': entries,
             'entry_title_max_length':
                 settings.IM_MAX_LENGTH_OF_ENTRY_TITLES_FOR_COMMENTS,
             }
  # add all our settings to the context
  context.update(context_processors.settings(None))

  c = template.Context(context, autoescape=False)

  t = template.loader.get_template('common/templates/im/im_comment.txt')
  plain_text_message = t.render(c)

  c = template.Context(context)
  if settings.IM_PLAIN_TEXT_ONLY:
    html_message = None
  else:
    t = template.loader.get_template('common/templates/im/im_comment.html')
    html_message = t.render(c)

    t = template.loader.get_template('common/templates/im/im_comment.atom')
    atom_message = t.render(c)

  xmpp_connection.send_message(im_aliases,
                               plain_text_message,
                               html_message=html_message,
                               atom_message=atom_message)

  _reply_add_cache_im(actor_ref, subscribers_ref, entry_ref.keyname())

def _notify_im_subscribers_for_entry(subscribers_ref, actor_ref, stream_ref, entry_ref):
  xmpp_connection = xmpp.XmppConnection()
  im_aliases = []
  for subscriber_ref in subscribers_ref:
    if not subscriber_ref.extra.get('im_notify'):
      continue
    im = im_get_actor(ROOT, subscriber_ref.nick)
    if not im:
      continue
    im_aliases.append(im)
  if not im_aliases:
    return

  # We're effectively duplicationg common.display.prep_entry here
  entry_ref.stream_ref = stream_ref
  logging.info('stream_ref %s', stream_ref)
  entry_ref.owner_ref = actor_get(ROOT, entry_ref.owner)
  entry_ref.actor_ref = actor_ref
  entry = entry_ref
  entries = [entry]

  context = {'entry': entry,
             'entries': entries,
             }
  # add all our settings to the context
  context.update(context_processors.settings(None))

  c = template.Context(context, autoescape=False)
  t = template.loader.get_template('common/templates/im/im_entry.txt')
  plain_text_message = t.render(c)

  c = template.Context(context)
  if settings.IM_PLAIN_TEXT_ONLY:
    html_message = None
  else:
    t = template.loader.get_template('common/templates/im/im_entry.html')
    html_message = t.render(c)
    t = template.loader.get_template('common/templates/im/im_entry.atom')
    atom_message = t.render(c)


  xmpp_connection.send_message(im_aliases,
                               plain_text_message,
                               html_message=html_message,
                               atom_message=atom_message)

  _reply_add_cache_im(actor_ref, subscribers_ref, entry_ref.keyname())

def _notify_new_contact(owner_ref, target_ref):
  if not target_ref.extra.get('email_notify'):
    return
  email = email_get_actor(ROOT, target_ref.nick)
  if not email:
    return

  # using ROOT for internal functionality
  mutual = actor_has_contact(ROOT, target_ref.nick, owner_ref.nick)
  if mutual:
    subject, message, html_message = mail.email_new_follower_mutual(
        owner_ref, target_ref)
  else:
    subject, message, html_message = mail.email_new_follower(
        owner_ref, target_ref)

  email_send(ROOT, email, subject, message, html_message=html_message)


# Helpers for replying via @nick
def _reply_cache_key(sender, target, service=''):
  memcache_key = 'reply/%s/%s/%s' % (service, sender, target)
  return memcache_key

def _reply_add_cache(sender_ref, target_refs, entry, service=''):
  """Add an entry in the memcache, matching each outgoing IM message
  from a given actor to a set of actors, so that reply-by-IM works
  with '@actor comment' syntax.
  PARAMETERS:
    sender_ref - actor who posted the entry
    target_refs - list of actors receiving notification
    entry - key for the entry posted
  """
  memcache_entry = {}
  for target_ref in target_refs:
    memcache_key = _reply_cache_key(sender_ref.nick, 
                                    target_ref.nick, 
                                    service=service)
    memcache_entry[memcache_key] = entry

  memcache.client.set_multi(memcache_entry)

def _reply_add_cache_im(sender_ref, target_refs, entry):
  return _reply_add_cache(sender_ref, target_refs, entry, service='im')

def _reply_add_cache_sms(sender_ref, target_refs, entry):
  return _reply_add_cache(sender_ref, target_refs, entry, service='sms')


def reply_get_cache(sender, target, service=''):
  """ get the last entry from sender seen by target on service 
  
  Note: this has a somewhat misleading signature, it is generally called
  in the processing of an @nick post, in which case the target is the
  user making the post and the sender is the @nick.
  """


  entry_ref = None
  sender_ref = actor_lookup_nick(ROOT, sender)
  target_ref = actor_lookup_nick(ROOT, target)
  memcache_key = _reply_cache_key(sender_ref.nick, 
                                  target_ref.nick, 
                                  service=service)
  stream_key = memcache.client.get(memcache_key)
  if stream_key:
    entry_ref = entry_get(ROOT, stream_key)
  if not entry_ref:
    # TODO(termie): should work for non-public users too
    inbox = inbox_get_actor_public(sender_ref, 
                                   target_ref.nick, 
                                   limit=1, 
                                   stream_type='presence')
    if not inbox:
      logging.info('NO INBOX!')
      return
    logging.info('aa %s', inbox)
    entry_ref = entry_get(sender_ref, inbox[0])
  return entry_ref

def _email_from_subscribers_for_comment(subscribers):
  """From a set of subscribers, get the actors.
  PARAMETERS:
    subscribers - returned from _subscribers_for_*
  RETURNS:
    [email]  -- list of email aliases
  """
  aliases = {}
  for subscriber in subscribers:
    actor = util.get_user_from_topic(subscriber)
    email = email_get_actor(ROOT, actor)

    # Not all actors want email updates.
    if email:
      # TODO(tyler): Not just if they have an email registered, but specifically
      #              if they have the bit flipped for wanting email.
      aliases[email] = 1

  return aliases.keys()

def _set_presence(api_user, **kw):
  pass

# HELPER
def _limit_query(query, limit, offset):
  o = []
  query_it = query.run()
  for i in xrange(limit + offset):
    try:
      x = query_it.next()
    except StopIteration:
      break
    o.append(x)
  return o[offset:(offset+limit)]

def _crop_to_square(size, dimensions):
  sq = dimensions[0]
  w = size[0]
  h = size[1]

  if size[0] > size[1]:
    left_x = (size[0] - sq) / 2
    right_x = left_x + sq
    top_y = 0
    bottom_y = sq
  else:
    left_x = 0
    right_x = sq
    top_y = (size[1] - sq) / 2
    bottom_y = top_y + sq
  return (float(left_x) / w, float(top_y) / h,
          float(right_x) / w, float(bottom_y) / h)
