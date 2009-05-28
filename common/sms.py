import logging
import re

from django.conf import settings

from common import api
from common import clean
from common import exception
from common import patterns
from common import user
from common import util
from common.protocol import base
from common.protocol import sms

HELP_HUH = "Sorry, did not understand \"%s\". Send HELP for commands"
HELP_WELCOME = "Welcome to %s SMS! Questions? Contact support@%s" % (settings.SITE_NAME, settings.NS_DOMAIN)
HELP_WELCOME_NICK = "Welcome to %s SMS %s! Questions? Contact support@%s" % (settings.SITE_NAME, '%s', settings.NS_DOMAIN)
HELP_DOUBLE_OPT_IN = "To confirm you'd like to receive SMS updates, reply YES. You'll only have to do this once."
HELP_SIGNED_OUT = "You have signed out."
HELP_CHARGES = "%s is free. Other charges may apply." % (settings.SITE_NAME)
HELP_HELP_1 = "%s SMS updates. To get alerts text FOLLOW user/channelname. To stop text LEAVE user/channelname. To stop all alerts text STOP. To resume text START" % (settings.SITE_NAME)
HELP_HELP_2 = "Complete list on %s/sms. Other charges may apply. Questions? Contact support@%s" % (settings.DOMAIN, settings.NS_DOMAIN)

HELP_NOT_SIGNED_IN = "You are currently signed out\n"
HELP_SIGNED_IN_AS = "You are signed in as '%s'\n"
HELP_FOLLOW_ONLY = "You are signed in as a follow-only user\n"
HELP_PASSWORD = "Your password is: %s\n" \
                "Use it to sign in on the web at http://%s/\n" % ('%s', settings.DOMAIN)
HELP_POST = "To post to your stream, just send a message"
HELP_CHANNEL_POST = "To post to a channel, start your message with " \
                    "#channel"
HELP_COMMENT = "To comment on the latest update from someone, start " \
               "with @user"
HELP_FOLLOW = "To follow a user or channel, send FOLLOW <user/#channel>"
HELP_FOLLOW_NEW = "Send FOLLOW <user/#channel> to just follow a user or " \
                  "channel without signing up"
HELP_LEAVE = "To stop following a user or channel, send LEAVE <user/#channel>"
HELP_STOP = "To stop all alerts, send OFF"
HELP_START = "To turn on alerts, send ON"
HELP_SIGN_OUT = "To sign out from %s SMS, send SIGN OUT" % (settings.SITE_NAME)
HELP_DELETE_ME = "To remove your %s account, send DELETE ME" % (settings.SITE_NAME)
HELP_SIGN_IN = "Send SIGN IN <screen name> <password> if you already have a " \
               "%s account" % (settings.SITE_NAME)
HELP_SIGN_UP = "Send SIGN UP <desired screen name> to create a new account"
HELP_MORE = "For more commands, type HELP"
HELP_FOOTER = "\n" \
              "Questions? Visit http://%s/help/im\n" \
              "Contact us at support@%s" % (settings.DOMAIN, settings.NS_DOMAIN)
HELP_FOOTER_INFORMAL = "\n" \
                       "How it all works: http://%s/help/im" % (settings.DOMAIN)
HELP_OTR = "Your IM client has tried to initiate an OTR (off-the-record) session. However, this bot does not support OTR."

HELP_START_NOTIFICATIONS = "SMS notifications have been enabled. Send OFF to stop, HELP for commands."

HELP_STOP_NOTIFICATIONS = "SMS notifications have been disabled. Send ON to start receiving again."

class SmsService(base.Service):
  handlers = [patterns.SignInHandler,
              patterns.SignOutHandler,
              patterns.PromotionHandler,
              patterns.HelpHandler,
              patterns.CommentHandler,
              patterns.OnHandler,
              patterns.OffHandler,
              patterns.ChannelPostHandler,
              patterns.FollowHandler,
              patterns.LeaveHandler,
              patterns.ConfirmHandler,
              patterns.PostHandler,
              ]

      
  # TODO(termie): the following should probably be part of some sort of
  #               service interface, it is almost an exact duplicate of
  #               ImService
  def response_ok(self, rv=None):
    return ""

  def response_error(self, exc):
    return str(exc)
  
  def channel_join(self, sender, nick):
    sender_ref = api.actor_lookup_mobile(api.ROOT, sender)
    if not sender_ref:
      raise exception.ValidationError(HELP_SIGN_IN)
    channel = clean.channel(nick)

    try:
      api.channel_join(sender_ref, sender_ref.nick, channel)
      self.send_message((sender,),
                        "%s joined %s" % (sender_ref.display_nick(), nick))

    except:
      self.send_message((sender,),
                        "Failed to join %s" % nick)

  def channel_part(self, sender, nick):
    sender_ref = api.actor_lookup_mobile(api.ROOT, sender)
    if not sender_ref:
      raise exception.ValidationError(HELP_SIGN_IN)
    channel = clean.channel(nick)

    try:
      api.channel_part(sender_ref, sender_ref.nick, channel)
      self.send_message((sender,),
                        "%s left %s" % (sender_ref.display_nick(), nick))

    except:
      self.send_message((sender,),
                        "Failed to leave %s" % nick)

  def confirm(self, sender):
    """ confirm something if something needs to be confirmed
    
    otherwise, just post the message
    """
    
    sender_ref = api.actor_lookup_mobile(api.ROOT, sender)
    if not sender_ref:
      raise exception.ValidationError(HELP_SIGN_IN)
    
    if sender_ref.extra.get('sms_double_opt_in', None):
      api.mobile_confirm_doubleoptin(api.ROOT, sender_ref.nick)

    self.start_notifications(sender)
    
  def actor_add_contact(self, sender, nick):
    sender_ref = api.actor_lookup_mobile(api.ROOT, sender)
    if not sender_ref:
      raise exception.ValidationError(HELP_SIGN_IN)
    clean_nick = clean.nick(nick)
  
    try:
      api.actor_add_contact(sender_ref, sender_ref.nick, clean_nick)
      self.send_message((sender,),
                        "%s followed %s" % (sender_ref.display_nick(), nick))

    except:
      self.send_message((sender,),
                        "Failed to follow %s" % nick)

  def actor_remove_contact(self, sender, nick):
    sender_ref = api.actor_lookup_mobile(api.ROOT, sender)
    if not sender_ref:
      raise exception.ValidationError(HELP_SIGN_IN)
    clean_nick = clean.nick(nick)

    try:
      api.actor_remove_contact(sender_ref, sender_ref.nick, clean_nick)
      self.send_message((sender,),
                        "%s stopped following %s" % (sender_ref.dispaly_nick(), 
                                                     nick))

    except:
      self.send_message((sender,),
                        "Failed to stop following %s" % nick)

  def send_message(self, to_list, message):
    self.connection.send_message(to_list, message)

  def unknown(self, sender, message):
    self.send_message([sender], HELP_HUH % message)

  def sign_in(self, sender, nick, password):
    sender_ref = api.actor_lookup_mobile(api.ROOT, sender)
    if sender_ref:
      raise exception.ValidationError(
          "You are already signed in, please SIGN OUT first")

    user_ref = user.authenticate_user_login(nick, password)
    if not user_ref:
      raise exception.ValidationError("Username or password is incorrect")

    mobile_ref = api.mobile_associate(api.ROOT, user_ref.nick, sender)
    
    # if they need to double opt in send them the confirmation message
    welcome = ' '.join([HELP_WELCOME_NICK % user_ref.display_nick(),
                         HELP_POST,
                         HELP_START,
                         HELP_CHARGES
                         ])

    self.send_message([sender], welcome)

  def sign_out(self, sender):
    sender_ref = api.actor_lookup_mobile(api.ROOT, sender)
    if not sender_ref:
      raise exception.ValidationError(HELP_SIGN_IN)

    mobile_ref = api.mobile_disassociate(api.ROOT, sender_ref.nick, sender)

    self.send_message([sender], HELP_SIGNED_OUT)

  def help(self, sender):
    welcome = ' '.join([HELP_HELP_1,
                        HELP_HELP_2,
                         ])

    self.send_message([sender], welcome)

  def start_notifications(self, sender):
    sender_ref = api.actor_lookup_mobile(api.ROOT, sender)
    if not sender_ref:
      raise exception.ValidationError(HELP_SIGN_IN)

    if sender_ref.extra.get('sms_double_opt_in', None):
      message = ' '.join([HELP_DOUBLE_OPT_IN,
                          HELP_CHARGES])
      self.send_message([sender], message)
      return

    actor_ref = api.settings_change_notify(api.ROOT, sender_ref.nick, sms=True)
      
    message = ' '.join([HELP_START_NOTIFICATIONS,
                        HELP_CHARGES])

    self.send_message([sender], message)

  def stop_notifications(self, sender):
    sender_ref = api.actor_lookup_mobile(api.ROOT, sender)
    if not sender_ref:
      raise exception.ValidationError(HELP_SIGN_IN)

    actor_ref = api.settings_change_notify(api.ROOT, sender_ref.nick, sms=False)

    self.send_message([sender], HELP_STOP_NOTIFICATIONS)

  def post(self, sender, message):
    sender_ref = api.actor_lookup_mobile(api.ROOT, sender)
    if not sender_ref:
      raise exception.ValidationError(HELP_SIGN_IN)
    entry_ref = api.post(sender_ref, nick=sender_ref.nick, message=message)

  def channel_post(self, sender, channel_nick, message):
    sender_ref = api.actor_lookup_mobile(api.ROOT, sender)
    if not sender_ref:
      raise exception.ValidationError(HELP_SIGN_IN)

    comment_ref = api.channel_post(
        sender_ref,
        message=message,
        nick=sender_ref.nick,
        channel=channel_nick
    )

  def add_comment(self, sender, nick, message):
    sender_ref = api.actor_lookup_mobile(api.ROOT, sender)
    if not sender_ref:
      raise exception.ValidationError(HELP_SIGN_IN)

    logging.debug("comment: %s %s %s", nick, sender_ref.nick, message)

    nick = clean.nick(nick)
    stream_entry = api.reply_get_cache(sender=nick, 
                                       target=sender_ref.nick, 
                                       service='sms')
    if not stream_entry:
      # Well, or memcache timed it out...  Or we crashed... Or... Or...
      raise exception.ValidationError(
          'The message to which you tried to respond doesn\'t exist')

    api.entry_add_comment(sender_ref, entry=stream_entry.keyname(),
                          content=message, nick=sender_ref.nick,
                          stream=stream_entry.stream)

