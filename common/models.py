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

import datetime
import logging

from google.appengine.ext import db as models

import appengine_django.models as aed_models
from oauth import oauth
from django.conf import settings
from django.db import models as django_models

from common import profile
from common import properties
from common import util

import settings
  

PRIVACY_PRIVATE = 1
PRIVACY_CONTACTS = 2
PRIVACY_PUBLIC = 3

ACTOR_ALLOWED_EXTRA = ('contact_count', 
                       'follower_count', 
                       'icon', 
                       'description',
                       'member_count', 
                       'admin_count', 
                       'given_name', 
                       'family_name'
                       )

ACTOR_LIMITED_EXTRA = ('icon', 
                       'description',
                       'given_name', 
                       'family_name'
                       )

# Internal Utility Functions

def _get_actor_type_from_nick(nick):
  if nick[0] == "#":
    return "channel"
  return "user"

def _get_actor_urlnick_from_nick(nick):
  parts = nick.split('@')
  nick = parts[0]
  if nick[0] == "#":
    nick = nick[1:]
  return nick

def _to_api(v):
  if hasattr(v, 'to_api'):
    v = v.to_api()
  elif isinstance(v, type([])):
    v = [_to_api(x) for x in v]
  elif isinstance(v, type({})):
    v = dict([(key, _to_api(value)) for (key, value) in v.iteritems()])
  elif isinstance(v, datetime.datetime):
    v = str(v)
  return v


# Base Models, Internal Only

class ApiMixinModel(aed_models.BaseModel):
  def to_api(self):
    o = {}
    for prop in self.properties().keys():
      value = getattr(self, prop)
      o[prop] = _to_api(value)
    return o

class CachingModel(ApiMixinModel):
  """A simple caching layer for model objects: caches any item read with
  get_by_key_name and removes from the cache on put() and delete()

  You must call reset_cache() in the beginning of any HTTP request or test.

  The design idea is that this should give a consistent view of the data within
  the processing a single request.
  """

  # TODO(mikie): appengine has non-Model put() and delete() that act on a bunch
  # of items at once. To be correct this should hook those as well.
  # TODO(mikie): should hook to the django sync_db signal so that the cache is
  # reset when database is (to support fixtures in tests correctly).
  # TODO(mikie): should cache items read through methods other than
  # get_by_key_name()

  _cache = { }
  _cache_enabled = False
  _get_count = 0
  def __init__(self, parent=None, key_name=None, _app=None, **kw):
    if not key_name:
      key_name = self.key_from(**kw)

    super(CachingModel, self).__init__(parent, key_name, _app, **kw)
    self._cache_keyname__ = (key_name, parent)
  
  @classmethod
  def key_from(cls, **kw):
    if hasattr(cls, 'key_template'):
      try:
        return cls.key_template % kw
      except KeyError:
        logging.warn('Automatic key_name generation failed: %s <- %s', 
                     cls.key_template, 
                     kw)
    return None

  def _remove_from_cache(self):
    clsname = self.__class__.__name__
    if CachingModel._cache_enabled:
      if CachingModel._cache.has_key(clsname):
        if CachingModel._cache[clsname].has_key(self._cache_keyname__):
          CachingModel._cache[clsname].pop(self._cache_keyname__)

  @profile.log_write
  def put(self):
    self._remove_from_cache()
    ret = super(CachingModel, self).put()
    self._cache_keyname__ = (self.key().name(), self.parent_key())
    self._remove_from_cache()
    return ret

  def save(self):
    return self.put()
  
  @profile.log_write
  def delete(self):
    self._remove_from_cache()
    return super(CachingModel, self).delete()
  
  @classmethod
  @profile.log_call('threadlocal_cached_read')
  def get_by_key_name(cls, key_names, parent=None):
    if not key_names:
      return
    # Only caches when called with a single key
    if CachingModel._cache_enabled and (
          isinstance(key_names, str) or isinstance(key_names, unicode)):
      clsname = cls.__name__
      if not CachingModel._cache.has_key(clsname):
        CachingModel._cache[clsname] = { }
      elif CachingModel._cache[clsname].has_key((key_names, parent)):
        profile.store_call(cls, 'get_by_key_name', 'threadlocal_cache_hit')
        return CachingModel._cache[clsname][(key_names, parent)]

      profile.store_call(cls, 'get_by_key_name', 'threadlocal_cache_miss')
      ret = super(CachingModel, cls).get_by_key_name(key_names, parent)
      CachingModel._get_count += 1
      CachingModel._cache[clsname][(key_names, parent)] = ret
      if ret:
        ret._cache_keyname__ = (key_names, parent)
      return ret
    else:
      CachingModel._get_count += len(key_names)
      return super(CachingModel, cls).get_by_key_name(key_names, parent)

  @classmethod
  def db_get_count(cls):
    return CachingModel._get_count

  @classmethod
  def reset_cache(cls):
    CachingModel._cache = { }

  @classmethod
  def enable_cache(cls, enabled = True):
    CachingModel._cache_enabled = enabled
    if not enabled:
      CachingModel._cache = { }

  @classmethod
  def reset_get_count(cls):
    CachingModel._get_count = 0
  
  @classmethod
  @profile.log_read
  def gql(cls, *args, **kw):
    return super(CachingModel, cls).gql(*args, **kw)

  @classmethod
  @profile.log_read
  def Query(cls):
    # TODO(termie): I don't like that this module is called "models" here,
    #               I'd prefer to be accessing it by "db"
    return models.Query(cls)

class DeletedMarkerModel(CachingModel):
  deleted_at = properties.DateTimeProperty()

  def mark_as_deleted(self):
    self.deleted_at = datetime.datetime.utcnow()
    self.put()

  def is_deleted(self):
    return self.deleted_at


# Public Models

class AbuseReport(CachingModel):
  entry = models.StringProperty()  # ref - entry
  actor = models.StringProperty()  # ref - actor for entry
  reports = models.StringListProperty() # the actors who have reported this
  count = models.IntegerProperty() # the count of the number of reports so far
  
  key_template = '%(entry)s'

class Activation(CachingModel):
  actor = models.StringProperty()
  content = models.StringProperty()
  code = models.StringProperty()
  type = models.StringProperty()

  key_template = 'activation/%(actor)s/%(type)s/%(content)s'

def actor_url(nick, actor_type, path='', request=None, mobile=False):
  """ returns a url, with optional path appended

  NOTE: if appending a path, it should start with '/'
  """
  prefix = ""
  try:
    if mobile or (request and request.mobile):
      prefix = "m."
  except AttributeError:
    pass
  
  if settings.WILDCARD_USER_SUBDOMAINS_ENABLED and actor_type == 'user':
    return 'http://%s.%s%s%s' % (nick, prefix, settings.HOSTED_DOMAIN, path)
  else:
    return 'http://%s%s/%s/%s%s' % (prefix,
                                    settings.DOMAIN,
                                    actor_type,
                                    nick,
                                    path)

class Actor(DeletedMarkerModel):
  """
  extra:
    contact_count - int; number of contacts
    follower_count - int; number of followers
    icon - string; avatar path
    bg_image - string; image for background (takes precedence over bg_color)
    bg_color - string; color for background
    bg_repeat - whether to repeat bg_image
    description [channel] - string; Channel description
    external_url [channel] - string; External url related ot channel
    member_count [channel] - int; number of members
    admin_count [channel] - int; number of admins
    email_notify [user] - boolean; does the user want email notifications?
    given_name [user] - string; First name
    family_name [user] - string; Last Name
    comments_hide [user] - boolean; Whether comments should be hidden on 
                             overview
  """
  nick = models.StringProperty()
  # the appengine datastore is case-sensitive whereas human brains are not, 
  # Paul is not different from paul to regular people so we need a way to 
  # prevent duplicate names from cropping up, this adds an additional indexed 
  # property to support that
  normalized_nick = models.StringProperty()
  password = models.StringProperty()
  privacy = models.IntegerProperty()
  type = models.StringProperty()
  extra = properties.DictProperty()
  # avatar_updated_at is used by DJabberd to get a list of changed avatar. We
  # set the default to a date before the launch so that initial avatars have an
  # updated_at that is less than any real changes.
  avatar_updated_at = properties.DateTimeProperty(
      default=datetime.datetime(2009, 01, 01))

  key_template = 'actor/%(nick)s'

  def url(self, path="", request=None, mobile=False):
    """ returns a url, with optional path appended
    
    NOTE: if appending a path, it should start with '/'
    """
    return actor_url(_get_actor_urlnick_from_nick(self.nick),
                     self.type,
                     path=path,
                     request=request,
                     mobile=mobile)

  def shortnick(self):
    return _get_actor_urlnick_from_nick(self.nick)

  def display_nick(self):
    return self.nick.split("@")[0]
    return _get_actor_urlnick_from_nick(self.nick)

  def to_api(self):
    rv = super(Actor, self).to_api()
    del rv['password']
    del rv['normalized_nick']
    extra = {}
    for k, v in rv['extra'].iteritems():
      if k in ACTOR_ALLOWED_EXTRA:
        extra[k] = v
    rv['extra'] = extra
    return rv

  def to_api_limited(self):
    rv = self.to_api()
    extra = {}
    for k, v in rv['extra'].iteritems():
      if k in ACTOR_LIMITED_EXTRA:
        extra[k] = v
    rv['extra'] = extra
    return rv

  def is_channel(self):
    return self.type == 'channel'

  def is_public(self):
    return self.privacy == PRIVACY_PUBLIC

  def is_restricted(self):
    return self.privacy == PRIVACY_CONTACTS

  def __repr__(self):
    # Get all properties, but not directly as property objects, because
    # constructor requires values to be passed in.
    d = dict([(k, self.__getattribute__(k)) for k in self.properties().keys()])
    return "%s(**%s)" % (self.__class__.__name__, repr(d))

class Image(CachingModel):
  actor = models.StringProperty()     # whose image is this?
  content = models.BlobProperty()     # the image itself
  size = models.StringProperty()      # see api.avatar_upload

  # TODO(termie): key_template plans don't really work very well here
  #               because we haven't been storing the path :/

class InboxEntry(CachingModel):
  """This is the inbox index for an entry.

  the index allows us to quickly pull the overview for a user. There may be
  items in the results that are later filtered out - deleted items or items
  whose privacy has changed.
  """
  inbox = models.StringListProperty()   # ref - who this is the inbox for
  stream = models.StringProperty()      # ref - the stream this belongs to
  stream_type = models.StringProperty() # separate because we may filter on it
  entry = models.StringProperty()       # ref - the entry if this is a comment
  created_at = properties.DateTimeProperty()
  uuid = models.StringProperty()
  shard = models.StringProperty()       # an identifier for this portion of
                                        # inboxes

  key_template = 'inboxentry/%(stream)s/%(uuid)s/%(shard)s'

  def stream_entry_keyname(self):
    """Returns the key name of the corresponding StreamEntry"""
    return "%s/%s" % (self.stream, self.uuid)

class Invite(CachingModel):
  code = models.StringProperty() # the code for the invite
  email = models.StringProperty() # the email this invite went to
  to_actor = models.StringProperty() # ref - the actor this invite was sent to
  from_actor = models.StringProperty() # ref - who sent this invite
  for_actor = models.StringProperty() # ref - invited to what, probs a channel
  status = models.StringProperty(default="active") # enum - active, blocked

  key_template = 'invite/%(code)s'

class KeyValue(CachingModel):
  actor = models.StringProperty()
  keyname = models.StringProperty()
  value = models.TextProperty()

  key_template = 'keyvalue/%(actor)s/%(keyname)s'

class OAuthAccessToken(CachingModel):
  key_ = models.StringProperty()      # the token key
  secret = models.StringProperty()    # the token secret
  consumer = models.StringProperty()  # the consumer this key is assigned to
  actor = models.StringProperty()     # the actor this key authenticates for
  created_at = properties.DateTimeProperty(auto_now_add=True)     
                                      # when this was created
  perms = models.StringProperty()     # read / write / delete

  key_template = 'oauth/accesstoken/%(key_)s'

  def to_string(self):
    token = oauth.OAuthToken(self.key_, self.secret)
    return token.to_string()

class OAuthConsumer(CachingModel):
  key_ = models.StringProperty()      # the consumer key
  secret = models.StringProperty()    # the consumer secret
  actor = models.StringProperty()     # the actor who owns this
  status = models.StringProperty()    # active / pending / inactive
  type = models.StringProperty()      # web / desktop / mobile
  commercial = models.IntegerProperty()   # is this a commercial key?
  app_name = models.StringProperty()  # the name of the app this is for,
                                      # to be displayed to the user
  created_at = properties.DateTimeProperty(auto_now_add=True)
  
  key_template = 'oauth/consumer/%(key_)s'
  
  def url(self):
    return '/api/keys/%s' % self.key_

class OAuthNonce(CachingModel):
  nonce = models.StringProperty()     # the nonce
  consumer = models.StringProperty()  # the consumer this nonce is for
  token = models.StringProperty()     # the token this nonce is for
  created_at = properties.DateTimeProperty(auto_now_add=True)     
                                      # when this was created

class OAuthRequestToken(CachingModel):
  key_ = models.StringProperty()      # the token key
  secret = models.StringProperty()    # the token secret
  consumer = models.StringProperty()  # the consumer this key is assigned to
  actor = models.StringProperty()     # the actor this key authenticates for
  authorized = models.IntegerProperty()   # has the actor authorized this token?
  created_at = properties.DateTimeProperty(auto_now_add=True)     
                                      # when this was created
  perms = models.StringProperty()     # read / write / delete

  key_template = 'oauth/requesttoken/%(key_)s'

  def to_string(self):
    token = oauth.OAuthToken(self.key_, self.secret)
    return token.to_string()

class Presence(CachingModel):
  """This represents all the presence data for an actor at a moment in time.
  extra:
    status - string; message (like an "away message")
    location - string; TODO(tyler): Consider gps / cell / structured data
    availability - string; TODO(tyler): Define structure
  """
  actor = models.StringProperty()     # The actor whose presence this is
  updated_at = properties.DateTimeProperty(auto_now_add=True)
                                      # The moment we got the update
  uuid = models.StringProperty()
  extra = properties.DictProperty()   # All the rich presence

  # TODO(termie): can't do key_template here yet because we include 
  #               current and history keys :/

class Task(CachingModel):
  actor = models.StringProperty()     # ref - the owner of this queue item
  action = models.StringProperty()    # api call we are iterating through
  action_id = models.StringProperty() # unique identifier for this queue item
  args = models.StringListProperty()  # *args
  kw = properties.DictProperty()      # *kw
  expire = properties.DateTimeProperty()
                                      # when our lock will expire
  progress = models.StringProperty()  # a string representing the offset to 
                                      # which we've progressed so far
  created_at = properties.DateTimeProperty(auto_now_add=True)
  
  key_template = 'task/%(actor)s/%(action)s/%(action_id)s'

class Relation(CachingModel):
  owner = models.StringProperty()     # ref - actor nick
  relation = models.StringProperty()  # what type of relationship this is
  target = models.StringProperty()    # ref - actor nick

  key_template = 'relation/%(relation)s/%(owner)s/%(target)s'

class Stream(DeletedMarkerModel):
  """
  extra:  see api.stream_create()
  """
  owner = models.StringProperty()     # ref
  title = models.StringProperty()
  type = models.StringProperty()
  slug = models.StringProperty()
  read = models.IntegerProperty()     # TODO: document this
  write = models.IntegerProperty()
  extra = properties.DictProperty()

  key_template = 'stream/%(owner)s/%(slug)s'

  def is_public(self):
    return self.read == PRIVACY_PUBLIC

  def is_restricted(self):
    return self.read == PRIVACY_CONTACTS

  def keyname(self):
    """Returns the key name"""
    return self.key().name()

class StreamEntry(DeletedMarkerModel):
  """
  extra :
    title - 
    location - 
    icon - 
    content - 
    entry_stream - 
    entry_stream_type - 
    entry_title - 
    entry_uuid - 
    comment_count - 
  """
  stream = models.StringProperty()    # ref - the stream this belongs to
  owner = models.StringProperty()     # ref - the actor who owns the stream
  actor = models.StringProperty()     # ref - the actor who wrote this
  entry = models.StringProperty()     # ref - the parent of this,
                                      #       should it be a comment
  uuid = models.StringProperty()
  created_at = properties.DateTimeProperty(auto_now_add=True)
  extra = properties.DictProperty()

  key_template = '%(stream)s/%(uuid)s'

  def url(self, with_anchor=True, request=None, mobile=False):
    if self.entry:
      # TODO bad?
      slug = self.entry.split("/")[-1]
      anchor = "#c-%s" % self.uuid
    else:
      # TODO(termie): add slug property
      slug = self.uuid
      anchor = ""
    path = "/%s/%s" % ('presence', slug)
    if with_anchor:
      path = "%s%s" % (path, anchor)
    return actor_url(_get_actor_urlnick_from_nick(self.owner),
                     _get_actor_type_from_nick(self.owner),
                     path=path,
                     request=request,
                     mobile=mobile)

  def keyname(self):
    """Returns the key name"""
    return self.key().name()

  def title(self):
    """ build a title for this entry, for a presence entry it will just be
    the title, but for a comment it will look like:

    Comment from [commenter nick] on [entry title] by [nick]

    Comment from [commenter nick] on [entry title] by [nick] to #[channel name]
    """

    if not self.is_comment():
      return self.extra.get('title')

    template = "Comment from %(actor)s on %(entry_title)s by %(entry_actor)s"
    actor = _get_actor_urlnick_from_nick(self.actor)
    entry_title = self.extra.get('entry_title')
    entry_actor = _get_actor_urlnick_from_nick(self.extra.get('entry_actor'))
    entry_owner_nick = util.get_user_from_topic(self.entry)
    entry_type = _get_actor_type_from_nick(entry_owner_nick)

    v = {'actor': actor,
         'entry_title': entry_title,
         'entry_actor': entry_actor,
         }

    if entry_type == 'channel':
      template += ' to #%(channel)s'
      channel = _get_actor_urlnick_from_nick(entry_owner_nick)
      v['channel'] = channel

    return template % v

  def is_comment(self):
    return (self.entry != None)

  def is_channel(self):
    return self.owner.startswith('#')

  def entry_actor(self):
    if self.entry:
      return util.get_user_from_topic(self.entry)
    return None

class Subscription(CachingModel):
  """this represents a topic, usually a stream, that a subscriber
     (usually an inbox) would like to receive updates to
  """
  topic = models.StringProperty()       # ref - the stream being subscribed to
  subscriber = models.StringProperty()  # ref - the subscriber (actor)
  target = models.StringProperty()      # where to dump this
  state = models.StringProperty() # The status of remote subs, see XEP-0060
                                  # sect 4.2. The 'pending' state is ignored if
                                  # the target of the subscription is used.
                                  # The design is for performance: on public 
                                  # entries
                                  # the state is ignored and listing the
                                  # subscriptions is a single query; for
                                  # contacts-only entries the state is used but
                                  # it is also kept up-to-date regarding buddy
                                  # relationships, so a single query for
                                  # state='subscribed' can again be used.
  extra = properties.DictProperty()     # holds a bunch of stuff
  created_at = properties.DateTimeProperty(auto_now_add=True) 
                                  # for ordering someday
  key_template = '%(topic)s/%(target)s'

  def is_subscribed(self):
    # LEGACY COMPAT: the 'or' here is for legacy compat
    return (self.state == 'subscribed' or self.state == None)

#class ActorMobile(models.Model):
#  nick = models.TextField()
#  mobile = models.TextField()
#  country_code = models.TextField()
#  confirmed = models.BooleanField()

#class ActorEmail(models.Model):
#  nick = models.TextField()
#  email = models.EmailField()
