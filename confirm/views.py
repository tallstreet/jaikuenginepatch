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

import logging

from django import http
from django import template
from django.conf import settings
from django.template import loader

from common import api
from common import decorator
from common import exception
from common import util

@decorator.login_required
def confirm_email(request, code):
  rel_ref = api.activation_activate_email(request.user,
                                          request.user.nick,
                                          code)
  return util.RedirectFlash(request.user.url() + "/overview",
                            "Email address '%s' confirmed." % rel_ref.target)
