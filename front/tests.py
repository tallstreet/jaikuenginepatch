from common import profile
from common.tests import ViewTestCase


class SmokeTest(ViewTestCase):
  def test_public_frontpage_logged_in(self):
    self.login('popular')
    
    l = profile.label('front_get_logged_in')
    r = self.client.get('/')
    l.stop()

    r = self.assertRedirectsPrefix(r, '/user/popular/overview')
    self.assertTemplateUsed(r, 'actor/templates/overview.html')
    self.assertWellformed(r)

  def test_public_frontpage(self):
    
    l = profile.label('front_get_public')
    r = self.client.get('/')
    l.stop()

    self.assertTemplateUsed(r, 'front/templates/front.html')
    self.assertWellformed(r)
