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

from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^$',
        'django.views.generic.simple.redirect_to',
        {'url': '/docs'}),
    (r'^api(?P<the_rest>/.*)$',
        'django.views.generic.simple.redirect_to',
        {'url': '%(the_rest)s'}),
    (r'^keys$', 'api.views.api_keys'),
    (r'^keys/(?P<consumer_key>\w+)$', 'api.views.api_key'),
    (r'^key$', 'api.views.api_key_legacy'),
    (r'^tokens', 'api.views.api_tokens'),
    (r'^docs$', 'api.views.api_docs'),
    (r'^docs/(?P<doc>\w+)$', 'api.views.api_doc'),
    (r'^json', 'api.views.api_call'),
    (r'^loaddata', 'api.views.api_loaddata'),
    (r'^cleardata', 'api.views.api_cleardata'),
    (r'^request_token', 'api.views.api_request_token'),
    (r'^authorize', 'api.views.api_authorize'),
    (r'^access_token', 'api.views.api_access_token'),
    (r'^sms_receive/(?P<vendor_secret>.*)$', 'api.views.api_vendor_sms_receive'),
    (r'^process_queue$', 'api.views.api_vendor_queue_process'),
    (r'^xmlrpc', 'api.views.api_xmlrpc'),
)


handler404 = 'common.views.common_404'
handler500 = 'common.views.common_500'
