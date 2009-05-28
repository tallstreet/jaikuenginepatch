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

from django import template
from django.template.loader_tags import ExtendsNode

register = template.Library()

class IncludeExtendNode(template.Node):
  """
  The node that implements include_extend.

  Note that we can't inherit from ExtendsNode as only one ExtendsNode is
  allowed in a template, although the implementation is exactly the same.
  """
  def __init__(self, nodelist, parent_name, parent_name_expr, template_dirs=None):
    self.impl = ExtendsNode(nodelist, parent_name, parent_name_expr,
                              template_dirs)
  def render(self, context):
    return self.impl.render(context)

def do_include_extend(parser, token):
  """
  A tag to include a template with the ability to replace blocks like with
  'extends'. Use like:

  {% include_extend 'foo' %}
    {% block bar %}...{% endblock %}
  {% endinclude_extend %}

  This is supposed to be used when you want to override bits of a template but
  don't plan to reuse the version on any other page, so that the overhead of
  doing that is kept to a minimum, encouraging reuse.

  Parsing copied from django's do_extend.
  """
  bits = token.contents.split()
  if len(bits) != 2:
      raise template.TemplateSyntaxError, "'%s' takes one argument" % bits[0]
  parent_name, parent_name_expr = None, None
  if bits[1][0] in ('"', "'") and bits[1][-1] == bits[1][0]:
      parent_name = bits[1][1:-1]
  else:
      parent_name_expr = parser.compile_filter(bits[1])
  nodelist = parser.parse(('end' + bits[0],))
  parser.delete_first_token()
  return IncludeExtendNode(nodelist, parent_name, parent_name_expr)

register.tag('include_extend', do_include_extend)

class IfPredNode(template.Node):
  def __init__(self, var1, var2, predicate, nodelist_true, nodelist_false):
    self.var1, self.var2 = template.Variable(var1), template.Variable(var2)
    self.nodelist_true, self.nodelist_false = nodelist_true, nodelist_false
    self.predicate = predicate

  def render(self, context):
    try:
      val1 = self.var1.resolve(context)
    except VariableDoesNotExist:
      val1 = None
    try:
      val2 = self.var2.resolve(context)
    except VariableDoesNotExist:
      val2 = None

    predicate = self.predicate
    if (predicate(val1, val2)):
      return self.nodelist_true.render(context)
    return self.nodelist_false.render(context)

def if_pred(parser, token, predicate):
  bits = list(token.split_contents())
  if len(bits) != 3:
    raise template.TemplateSyntaxError, "%r takes two arguments" % bits[0]
  end_tag = 'end' + bits[0]
  nodelist_true = parser.parse(('else', end_tag))
  token = parser.next_token()
  if token.contents == 'else':
    nodelist_false = parser.parse((end_tag,))
    parser.delete_first_token()
  else:
    nodelist_false = template.NodeList()
  return IfPredNode(bits[1], bits[2], predicate, nodelist_true, nodelist_false)
