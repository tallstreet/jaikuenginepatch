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

import epydoc
from epydoc import docparser
from epydoc import apidoc

a = docparser.parse_docs(name='common.api.post')
#print a

#print apidoc.pp_apidoc(a, depth=2)

#for d in a.decorators:
#  print d
#print '%s(%s, **%s):' % (a.canonical_name, a.posargs, a.kwarg)
#print a.docstring




def markdown_docs(api_doc):
  sig_template = '**%(shortname)s** (%(args_list)s)'
  dec_template = ' * %(decorator)s'

  shortname = str(api_doc.canonical_name).split('.')[-1]
  args_list = ', '.join(api_doc.posargs)
  if api_doc.kwarg:
    args_list += ', **%s' % api_doc.kwarg
  
  o = [sig_template % {'shortname': shortname, 'args_list': args_list},
       '']
  for d in api_doc.decorators:
    o.append(dec_template % {'decorator': d})
  
  o.append('')
  o.append(api_doc.docstring)
  return '\n'.join(o)


print markdown_docs(a)
