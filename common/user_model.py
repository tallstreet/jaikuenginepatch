import datetime
from django.utils.translation import ugettext_lazy as _
from google.appengine.ext import db as models
from ragendja.auth.google_models import GoogleUserTraits
from common.models import DeletedMarkerModel
from common import properties
from common.models import PRIVACY_PRIVATE, PRIVACY_CONTACTS, PRIVACY_PUBLIC, _get_actor_urlnick_from_nick, actor_url
from django.conf import settings
import logging

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

class User(DeletedMarkerModel, GoogleUserTraits):
 """
  extra:
    channel_count - int; number of channels
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
    rv = super(User, self).to_api()
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

  class Meta:
    verbose_name = _('user')
    verbose_name_plural = _('users')

  @classmethod
  def create_djangouser_for_user(cls, user):
    from common import api
    actor_ref = api.actor_lookup_email(api.ROOT, user.email()) 
    if actor_ref:
      return actor_ref
    params = {'nick': user.nickname(), 'password': "NOPASSWORD", 'first_name': user.nickname(),  'last_name': user.nickname()}
    actor_ref = api.user_create(api.ROOT, **params)
    actor_ref.access_level = "delete"
    relation_ref = api.email_associate(api.ROOT, actor_ref.nick, user.email())
    api.post(actor_ref, 
             nick=actor_ref.nick, 
             message='Joined %s!' % (settings.SITE_NAME),
             icon='jaiku-new-user')
    return actor_ref
   


