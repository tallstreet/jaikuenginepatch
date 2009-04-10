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

"""django template tags for entry display logic
"""

__author__ = 'mikie@google.com (Mika Raento)'

import urllib

from django import template
from django.template.defaultfilters import stringfilter
import django.template.defaulttags
from django.utils.safestring import mark_safe
from django.utils.html import escape

from common.util import create_nonce, safe
from common import messages
from common.templatetags.base import if_pred
import settings

register = template.Library()

def is_actor_or_owner(user, entry, is_admin = False):
  if is_admin:
    return True
  if not user:
    return False
  return user.nick == entry.actor or user.nick == entry.owner

def is_not_actor(user, entry, is_admin = None):
  if not user:
    return False
  return user.nick != entry.actor

@register.tag
def if_actor_or_owner(parser, token):
  return if_pred(parser, token, is_actor_or_owner)

@register.tag
def if_not_actor(parser, token):
  return if_pred(parser, token, is_not_actor)

class EntryActionNode(template.Node):
  def __init__(self, var_user, var_entry, is_admin, pred, api_call, link_class, content):
    self.var_user = template.Variable(var_user)
    self.var_entry = template.Variable(var_entry)
    self.var_is_admin = None
    try:
      template.Variable(is_admin)
    except:
      pass
    self.pred = pred
    self.api_call = api_call
    self.link_class = link_class
    if not isinstance(content, template.Node):
      self.content = template.TextNode(content)
    else:
      self.content = content

  def render(self, context):
    user = self.var_user.resolve(context)
    entry = self.var_entry.resolve(context)
    is_admin = None
    try:
      is_admin = self.var_is_admin.resolve(context)
    except:
      pass
    if self.pred(user, entry, is_admin):
      content = self.content.render(context)
      return (
          ('<a href="?%s=%s&amp;_nonce=%s"'  +
          ' class="%s" title="%s">%s</a>') % (
              self.api_call, urllib.quote(entry.keyname()),
              create_nonce(user, self.api_call),
              self.link_class, escape(messages.title(self.api_call)),
              content))
    else:
      return ''

def entry_remove_x(parser, token, api_call):
  bits = list(token.split_contents())
  is_admin = None
  if len(bits) != 3 and len(bits) != 4:
    raise template.TemplateSyntaxError, "%r takes two or three arguments" % bits[0]
  if len(bits) == 4:
    is_admin = bits[3]
  return EntryActionNode(bits[1], bits[2], is_admin, is_actor_or_owner,
                         api_call, 'confirm-delete', 'Delete')

@register.tag
def entry_remove(parser, token):
  """
  Adds a Delete link for a post.
  Parameters: viewer, entry, is_admin.
  """
  return entry_remove_x(parser, token, 'entry_remove')

@register.tag
def entry_remove_comment(parser, token):
  """
  Adds a Delete link for a comment.
  Parameters: viewer, entry.
  """
  return entry_remove_x(parser, token, 'entry_remove_comment')

@register.tag
def entry_mark_as_spam(parser, token):
  """
  Adds a Mark as spam link for a post or comment.
  Parameters: viewer, entry.
  """
  if not settings.MARK_AS_SPAM_ENABLED:
    return django.template.defaulttags.CommentNode()
  bits = list(token.split_contents())
  is_admin = None
  if len(bits) != 3:
    raise template.TemplateSyntaxError, "%r takes two arguments" % bits[0]
  return EntryActionNode(bits[1], bits[2], is_admin, is_not_actor,
                         'entry_mark_as_spam', 'confirm-spam', 'Mark as spam')

@register.filter
def entry_url(value, arg="anchor"):
  if arg == "noanchor":
    with_anchor = False
  else:
    with_anchor = True
  return value.url(with_anchor=with_anchor)
