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

"""User-visible strings for confirmation and flash messages.
"""

__author__ = 'mikie@google.com (Mika Raento)'

# api call -> (confirmation message, flash message)
# If the confirmation message is None, no confirmation is required.
_message_table__ = {
  'activation_activate_mobile':
      (None,
       'Mobile activated.'),
  'activation_request_email':
      (None,
       'Email confirmation has been sent.'),
  'activation_request_mobile':
      (None,
       'Mobile activation code has been sent.'),
  'actor_add_contact':
      (None,
       'Contact added.'),
  'actor_remove' :
      (None,
       'Deleted'),
  'actor_remove_contact':
      (None,
       'Contact removed.'),
  'channel_create':
      (None,
       'Channel created'),
  'channel_join':
      (None,
       'You have joined the channel.'),
  'channel_update':
      (None,
       'Channel settings updated.'),
  'channel_part':
      (None,
       'You have left the channel.'),
  'channel_post':
      (None,
       'Message posted.'),
  'entry_add_comment':
      (None,
       'Comment added.'),
  'entry_mark_as_spam':
      ('Mark this item as spam',
       'Marked as spam.'),
  'entry_remove' :
      ('Delete this post',
       'Post deleted.'),
  'entry_remove_comment':
      ('Delete this comment',
       'Comment deleted.'),
  'invite_accept':
      (None,
       'Invitation accepted'),
  'invite_reject':
      (None,
       'Invitation rejected'),
  'invite_request_email':
      (None,
       'Invitation sent'),
  'login_forgot':
      (None,
       'New Password Emailed'),
  'oauth_consumer_delete':
      ('Delete this key',
       'API Key deleted'),
  'oauth_consumer_update':
      (None,
       'API Key information updated'),
  'oauth_generate_consumer':
      (None,
       'New API key generated'),
  'oauth_revoke_access_token':
      (None,
       'API token revoked.'),
  'presence_set':
      (None,
       'Location updated'),
  'post':
      (None,
       'Message posted.'),
  'settings_change_notify':
      (None,
       'Settings updated.'),
  'settings_change_privacy':
      (None,
       'privacy updated'),
  'settings_hide_comments':
      (None,
       'Comments preferenced stored.'),
  'settings_update_account':
      (None,
       'profile updated'),
  'subscription_remove':
      (None,
       'Unsubscribed.'),
  'subscription_request':
      (None,
       'Subscription requested.'),
}

def confirmation(api_call):
  msg = title(api_call)
  if msg is None:
    return None
  return ('Are you sure you want to ' +
          msg +
          '?')

def title(api_call):
  if _message_table__.has_key(api_call):
    return _message_table__[api_call][0]
  return None

def flash(api_call):
  return _message_table__[api_call][1]
