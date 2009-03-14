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


urlpatterns = patterns('actor.views',
    (r'^invite$', 'actor_invite'),
    (r'^contacts$', 'actor_contacts'),
    (r'^contacts/(?P<format>json|xml|atom)$', 'actor_contacts'),
    (r'^followers$', 'actor_followers'),
    (r'^followers/(?P<format>json|xml|atom)$', 'actor_followers'),
    (r'^presence/(?P<item>[\da-f]+|last)/(?P<format>json|xml|atom)$', 'actor_item'),
    (r'^presence/(?P<item>[\da-f]+|last)$', 'actor_item'),
    #(r'^presence/(?P<format>json|xml|atom)$', 'presence_current'),
    #(r'^presence$', 'presence_current'),
    (r'^(?P<format>json|xml|atom|rss)$', 'actor_history'),
    (r'^feed/(?P<format>json|xml|atom|rss)$', 'actor_history'),
    (r'^contacts/feed/(?P<format>json|xml|atom|rss)$', 'actor_overview'),
    (r'^overview/(?P<format>json|xml|atom|rss)$', 'actor_overview'),
    (r'^overview$', 'actor_overview', {"format": "html"}),
    (r'^$', 'actor_history', {'format': 'html'}),
    (r'^settings$', 'actor_settings'),
    (r'^settings/(?P<page>\w+)$', 'actor_settings'),
)


handler404 = 'common.views.common_404'
handler500 = 'common.views.common_500'
