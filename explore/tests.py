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
from common import normalize
from common import profile
from common import util
from common.tests import ViewTestCase

class ExploreTest(ViewTestCase):

  def test_explore_when_signed_out(self):
    
    l = profile.label('explore_get_public')
    r = self.client.get('/explore')
    l.stop()
    
    self.assertContains(r, "Latest Public Posts")
    self.assertTemplateUsed(r, 'explore/templates/recent.html')

  def test_explore_when_signed_in(self):
    self.login('popular')
    
    l = profile.label('explore_get_logged_in')
    r = self.client.get('/explore')
    l.stop()

    self.assertContains(r, "Latest Public Posts")
    self.assertTemplateUsed(r, 'explore/templates/recent.html')

  def test_rss_and_atom_feeds(self):
    r = self.client.get('/explore')
    self.assertContains(r, 'href="/explore/rss"')
    self.assertContains(r, 'href="/explore/atom"')
