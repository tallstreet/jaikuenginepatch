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

import re

"""Regular expressions for various things..."""


# TODO(tyler): Separate out nick sub-pattern.
AVATAR_PARTIAL_PATH_RE = r'(default|(?P<nick>#?\w+@[\w\.]+))/(?P<path>.*)'
AVATAR_PARTIAL_PATH_COMPILED = re.compile(AVATAR_PARTIAL_PATH_RE)

AVATAR_PATH_RE = r'^image/' + AVATAR_PARTIAL_PATH_RE + '\.jpg'
AVATAR_PATH_COMPILED = re.compile(AVATAR_PATH_RE)


# TODO(tyler): Make these match reality / tighter:
EMAIL_RE = r'[^@]+@[a-zA-Z.]+'
EMAIL_COMPILED = re.compile(EMAIL_RE)

class PatternHandler(object):
  pattern = None
  service = None
  def __init__(self, service):
    self.service = service

  def match(self, from_jid, message):
    if self.pattern:
      return self.pattern.match(message)
    return None

  def handle(self, from_jid, match, message):
    raise NotImplementedError()


class ChannelPostHandler(PatternHandler):
  pattern = re.compile(r'^\s*(#[\w@.]+):?\s+(.*)$')

  def handle(self, sender, match, message):
    self.service.channel_post(sender, match.group(1), match.group(2))


class CommentHandler(PatternHandler):
  """
  Pattern handler for placing a comment.

  Comments are placed by prefixing the message with C{'@'} and a nick name.
  The comment will be added to the last entry posted or commented on by the
  user associated with the given nick name, as received by the commenter.
  """
  pattern = re.compile(r"""^\s*@(\w+):?\s*(.*)$""", re.I | re.S)

  def handle(self, sender, match, message):
    nick = match.group(1)
    msg = match.group(2)

    self.service.add_comment(sender, nick, msg)


class ConfirmHandler(PatternHandler):
  pattern = re.compile(r"""^\s*(?:yes)(?:\s+)?$""", re.I)

  def handle(self, sender, match, message):
    self.service.confirm(sender)


class FollowHandler(PatternHandler):
  pattern = re.compile(
      r"""^\s*(?:join|follow|add|f)\s+((?P<channel>#\w+)|(?P<nick>\w+))""",
      re.I)

  def handle(self, sender, match, message):
    channel = match.group('channel')
    nick = match.group('nick')

    if channel:
      self.service.channel_join(sender, channel)
    elif nick:
      self.service.actor_add_contact(sender, nick)
    else:
      # hmm, perhaps we should return true or false, depending on whether
      # this was handled.
      pass


class HelpHandler(PatternHandler):
  pattern = re.compile(r"""^\s*(help)\s*$""", re.I)

  def handle(self, sender, match, message):
    self.service.help(sender)


class LeaveHandler(PatternHandler):
  pattern = re.compile(
      r"""^\s*(?:leave|part|remove|l)\s+((?P<channel>#\w+)|(?P<nick>\w+))""",
      re.I)

  def handle(self, sender, match, message):
    channel = match.group('channel')
    nick = match.group('nick')

    if channel:
      self.service.channel_part(sender, channel)
    elif nick:
      self.service.actor_remove_contact(sender, nick)
    else:
      # hmm, perhaps we should return true or false, depending on whether
      # this was handled.
      pass


class OffHandler(PatternHandler):
  pattern = re.compile(r"""^\s*(?:off|stop|end|quit|cancel|unsubscribe|pause)(?:\s+)?$""", re.I)

  def handle(self, sender, match, message):
    self.service.stop_notifications(sender)


class OnHandler(PatternHandler):
  pattern = re.compile(r"""^\s*(?:on|start|wake)(?:\s+)?$""", re.I)

  def handle(self, sender, match, message):
    self.service.start_notifications(sender)


class PostHandler(PatternHandler):
  def match(self, sender, message):
    return True

  def handle(self, sender, match, message):
    self.service.post(sender, message)


class PromotionHandler(PatternHandler):
  """
  Create a new account
  """
  pattern = re.compile(r"""^\s*(sign\s+up)\s+(\w+)""", re.I)

  def handle(self, sender, match, message):
    self.service.promote_user(sender, match.group(2))


class SignInHandler(PatternHandler):
  """
  Pattern handler to claim an existing account from a follow-only account.
  """
  pattern = re.compile(r"""^\s*(claim|sign\s+in)\s+(\w+)\s+(\S+)""", re.I)

  def handle(self, sender, match, message):
    nick = match.group(2)
    password = match.group(3)

    self.service.sign_in(sender, nick, password)


class SignOutHandler(PatternHandler):
  pattern = re.compile(r"""^\s*(sign\s+out)\s*$""", re.I)

  def handle(self, sender, match, message):
    self.service.sign_out(sender)






