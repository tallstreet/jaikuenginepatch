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

from django.conf import settings

from common import api
from common import util

def generate_personal_key(actor_ref):
  salt = settings.LEGACY_SECRET_KEY
  nick = actor_ref.display_nick()
  password = actor_ref.password
  import logging
  to_hash = '%s%sapi_key%s' % (nick, password, salt)
  hashed = util.sha1(to_hash)

  return hashed[10:-12]

def authenticate_user_personal_key(nick, key):
  actor_ref = api.actor_get(api.ROOT, nick)
  check_key = generate_personal_key(actor_ref)

  if check_key != key:
    return None

  actor_ref.access_level = api.WRITE_ACCESS
  return actor_ref

