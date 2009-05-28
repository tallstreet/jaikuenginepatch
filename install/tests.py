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
from google.appengine.api import users

from common import api
from common.test import base

def _true():
  return True

class InstallTest(base.ViewTestCase):
  
  # override fixtures, so that there is no root user
  fixtures = []

  def patch_users(self):
    users.get_current_user_old = users.get_current_user
    users.get_current_user = _true
    users.is_current_user_admin_old = users.is_current_user_admin
    users.is_current_user_admin = _true

  def unpatch_users(self):
    users.get_current_user = users.get_current_user_old
    users.is_current_user_admin = users.is_current_user_admin_old

  def setUp(self):
    super(InstallTest, self).setUp()
    self.patch_users()

  def tearDown(self):
    super(InstallTest, self).tearDown()
    self.unpatch_users()

  def test_noroot(self):
    r = self.client.get('/install')
    self.assertContains(r, 'Make the root user')

  def test_root(self):
    api.user_create_root(api.ROOT)
    r = self.client.get('/install')
    self.assertContains(r, 'Root User root@example.com exists')

