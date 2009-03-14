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
from common.util import create_nonce, safe

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
def format_actor_links(value, arg=None):
  """Formats usernames / channels
  """
  def user_replace(match):
    return '<a href="%s">@%s</a>' % (
        models.actor_url(match.group(1), 'user'), match.group(1))

  value = re.sub(user_regex, user_replace, value)

  def channel_replace(match):
    return '<a href="%s">#%s</a>' % (
        models.actor_url(match.group(1), 'channel'), match.group(1))
  
  value = re.sub(channel_regex, channel_replace, value)
  return value

@register.filter(name="format_markdown")
@safe
def format_markdown(value, arg=None):
  return markdown2.markdown(value)

@register.filter(name="format_comment")
@safe
def format_comment(value, arg=None):
  content = escape(value.extra.get('content', 'no title'))
  content = format_markdown(content)
  content = format_autolinks(content)
  content = format_actor_links(content)
  return content


@register.filter(name="truncate")
def truncate(value, arg=30):
  arg = int(arg)
  return value[:arg]
  #return value.content

@register.filter
@safe
def actor_link(value, arg=None):
  return '<a href="%s">%s</a>' % (value.url(), value.display_nick())

@register.filter(name="entry_icon")
@safe
def entry_icon(value, arg=None):
  icon = value.extra.get('icon', None)
  if not icon:
    return ""

  return '<img src="/themes/%s/icons/%s.gif" alt="%s" class="icon" />' % (settings.DEFAULT_THEME, icon, icon)

@register.filter(name="linked_entry_title")
@safe
def linked_entry_title(value, arg=None):
  return '<a href="%s">%s</a>' % (
      value.url(), 
      format_fancy(escape(value.extra['title'])).replace('\n', ' '))


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


