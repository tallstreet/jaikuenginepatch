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

class WhitespaceMiddleware(object):
  """Class to strip leading and trailing whitespace from all form fields.

  Note that files are not in POST but in FILES, so this will not touch binary
  data.

  If it turns out that this breaks something we can add an url white/blacklist.
  """
  def _strip_from_values(self, qdict):
    copy = None
    for k, v in qdict.items():
      stripped = v.strip()
      if not v == stripped:
        if not copy:
          copy = qdict.copy()
        copy[k] = stripped
    if copy:
      return copy
    return qdict

  def process_request(self, request):
    request.GET = self._strip_from_values(request.GET)
    request.POST = self._strip_from_values(request.POST)
