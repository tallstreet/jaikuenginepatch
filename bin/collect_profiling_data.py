#!/usr/local/bin/python

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

import optparse
import urllib
import urllib2

parser = optparse.OptionParser()
parser.add_option('--db', action='store_const', const='db',
                  dest='profile_type',
                  help='profile the db calls')
parser.add_option('-o', '--out', action='store', 
                  dest='output_file',
                  help='directory to put profiling data')
parser.add_option('-d', '--data', action='store', dest='data',
                  help='post data to include in the request')
parser.set_defaults(profile_type='db',
                    )


def fetch_profile(url, profile_type='db', data=None):
  headers = {'X-Profile': profile_type}

  req = urllib2.Request(url, data, headers)
  resp = urllib2.urlopen(req)
  
  return resp.read()

def main(options, args):
  if not args:
    raise Exception('need to specify a url')
  
  url = args[0]
  profile_type = getattr(options, 'profile_type', 'db')
  data = getattr(options, 'data', None)
  output_file = getattr(options, 'output_file', None)

  rv = fetch_profile(url, profile_type, data)
  
  if output_file:
    f = open(output_file, 'w')
    f.write(rv)
    f.close()
  else:
    print rv
  

  



if __name__ == '__main__':
  (options, args) = parser.parse_args()
  
  main(options, args)
