#!/usr/bin/env python
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

import getpass
import logging
import os
import optparse
import sys

sys.path.append(".")
sys.path.append("./vendor")

from appengine_django import InstallAppengineHelperForDjango
InstallAppengineHelperForDjango()

from google.appengine.ext.remote_api import remote_api_stub
from google.appengine.ext import db

from common import models
from common import util

class ChannelCountBackfiller(object):
  """Backfills the channel_count extra property for all users.

  This script should be idempotent - running it again would merely overwrite the
  previous result.

  Make sure to run it from the top jaikuengine directory. The following command
  would execute the script against a local testing instance:
  './bin/backfill_channel_count.py -w 1 -s localhost:8080'
  """

  def __init__(self, do_write):
    self._do_write = do_write

  def get_channel_count(self, actor_nick):
    """Returns the number of channels the actor is a member of."""
    batch_size = 1000
    count = 0
    q = self.get_channel_relationship_query(actor_nick)
    memberships = q.fetch(batch_size)
    while memberships:
      count += len(memberships)
      q = self.get_channel_relationship_query(actor_nick)
      q.filter("__key__ >", memberships[-1].key())
      memberships = q.fetch(batch_size)

    return count

  def get_channel_relationship_query(self, actor_nick):
    q = models.Relation.all(keys_only=True)
    q.filter("relation =", "channelmember")
    q.filter("target =", actor_nick)
    q.order("__key__")
    return q

  def get_actor_query(self):
    q = models.Actor.all()
    q.order("__key__")
    return q

  def run(self, batch_size=100):
    """Updates the channel_count extra property for users."""
    actor_refs = self.get_actor_query().fetch(batch_size)
    actors_processed = 0
    while actor_refs:
      to_put = []
      for actor_ref in actor_refs:
        if not util.is_channel_nick(actor_ref.nick):
          actor_ref.extra["channel_count"] \
              = self.get_channel_count(actor_ref.nick)
          to_put.append(actor_ref)
          if not self._do_write:
            logging.info("Would have set channel_count to %d for %s",
                         actor_ref.extra["channel_count"],
                         actor_ref.nick)

      if to_put and self._do_write:
        db.put(to_put)
      actors_processed += len(actor_refs)
      logging.info("Processed %d actors...", actors_processed)
      q = self.get_actor_query()
      q.filter("__key__ >", actor_refs[-1].key())
      actor_refs = q.fetch(batch_size)


def auth_function():
  return (raw_input("Username: "), getpass.getpass("Password:"))

def main():
  parser = optparse.OptionParser()
  parser.add_option("-b", "--actor_batch_size", dest="actor_batch_size",
                    default=100,
                    help="number of actors to fetch in a single query")
  parser.add_option("-w", "--write", dest="write", action="store_true",
                    default=False, help="write results back to data store")
  parser.add_option("-a", "--app_id", dest="app_id",
                    help="the app_id of your app, as declared in app.yaml")
  parser.add_option("-s", "--servername", dest="servername",
                    help="the hostname your app is deployed on. Defaults to"
                         "<app_id>.appspot.com")
  (options, args) = parser.parse_args()
  remote_api_stub.ConfigureRemoteDatastore(app_id=options.app_id,
                                           path='/remote_api',
                                           auth_func=auth_function,
                                           servername=options.servername)

  ChannelCountBackfiller(options.write).run(int(options.actor_batch_size))

if __name__ == "__main__":
  main()
