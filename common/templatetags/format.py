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
import re

from markdown import markdown2

from django import template
from django.conf import settings
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.utils.timesince import timesince
from common.util import create_nonce, safe, display_nick, url_nick

from common import clean
from common import models

register = template.Library()

link_regex = re.compile(r'\[([^\]]+)\]\((http[^\)]+)\)')

r'(^|\s|>)([A-Za-z][A-Za-z0-9+.-]{1,120}:[A-Za-z0-9/](([A-Za-z0-9$_.+!*,;/?:@&~=-])|%[A-Fa-f0-9]{2}){1,333}(#([a-zA-Z0-9][a-zA-Z0-9$_.+!*,;/?:@&~=%-]{0,1000}))?)'

# lifted largely from: 
# http://www.manamplified.org/archives/2006/10/url-regex-pattern.html
autolink_regex = re.compile(r'(^|\s|>)([A-Za-z][A-Za-z0-9+.-]{1,120}:[A-Za-z0-9/](([A-Za-z0-9$_.+!*,;/?:@&~=-])|%[A-Fa-f0-9]{2}){1,333}(#([a-zA-Z0-9][a-zA-Z0-9$_.+!*,;/?:@&~=%-]{0,1000}))?)')
bold_regex = re.compile(r'\*([^*]+)\*')
italic_regex = re.compile(r'_([^_]+)_')


@register.filter(name="format_fancy")
@safe
def format_fancy(value, arg=None):
  value = italic_regex.sub(r'<i>\1</i>', value)
  value = bold_regex.sub(r'<b>\1</b>', value)
  return value


@register.filter(name="format_links")
@safe
def format_links(value, arg=None):
  value = link_regex.sub(r'<a href="\2" target=_new>\1</a>', value)
  return value

@register.filter(name="format_autolinks")
@safe
def format_autolinks(value, arg=None):
  value = autolink_regex.sub(r'\1<a href="\2" target="_new">\2</a>', value)
  return value

# TODO(tyler): Combine these with validate
user_regex = re.compile(
    r'@([a-zA-Z][a-zA-Z0-9]{%d,%d})' 
    % (clean.NICK_MIN_LENGTH - 1, clean.NICK_MAX_LENGTH - 1)
    )
channel_regex = re.compile(
    r'#([a-zA-Z][a-zA-Z0-9]{%d,%d})' 
    % (clean.NICK_MIN_LENGTH - 1, clean.NICK_MAX_LENGTH - 1)
    )

@register.filter(name="format_actor_links")
@safe
def format_actor_links(value, request=None):
  """Formats usernames / channels
  """
  value = re.sub(user_regex,
                 lambda match: '<a href="%s" rel="user">@%s</a>' % (
                   models.actor_url(match.group(1), 'user', request=request),
                   match.group(1)),
                 value)

  value = re.sub(channel_regex,
                 lambda match: '<a href="%s" rel="channel">#%s</a>' % (
                   models.actor_url(match.group(1), 'channel', request=request),
                   match.group(1)),
                 value)
  return value

@register.filter(name="format_markdown")
@safe
def format_markdown(value, arg=None):
  return markdown2.markdown(value)

@register.filter(name="format_comment")
@safe
def format_comment(value, request=None):
  content = escape(value.extra.get('content', 'no title'))
  content = format_markdown(content)
  content = format_autolinks(content)
  content = format_actor_links(content, request)
  return content

@register.filter(name="truncate")
def truncate(value, arg):
  """
  Truncates a string after a certain number of characters. Adds an
  ellipsis if truncation occurs.
  
  Due to the added ellipsis, truncating to 10 characters results in an
  11 character string unless the original string is <= 10 characters
  or ends with whitespace.

  Argument: Number of characters to truncate after.
  """
  try:
    max_len = int(arg)
  except:
    return value # No truncation/fail silently.

  if len(value) > max_len:
    # Truncate, strip rightmost whitespace, and add ellipsis
    return value[:max_len].rstrip() + u"\u2026"
  else:
    return value

@register.filter(name="entry_icon")
@safe
def entry_icon(value, arg=None):
  icon = value.extra.get('icon', None)
  if not icon:
    return ""

  return '<img src="/themes/%s/icons/%s.gif" alt="%s" class="icon" />' % (settings.DEFAULT_THEME, icon, icon)

@register.filter(name="linked_entry_title")
@safe
def linked_entry_title(value, request=None):
  """
  Returns an entry link.

  value     an entry object.
  request   a HttpRequest (optional).
  """
  return '<a href="%s">%s</a>' % (
      value.url(request=request), 
      format_fancy(escape(value.extra['title'])).replace('\n', ' '))

@register.filter
@safe
def linked_entry_truncated_title(value, arg):
  """
  Returns a link to an entry using a truncated entry title as source anchor.

  Argument: Number of characters to truncate after.
  """
  try:
    max_len = int(arg)
  except:
    max_len = None # No truncation/fail silently.

  if value.is_comment():
    title = escape(truncate(value.extra['entry_title'].replace('\n', ' '),
                            max_len))
  else:
    title = escape(truncate(value.extra['title'].replace('\n', ' '), max_len))

  return '<a href="%s">%s</a>' % (value.url(), title)

@register.filter(name="stream_icon")
@safe
def stream_icon(value, arg=None):
  return '<img src="/themes/%s/icons/favku.gif" class="icon" />' % settings.DEFAULT_THEME
  if type(value) is type(1):
    return '<!-- TODO entry icon goes here -->'
  return '<!-- TODO entry icon goes here -->'

@register.filter(name="je_timesince")
@safe
def je_timesince(value, arg=None):
  d = value
  if (datetime.datetime.now() - d) < datetime.timedelta(0,60,0):
    return "a moment"
  else:
    return timesince(d)

@register.filter
@safe
def entry_actor_link(value, request=None):
  """
  Returns an actor html link.

  value     an entry_actor object.
  request   a HttpRequest (optional).
  """
  return '<a href="%s">%s</a>' % (models.actor_url(url_nick(value),
                                                   'user',
                                                   request=request),
                                  display_nick(value))

class URLForNode(template.Node):
  def __init__(self, entity, request):
    self.entity = template.Variable(entity)
    self.request = template.Variable(request)

  def render(self, context):
    try:
      actual_entity = self.entity.resolve(context)
      actual_request = self.request.resolve(context)

      try:
        return actual_entity.url(request=actual_request)
      except AttributeError:
        # treat actual_entity as a string
        try:
          mobile = actual_request.mobile
        except AttributeError:
          mobile = False

        if mobile and settings.SUBDOMAINS_ENABLED:
          return 'http://m.' + settings.HOSTED_DOMAIN
        else:
          return 'http://' + str(actual_entity)

    except template.VariableDoesNotExist:
      return ''

@register.tag
def url_for(parser, token):
  """
  Custom tag for more easily being able to pass an HttpRequest object to
  underlying url() functions.
  
  One use case is being able to return mobile links for mobile users and
  regular links for others. This depends on request.mobile being set or
  not.

  Observe that if entity is not an object with the method url(), it is
  assumed to be a string.

  Parameters: entity, request.
  """
  try:
    tag_name, entity, request = token.split_contents()
  except ValueError:
    raise template.TemplateSyntaxError, \
      "%r tag requires exactly two arguments" % token.contents.split()[0]
  return URLForNode(entity, request)

class ActorLinkNode(template.Node):
  def __init__(self, actor, request):
    self.actor = template.Variable(actor)
    self.request = template.Variable(request)

  def render(self, context):
    try:
      actual_actor = self.actor.resolve(context)
      actual_request = self.request.resolve(context)

      try:
        url = actual_actor.url(request=actual_request)
        return '<a href="%s">%s</a>' % (url, actual_actor.display_nick())
      except AttributeError:
        return ''
    except template.VariableDoesNotExist:
      return ''

@register.tag
def actor_link(parser, token):
  """
  Custom tag for more easily being able to pass an HttpRequest object to
  underlying url() functions.
  
  One use case is being able to return mobile links for mobile users and
  regular links for others. This depends on request.mobile being set or
  not.

  Parameters: actor, request.
  """
  try:
    tag_name, actor, request = token.split_contents()
  except ValueError:
    raise template.TemplateSyntaxError, \
      "%r tag requires exactly two arguments" % token.contents.split()[0]
  return ActorLinkNode(actor, request)
