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

import glob
import logging
import os
import re
import sys
import zipfile
import os.path


ZIP_SKIP_RE = re.compile('\.svn|\.pyc|\.[pm]o')
IGNORED_CONTRIB = ('admin', 'gis', 'comments', 'localflavor', 'databrowse')
ROOT_DIR = os.path.dirname(__file__)
DOC_DIR = os.path.join(ROOT_DIR, 'doc')
RST_TEMPLATE_PATH = os.path.join(DOC_DIR, 'template.rst2html')
API_TEMPLATE_DIR = os.path.join(ROOT_DIR, 'api', 'templates')

def bootstrap(only_check_for_zips=False):
  logging.info('Beginning bootstrap...')
  l = os.listdir('vendor')
  for vendor_lib in l:
    if vendor_lib.startswith('.'):
      continue
    if only_check_for_zips and os.path.exists('%s.zip' % vendor_lib):
      continue
    logging.info('Building zip for %s...' % vendor_lib)
    zip_vendor_lib(vendor_lib)
  logging.info('Finishing bootstrap.')

def monkey_patch_skipped_files():
  logging.info('Monkey patching dev_appserver...')
  from google.appengine.tools import dev_appserver as da

  def _patch(logical_filename, normcase=os.path.normcase):
    """Determines if a file's path is accessible.

    This is an internal part of the IsFileAccessible implementation.

    Args:
      logical_filename: Absolute path of the file to check.
      normcase: Used for dependency injection.

    Returns:
      True if the file is accessible, False otherwise.
    """
    if da.IsPathInSubdirectories(logical_filename, [da.FakeFile._root_path],
                              normcase=normcase):
      relative_filename = logical_filename[len(da.FakeFile._root_path):]

      #if da.FakeFile._skip_files.match(relative_filename):
      #  logging.warning('Blocking access to skipped file "%s"',
      #                  logical_filename)
      #  return False

      if da.FakeFile._static_file_config_matcher.IsStaticFile(relative_filename):
        logging.warning('Blocking access to static file "%s"',
                        logical_filename)
        return False

    if logical_filename in da.FakeFile.ALLOWED_FILES:
      return True

    if da.IsPathInSubdirectories(logical_filename,
                              da.FakeFile.ALLOWED_SITE_PACKAGE_DIRS,
                              normcase=normcase):
      return True

    allowed_dirs = da.FakeFile._application_paths | da.FakeFile.ALLOWED_DIRS
    if (da.IsPathInSubdirectories(logical_filename,
                               allowed_dirs,
                               normcase=normcase) and
        not da.IsPathInSubdirectories(logical_filename,
                                   da.FakeFile.NOT_ALLOWED_DIRS,
                                   normcase=normcase)):
      return True

    return False
  
  da.FakeFile._IsFileAccessibleNoCache = staticmethod(_patch)

def generate_api_docs():
  logging.info('Generating api docs...')
  from epydoc import docparser

  try:
    import roman
  except ImportError:
    print ("Could not import module 'roman,' docutils has not been installed"
          "properly")
    print "Please install docutils: http://docutils.sourceforge.net"
    sys.exit(1)

  from common import api
  
  a = docparser.parse_docs(name='common.api')
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

    logging.info('  for %s...' % v.name)

    docs = rst_docs(v.value)
    
    f = open(path, 'w')
    f.write(docs)
    f.close()
  logging.info('Finished generating api docs.')

def build_docs():
  logging.info('Building html docs...')
  txts = glob.glob(os.path.join(DOC_DIR, '*.txt')) 
  for t in txts:
    basename = os.path.basename(t)
    baseroot, ext = os.path.splitext(basename)
    outname = os.path.join(API_TEMPLATE_DIR, 'built_%s.html' % baseroot)

    logging.info('  for %s...' % baseroot)

    infile = open(t)
    outfile = open(outname, 'w')

    rst_to_html(infile, outfile)
    infile.close()
    outfile.close()
  
  logging.info('Finished building html docs.')

def clean(skip_zip=False):
  # TODO(termie): running this multiple times will tend to create zip files
  #               and then delete them
  logging.info('Removing built files...')
  # clean up docs, built html and zip files
  if not skip_zip:
    zipfiles = glob.glob(os.path.join(ROOT_DIR, '*.zip'))
  else:
    zipfiles = []
  api_methods = glob.glob(os.path.join(DOC_DIR, 'method_*'))
  api_decos = glob.glob(os.path.join(DOC_DIR, 'deco_*'))
  html_docs = glob.glob(os.path.join(API_TEMPLATE_DIR, 'built_*'))
  
  all_to_remove = zipfiles + api_methods + api_decos + html_docs
  for filename in all_to_remove:
    os.unlink(filename)

  logging.info('Finished removing built files.')
  

def rst_to_html(infile, outfile):
  import docutils.core

  docutils.core.publish_file(
      source=infile,
      destination=outfile,
      writer_name='html',
      settings_overrides={'default_template_path': RST_TEMPLATE_PATH,
                          'doctitle_xform': False}
      )

def rst_docs(api_doc):
  from epydoc import apidoc

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

def _strip_contrib(dirnames):
  for d in IGNORED_CONTRIB:
    try:
      dirnames.remove(d)
    except ValueError:
      pass

def zip_vendor_lib(lib):
  f = zipfile.ZipFile('%s.zip' % lib, 'w')

  for dirpath, dirnames, filenames in os.walk('vendor/%s' % lib):
    if dirpath == os.path.join('vendor', lib, 'contrib'):
      _strip_contrib(dirnames)

    for filename in filenames:
      name = os.path.join(dirpath, filename)
      if ZIP_SKIP_RE.search(name):
        logging.debug('Skipped (skip_re): %s', name)
        continue
      if not os.path.isfile(name):
        logging.debug('Skipped (isfile): %s', name)
        continue
      logging.debug('Adding %s...', name)
      f.write(name, name[len('vendor/'):], zipfile.ZIP_DEFLATED)

  f.close()
