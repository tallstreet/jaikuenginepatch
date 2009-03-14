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
import re

from django.conf import settings

from common import api
from common import clean
from common import exception
from common import patterns
from common import user
from common import util
from common.protocol import base
from common.protocol import xmpp


HELP_HUH = "Sorry, did not understand \"%s\". Send HELP for commands"
HELP_WELCOME = "Welcome to %s IM!\n" % (settings.SITE_NAME)
HELP_WELCOME_NICK = "Welcome to %s IM, %s!\n" % (settings.SITE_NAME, '%s')
HELP_NOT_SIGNED_IN = "You are currently signed out\n"
HELP_SIGNED_IN_AS = "You are signed in as '%s'\n"
HELP_FOLLOW_ONLY = "You are signed in as a follow-only user\n"
HELP_PASSWORD = "Your password is: %s\n" \
                "Use it to sign in on the web at http://%s/\n" % ('%s', settings.DOMAIN)
HELP_POST = "To post to your stream, just send a message"
HELP_CHANNEL_POST = "To post to a channel, start your message with " \
                    "#channel"
HELP_COMMENT = "To comment the latest update from someone, start " \
               "with @user"
HELP_FOLLOW = "To follow a user or channel, send FOLLOW <user/#channel>"
HELP_FOLLOW_NEW = "Send FOLLOW <user/#channel> to just follow a user or " \
                  "channel without signing up"
HELP_LEAVE = "To stop following a user or channel, send LEAVE <user/#channel>"
HELP_STOP = "To stop all alerts, send STOP"
HELP_START = "To resume alerts, send START"
HELP_SIGN_OUT = "To sign out from %s IM, send SIGN OUT" % (settings.SITE_NAME)
HELP_DELETE_ME = "To remove your %s account, send DELETE ME" % (settings.SITE_NAME)
HELP_SIGN_IN = "Send SIGN IN <screen name> <password> if you already have a " \
               "%s account" % (settings.SITE_NAME)
HELP_SIGN_UP = "Send SIGN UP <desired screen name> to create a new account"
HELP_MORE = "For more commands, type HELP"
HELP_FOOTER = "\n" \
              "Questions? Visit http://%s/help/im\n"  \
              "Contact us at support@%s" % (settings.DOMAIN, settings.NS_DOMAIN)
HELP_FOOTER_INFORMAL = "\n" \
                       "How it all works: http://%s/help/im" % (settings.DOMAIN)
HELP_OTR = "Your IM client has tried to initiate an OTR (off-the-record) session. However, this bot does not support OTR."

HELP_START_NOTIFICATIONS = "IM notifications have been enabled. Send STOP to disable notifications, HELP for commands."

HELP_STOP_NOTIFICATIONS = "IM notifications have been disabled. Send START to enable notifications, HELP for commands."

# TODO(tyler): Merge with validate/clean/nick/whatever
NICK_RE = re.compile(r"""^[a-zA-Z][a-zA-Z0-9]{2,15}$""")


class ImService(base.Service):
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
              patterns.PostHandler,
              ]

      
  # TODO(termie): the following should probably be part of some sort of
  #               service interface
  def response_ok(self, rv=None):
    return ""

  def response_error(self, exc):
    return str(exc)
  
  def channel_join(self, from_jid, nick):
    jid_ref = api.actor_lookup_im(api.ROOT, from_jid.base())
    if not jid_ref:
      raise exception.ValidationError(
          "You must be signed in to join a channel, please SIGN IN")
    channel = clean.channel(nick)

    try:
      api.channel_join(jid_ref, jid_ref.nick, channel)
      self.send_message((from_jid,),
                        "%s joined %s" % (jid_ref.nick, channel))

    except:
      self.send_message((from_jid,),
                        "Join FAILED:  %s" % channel)

  def channel_part(self, from_jid, nick):
    jid_ref = api.actor_lookup_im(api.ROOT, from_jid.base())
    if not jid_ref:
      raise exception.ValidationError(
          "You must be signed in to leave a channel, please SIGN IN")
    channel = clean.channel(nick)

    try:
      api.channel_part(jid_ref, jid_ref.nick, channel)
      self.send_message((from_jid,),
                        "%s parted %s" % (jid_ref.nick, channel))

    except:
      self.send_message((from_jid,),
                        "Leave FAILED:  %s" % channel)

  def actor_add_contact(self, from_jid, nick):
    jid_ref = api.actor_lookup_im(api.ROOT, from_jid.base())
    if not jid_ref:
      raise exception.ValidationError(
          "You must be signed in to post, please SIGN IN")
    nick = clean.nick(nick)
  
    try:
      api.actor_add_contact(jid_ref, jid_ref.nick, nick)
      self.send_message((from_jid,),
                        "%s followed %s" % (jid_ref.nick, nick))

    except:
      self.send_message((from_jid,),
                        "Follow FAILED:  %s" % nick)

  def actor_remove_contact(self, from_jid, nick):
    jid_ref = api.actor_lookup_im(api.ROOT, from_jid.base())
    if not jid_ref:
      raise exception.ValidationError(
          "You must be signed in to post, please SIGN IN")
    nick = clean.nick(nick)

    try:
      api.actor_remove_contact(jid_ref, jid_ref.nick, nick)
      self.send_message((from_jid,),
                        "%s stopped following %s" % (jid_ref.nick, nick))

    except:
      self.send_message((from_jid,),
                        "Leave FAILED:  %s" % nick)

  def send_message(self, to_jid_list, message):
    self.connection.send_message(to_jid_list, message)

  def unknown(self, from_jid, message):
    self.send_message([from_jid], HELP_HUH % message)

  def sign_in(self, from_jid, nick, password):
    jid_ref = api.actor_lookup_im(api.ROOT, from_jid.base())
    if jid_ref:
      raise exception.ValidationError(
          "You are already signed in, please SIGN OUT first")

    user_ref = user.authenticate_user_login(nick, password)
    if not user_ref:
      raise exception.ValidationError("Username or password is incorrect")

    im_ref = api.im_associate(api.ROOT, user_ref.nick, from_jid.base())

    welcome = '\n'.join([HELP_WELCOME_NICK % user_ref.display_nick(),
                         HELP_POST,
                         HELP_CHANNEL_POST,
                         HELP_COMMENT,
                         HELP_FOLLOW,
                         HELP_STOP,
                         HELP_MORE,
                         HELP_FOOTER])

    self.send_message([from_jid], welcome)

  def sign_out(self, from_jid):
    jid_ref = api.actor_lookup_im(api.ROOT, from_jid.base())
    if not jid_ref:
      raise exception.ValidationError("You are not signed in.")

    im_ref = api.im_disassociate(api.ROOT, jid_ref.nick, from_jid.base())

    self.send_message([from_jid], "signed out")

  def help(self, from_jid):
    welcome = '\n'.join([HELP_WELCOME,
                         HELP_POST,
                         HELP_CHANNEL_POST,
                         HELP_COMMENT,
                         HELP_FOLLOW,
                         HELP_STOP,
                         HELP_MORE,
                         HELP_FOOTER])

    self.send_message([from_jid], welcome)

  def start_notifications(self, from_jid):
    jid_ref = api.actor_lookup_im(api.ROOT, from_jid.base())
    if not jid_ref:
      raise exception.ValidationError("You are not signed in.")

    actor_ref = api.settings_change_notify(api.ROOT, jid_ref.nick, im=True)

    self.send_message([from_jid], HELP_START_NOTIFICATIONS)

  def stop_notifications(self, from_jid):
    jid_ref = api.actor_lookup_im(api.ROOT, from_jid.base())
    if not jid_ref:
      raise exception.ValidationError("You are not signed in.")

    actor_ref = api.settings_change_notify(api.ROOT, jid_ref.nick, im=False)

    self.send_message([from_jid], HELP_STOP_NOTIFICATIONS)

  def post(self, from_jid, message):
    jid_ref = api.actor_lookup_im(api.ROOT, from_jid.base())
    if not jid_ref:
      raise exception.ValidationError(
          "You must be signed in to post, please SIGN IN")
    entry_ref = api.post(jid_ref, nick=jid_ref.nick, message=message)

  def channel_post(self, from_jid, channel_nick, message):
    jid_ref = api.actor_lookup_im(api.ROOT, from_jid.base())
    if not jid_ref:
      raise exception.ValidationError(
          "You must be signed in to post, please SIGN IN")

    comment_ref = api.channel_post(
        jid_ref,
        message=message,
        nick=jid_ref.nick,
        channel=channel_nick
    )

  def add_comment(self, from_jid, nick, message):
    jid_ref = api.actor_lookup_im(api.ROOT, from_jid.base())
    if not jid_ref:
      raise exception.ValidationError(
          "You must be signed in to post, please SIGN IN")

    logging.debug("comment: %s %s %s", nick, jid_ref.nick, message)

    nick = clean.nick(nick)
    stream_entry = api.reply_get_cache(sender=nick, 
                                       target=jid_ref.nick, 
                                       service='im')
    if not stream_entry:
      # Well, or memcache timed it out...  Or we crashed... Or... Or...
      raise exception.ValidationError(
          'The message to which you tried to respond doesn\'t exist')

    api.entry_add_comment(jid_ref, entry=stream_entry.keyname(),
                          content=message, nick=jid_ref.nick,
                          stream=stream_entry.stream)

  def promote_user(self, from_jid, nick):
    ji_ref = api.actor_lookup_im(api.ROOT, from_jid.base())
    if jid_ref:
      # TODO(tyler): Should we tell the user who they are?
      raise exception.ValidationError(
          "You already have an account and are signed in.")

    if not NICK_RE.match(nick):
      raise exception.ValidationError(
          "Invalid screen name, can only use letters or numbers, 3 to 16 "
          "characters")

    # Create the user.  (user_create will check to see if the account has
    # already been created.)
    password = util.generate_uuid()[:8]

    # TODO(termie): Must have a first/last name. :(
    actor = api.user_create(api.ROOT, nick=nick, password=password,
                            given_name=nick, family_name=nick)

    # link this im account to the user's account (equivalent of SIGN IN)
    self.sign_in(from_jid, nick, password)

    # Inform the user of their new password
    welcome = '\n'.join([HELP_WELCOME_NICK % nick,
                         HELP_PASSWORD % password,
                         HELP_POST,
                         HELP_CHANNEL_POST,
                         HELP_COMMENT,
                         HELP_FOLLOW,
                         HELP_STOP,
                         HELP_MORE,
                         HELP_FOOTER])

    self.send_message([from_jid], welcome)

