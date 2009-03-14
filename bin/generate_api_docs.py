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

"""
a script to generate docs for the public api

"""
import sys
import os.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
  import roman
except ImportError:
  print "Could not import module 'roman,' docutils has not been installed properly"
  print "Please install docutils: http://docutils.sourceforge.net"
  sys.exit(1)

import epydoc
from epydoc import docparser
from epydoc import apidoc

from appengine_django import InstallAppengineHelperForDjango
InstallAppengineHelperForDjango()

from common import api

DOC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'doc')

def rst_docs(api_doc):
  sig_template = '**%(shortname)s** (%(args_list)s)'
  dec_template = ' * %(decorator)s'

  shortname = str(api_doc.canonical_name).split('.')[-1]
  args_list = ', '.join(api_doc.posargs)
  if api_doc.kwarg:
    args_list += ', \*\*%s' % api_doc.kwarg
  
  o = [sig_template % {'shortname': shortname, 'args_list': args_list},
       '']
  #for d in api_doc.decorators:
  #  o.append(dec_template % {'decorator': d})
  
  o.append('')
  if api_doc.docstring != apidoc.UNKNOWN:
    o.append(api_doc.docstring)
  else:
    o.append('No additional documentation')
  return '\n'.join(o)


def main():
  a = docparser.parse_docs(name='common.api')
  #print a

  variables = a.apidoc_links(imports=False, 
                             packages=False, 
                             submodules=False,
                             bases=False,
                             subclasses=False,
                             private=False,
                             overrides=False)


  public_api_methods = api.PublicApi.methods.keys()
  public_decorators = ['throttle', 'owner_required']

  allowed_names = public_api_methods + public_decorators

  for v in variables:
    if v.name in public_api_methods:
      prefix = "method"
    elif v.name in public_decorators:
      prefix = "deco"
    else:
      continue

    filename = '%s_%s.txt' % (prefix, v.name)
    path = os.path.join(DOC_DIR, filename)

    docs = rst_docs(v.value)
    
    f = open(path, 'w')
    f.write(docs)
    f.close()


if __name__ == '__main__':
  main()
