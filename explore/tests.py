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
