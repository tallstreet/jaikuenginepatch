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

from common import exception

class Connection(object):
  pass

class Service(object):
  connection = None 
  handlers = None
  _handlers = None

  def __init__(self, connection):
    self.connection = connection
    self._handlers = []

  def init_handlers(self):
    if not self.handlers:
      return

    for handler_class in self.handlers:
      self._handlers.append(handler_class(self))

  def handle_message(self, sender, target, message):
    matched = None
    handler = None
    for h in self._handlers:
      matched = h.match(sender, message)
      if matched:
        handler = h
        break

    if not matched:
      rv = self.unknown(sender, message)
      return self.response_ok(rv)

    try:
      rv = handler.handle(sender, matched, message)
      return self.response_ok(rv)
    except exception.UserVisibleError, e:
      exception.log_exception()
      self.send_message([sender], str(e))
      return self.response_error(e)
    except exception.Error:
      exception.log_exception()
