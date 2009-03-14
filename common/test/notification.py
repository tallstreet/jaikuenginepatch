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

from common import api
from common import exception
from common import mail as common_mail
from common import sms
from common.protocol import xmpp
from common.test import base

class NotificationTest(base.FixturesTestCase):
  """ tests as per the Notifications Design section of doc/design_funument.txt

   * Uu - A simple update posted in a User's stream (you're subscribed).
   * Uc - A simple update posted in a Channel's stream (you're subscribed).
   * Eu - An external feed update posted in a User's stream (you're
     subscribed).
   * Ec - An external feed update posted in a Channel's stream (you're
     subscribed).
   * Cu - A comment posted to a User's entry by a User whose comment stream
     you are subscribed to.
   * Cc - A comment posted to a Channel's entry by a User whose comment stream
     you are subscribed to.
   * Cs - A comment posted to an entry created by you.
   * Cx - A comment posted to an entry you have also commented on.

  oneliner: email[Cs, Cx]; sms[Cs, Cx, Uu, Uc]; im[Cs, Cx, Uu, Uc, Cu]
  
  """

  # Cs:
  #   email
  #   sms
  #   im
  # comment by unpopular on popular's entry
  def test_comment_self(self):
    pass

  # Cx:
  #   email
  #   sms
  #   im
  # comment by hermit on popular's entry with a comment by unpopular
  def test_comment_comment(self):
    pass
  
  # Uu:
  #   sms
  #   im
  # update by popular
  def test_update_user(self):
    pass


  # Uc:
  #   sms
  #   im
  # update by unpopular in #popular
  def test_update_channel(self):
    pass


  # Cu:
  #   im
  # comment on 
  def test_comment_user(self):
    pass


  # Cc:
  #   none
  # comment by popular on own post in #popular
  def test_comment_channel(self):
    pass

