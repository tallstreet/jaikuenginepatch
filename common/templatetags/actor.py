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

"""django template tags for contact display logic
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

register = template.Library()

def is_not_contact(user, view, actor):
  if not user or user.nick != view.nick:
    return False
  if getattr(actor, 'my_contact', False):
    return False
  return True

def is_contact(user, view, actor):
  if not user or user.nick != view.nick:
    return False
  if getattr(actor, 'my_contact', False):
    return True
  return False

class ActorActionNode(template.Node):
  def __init__(self, var_user, var_view, var_actor,
               pred, api_call, link_class, content):
    self.var_user = template.Variable(var_user)
    self.var_view = template.Variable(var_view)
    self.var_actor = template.Variable(var_actor)
    self.pred = pred
    self.api_call = api_call
    self.link_class = link_class
    self.content = content

  def render(self, context):
    user = self.var_user.resolve(context)
    view = self.var_view.resolve(context)
    actor = self.var_actor.resolve(context)
    if self.pred(user, view, actor):
      content = escape(self.content % actor.display_nick())
      return (('<a href="?%s=&amp;target=%s&amp;_nonce=%s' +
               '&amp;owner=%s" class="%s">%s</a>') % (
                   self.api_call, urllib.quote(actor.nick),
                   create_nonce(user, self.api_call),
                   escape(view.nick), self.link_class,
                   content))
    else:
      return ''

def _actor_action(parser, token, pred, api_call, link_class, content):
  bits = list(token.split_contents())
  if len(bits) != 4:
    raise template.TemplateSyntaxError, "%r takes two arguments" % bits[0]
  return ActorActionNode(bits[1], bits[2], bits[3], pred,
                         api_call, link_class, content)

@register.tag
def actor_add_contact(parser, token):
  """
  Adds a 'add contact' link for an actor tile.
  Parameters: user, view, actor.
  """
  return _actor_action(parser, token, is_not_contact, 'actor_add_contact',
                       'add', 'Add %s')

@register.tag
def actor_add_contact_long(parser, token):
  return _actor_action(parser, token, is_not_contact, 'actor_add_contact',
                       'add', '+ Add %s as a contact')


@register.tag
def actor_remove_contact(parser, token):
  """
  Adds a 'remove contact' link for an actor tile.
  Parameters: user, view, actor.
  """
  return _actor_action(parser, token, is_contact, 'actor_remove_contact',
                       'remove', 'Remove %s')
