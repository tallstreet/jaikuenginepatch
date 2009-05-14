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
import urlparse
import smtplib

from django.conf import settings
from django import template
from django.template import loader
from django.core import mail

from common import exception
from common import util

def is_allowed_to_send_email_to(email):
  if settings.EMAIL_LIMIT_DOMAIN:
    limit_email = re.compile(r'.+@%s$' % (settings.EMAIL_LIMIT_DOMAIN))
    return limit_email.match(email)

  if settings.EMAIL_TEST_ONLY and email not in settings.EMAIL_TEST_ADDRESSES:
    return False
  return True

def _greeting_name(actor_ref):
  try:
    return actor_ref.extra['given_name']
  except KeyError:
    return actor_ref.display_nick()

def _full_name(actor_ref):
  try:
    return "%s %s" % (actor_ref.extra['given_name'],
        actor_ref.extra['family_name'])
  except KeyError:
    return actor_ref.display_nick()

def log_blocked_send(on_behalf, email, subject, message=None):
  logging.info("Not sending an email on behalf of %s to a blocked address to %s: %s",
               on_behalf, email, subject)
  if message:
    logging.info("MSG: \n%s", message)

def send(to_email, subject, message, on_behalf=None, html_message=None):
  on_behalf = on_behalf and on_behalf or settings.DEFAULT_FROM_EMAIL
  if is_allowed_to_send_email_to(to_email):
    email_message = mail.EmailMultiAlternatives(subject=subject,
        body=message,
        from_email=on_behalf,
        to=(to_email,))
    if html_message:
      email_message.attach_alternative(html_message, mimetype="text/html")
    # uses the default email sender, see DEFAULT_FROM_EMAIL in settings.py
    # if on_behalf is None
    fail_silently = settings.MANAGE_PY
    return email_message.send(fail_silently)
  else:
    log_blocked_send(on_behalf, to_email, subject, message)
    raise exception.ValidationError("Cannot send to that email address")
  

def filter_out_blocked_addresses(message_tuples):
  send_count = 0
  allowed = []
  for subject, message, from_email, recipients in message_tuples:
    blocked = [r for r in recipients if not is_allowed_to_send_email_to(r)]
    for r in blocked:
      log_blocked_send(from_email, r, subject)
      send_count += 1
    allowed_recipients = [r for r in recipients if not r in blocked]
    allowed.append((subject, message, from_email, allowed_recipients))
  return (allowed, send_count)

def mass_send(message_tuples):
  send_count = 0
  allowed, fake_send_count = filter_out_blocked_addresses(message_tuples)
  send_count += fake_send_count
  send_count += mail.send_mass_mail(tuple(allowed))
  return send_count


def email_comment_notification(actor_to_ref, actor_from_ref, 
                               comment_ref, entry_ref):
    
  """Send an email in response to a comment being posted.
  PARAMETERS:
    actor_to_ref - actor whom this email is going to
    actor_from_ref - actor who posted the comment
    comment_ref - the comment that was posted
    entry_ref - the entry that was commented on
  RETURNS: (subject, message)
  """

  entry_url = entry_ref.url()
  entry_mobile_url = entry_ref.url(mobile=True)
  from_name = actor_from_ref.display_nick()
  my_entry = (actor_to_ref.nick == entry_ref.actor)
  entry_actor_name = util.display_nick(entry_ref.actor)
  entry_title = entry_ref.title()

  
  # TODO(termie) pretty 'r up
  comment_pretty = comment_ref.extra.get('content', '')

  t = loader.get_template('common/templates/email/email_comment.txt')
  c = template.Context(locals(), autoescape=False)
  message = t.render(c)
  subject = 'New comment on %s' % (entry_ref.title())
  return (subject, message)

def email_confirmation_message(actor, activation_code):
  name = _greeting_name(actor)
  # TODO(teemu): what is a canonical way to do get URLs in Django?
  activation_url = 'http://%s/confirm/email/%s' % (settings.DOMAIN, activation_code)
  activation_mobile_url = 'http://m.%s/confirm/email/%s' % (settings.DOMAIN,
                                                            activation_code)

  email_first = name
  email_link = activation_url
  email_mobile_link = activation_mobile_url

  t = loader.get_template('common/templates/email/email_confirm.txt')
  c = template.Context(locals(), autoescape=False)
  message = t.render(c)
  c.autoescape = True
  html_template = loader.get_template(
      'common/templates/email/email_confirm.html')
  html_message = html_template.render(c)
  subject = "Welcome! Confirm your email"
  return (subject, message, html_message)

def email_invite(from_actor_ref, invite_code):
  full_name = _full_name(from_actor_ref)
  nick_name = from_actor_ref.display_nick()
  accept_url = 'http://%s/invite/email/%s' % (settings.DOMAIN, invite_code)
  accept_mobile_url = 'http://m.%s/invite/email/%s' % (settings.DOMAIN,
                                                       invite_code)

  t = loader.get_template('common/templates/email/email_invite.txt')
  c = template.Context(locals(), autoescape=False)
  message = t.render(c)
  c.autoescape = True
  html_template = loader.get_template(
      'common/templates/email/email_invite.html')
  html_message = html_template.render(c)
  subject = '%s invited you to %s' % (full_name, settings.SITE_NAME)
  return (subject, message, html_message)

def email_new_follower(owner_ref, target_ref):
  email_url = owner_ref.url()
  email_mobile_url = owner_ref.url(mobile=True)

  t = loader.get_template('common/templates/email/email_new_follower.txt')
  c = template.Context(locals(), autoescape=False)
  message = t.render(c)
  c.autoescape = True
  html_template = loader.get_template(
      'common/templates/email/email_new_follower.html')
  html_message = html_template.render(c)
  subject = '%s now follows you' % owner_ref.display_nick()
  return (subject, message, html_message)

def email_new_follower_mutual(owner_ref, target_ref):
  profile_url = owner_ref.url()
  profile_mobile_url = owner_ref.url(mobile=True)
  full_name = _full_name(owner_ref)

  t = loader.get_template(
      'common/templates/email/email_new_follower_mutual.txt')
  c = template.Context(locals(), autoescape=False)
  message = t.render(c)
  c.autoescape = True
  html_template = loader.get_template(
      'common/templates/email/email_new_follower_mutual.html')
  html_message = html_template.render(c)
  subject = '%s is now following you, too' % full_name
  return (subject, message, html_message)

def email_lost_password(actor, email, code):
  email_link = ("http://%s/login/reset?email=%s&hash=%s" %
                (settings.DOMAIN, email, code))
  email_mobile_link = ("http://m.%s/login/reset?email=%s&hash=%s" %
                       (settings.DOMAIN, email, code))

  t = loader.get_template('common/templates/email/email_password.txt')
  c = template.Context(locals(), autoescape=False)
  message = t.render(c)
  c.autoescape = True
  html_template = loader.get_template(
      'common/templates/email/email_password.html')
  html_message = html_template.render(c)

  subject = ('Password reset')
  return (subject, message, html_message)
