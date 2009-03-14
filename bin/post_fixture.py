#!/bin/env python
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

import urllib
import urllib2

def main(url, fixture):
  
  f = open(fixture)
  params = {"format": "json",
            "fixture": f.read()}
  f.close()

  data = urllib.urlencode(params)
  rv = urllib.urlopen(url, data)

  print rv.read()

if __name__ == "__main__":
  import sys
  url = sys.argv[1]
  fixture = sys.argv[2]
  main(url, fixture)
