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
import simplejson

from common.display import prep_stream_dict, prep_entry_list, prep_entry, prep_comment_list, DEFAULT_AVATARS

from common import api
from common import component
from common import exception
from common import decorator
from common import display
from common import google_contacts
from common import mail
from common import memcache
from common import oauth_util
from common import user
from common import util
from common import validate
from common import views as common_views


def join_join(request):
  if request.user:
    raise exception.AlreadyLoggedInException()

  redirect_to = request.REQUEST.get('redirect_to', '/')

  # get the submitted vars
  nick = request.REQUEST.get('nick', '');
  first_name = request.REQUEST.get('first_name', '');
  last_name = request.REQUEST.get('last_name', '');
  email = request.REQUEST.get('email', '');
  password = request.REQUEST.get('password', '');
  confirm = request.REQUEST.get('confirm', '');
  hide = request.REQUEST.get('hide', '');

  if request.POST:
    try:
      # TODO validate
      params = util.query_dict_to_keywords(request.POST)

      if hide:
        params['privacy'] = 2
 
      validate.email(email)
      if not mail.is_allowed_to_send_email_to(email):
        raise exception.ValidationError("Cannot send email to that address")

      # TODO start transaction
      if api.actor_lookup_email(api.ROOT, email):
        raise exception.ValidationError(
            'That email address is already associated with a member.')
    
      actor_ref = api.user_create(api.ROOT, **params)
      actor_ref.access_level = "delete"

      api.post(actor_ref, 
               nick=actor_ref.nick, 
               message='Joined %s!' % (settings.SITE_NAME),
               icon='jaiku-new-user')

      # send off email confirmation
      api.activation_request_email(actor_ref, actor_ref.nick, email)
      
      # TODO end transaction
  
      welcome_url = util.qsa('/welcome', {'redirect_to': redirect_to})

      # NOTE: does not provide a flash message
      response = http.HttpResponseRedirect(welcome_url)
      user.set_user_cookie(response, actor_ref)
      return response
    except:
      exception.handle_exception(request)

  # for legal section
  legal_component = component.include('legal', 'dummy_legal')
  legal_html = legal_component.embed_join()

  # for sidebar
  sidebar_green_top = True

  area = "join"
  c = template.RequestContext(request, locals())

  t = loader.get_template('join/templates/join.html')
  return http.HttpResponse(t.render(c))

@decorator.login_required
def join_welcome(request):
  redirect_to = request.REQUEST.get('redirect_to', '/')
  next = '/welcome/1'

  view = request.user
  page = 'start'

  area = 'welcome'
  c = template.RequestContext(request, locals())
  
  t = loader.get_template('join/templates/welcome_%s.html' % page)
  return http.HttpResponse(t.render(c))

@decorator.login_required
def join_welcome_photo(request):
  next = '/welcome/2'
  redirect_to = request.REQUEST.get('redirect_to', '/')

  # Welcome pages have a 'Continue' button that should always lead
  # to the next page. 
  success = '/welcome/1'
  if 'continue' in request.POST:
    success = next

  rv = common_views.common_photo_upload(
    request, 
    util.qsa(success, {'redirect_to': redirect_to})
    )
  if rv:
    return rv

  # If avatar wasn't changed, just go to next page, if 'Continue' was clicked.
  if 'continue' in request.POST:
    return http.HttpResponseRedirect(util.qsa(next, {'redirect_to': redirect_to}))
  
  avatars = display.DEFAULT_AVATARS

  view = request.user
  page = 'photo'
  area = 'welcome'
  c = template.RequestContext(request, locals())

  t = loader.get_template('join/templates/welcome_%s.html' % page)
  return http.HttpResponse(t.render(c))

@decorator.login_required
def join_welcome_mobile(request):
  redirect_to = request.REQUEST.get('redirect_to', '/')
  next = '/welcome/3'
  

  try:
    if not settings.SMS_ENABLED:
      raise exception.FeatureDisabledError('Mobile activation is currently disabled')
    
  except:
    exception.handle_exception(request)
  
  mobile = api.mobile_get_actor(request.user, request.user.nick)

  # set the progress
  welcome_photo = True

  view = request.user
  page = 'mobile'

  area = 'welcome'
  c = template.RequestContext(request, locals())
  
  t = loader.get_template('join/templates/welcome_%s.html' % page)
  return http.HttpResponse(t.render(c))

@decorator.login_required
def join_welcome_contacts(request):

  """
  if we have an access token for this user attempt to fetch the contacts
  else if we have a request token attempt to get an access token
  if we have neither
    if we are trying to authorize, grab a request token and redirect to authorize page
    else
      show the page
  """
  redirect_to = request.REQUEST.get('redirect_to', '/')
  next = '/welcome/done'


  # these are for the find more contacts bits
  start_index = int(request.REQUEST.get('index', 1))
  max = 100
  token = request.REQUEST.get('token')
  contacts_more = int(request.REQUEST.get('contacts_more', 0))
  # this won't be seen unless contacts_more is positive,
  # so no worries about the possible negative value
  contacts_so_far = contacts_more - 1


  try:
    if not settings.GOOGLE_CONTACTS_IMPORT_ENABLED:
      raise exception.FeatureDisabledError('Google Contacts import is currently disabled')
    
    if 'lookup_remote_contacts' in request.POST:
      validate.nonce(request, 'lookup_remote_contacts')

      next_url = util.qsa(util.here(request), 
                          {'redirect_to': redirect_to,
                           'upgrade_auth_token': '',
                           '_nonce': util.create_nonce(request.user, 
                                                       'upgrade_auth_token'),
                           }
                          )
      auth_url = google_contacts.auth_sub_url(next_url)
      return http.HttpResponseRedirect(auth_url)
    elif 'actor_add_contacts' in request.POST:
      validate.nonce(request, 'actor_add_contacts')

  
      targets = request.POST.getlist('targets')
      owner = request.POST.get('owner', '')

      rv = api.actor_add_contacts(request.user, owner, targets)

      next_url = util.qsa(util.here(request),
                          {'redirect_to': redirect_to,
                           'contacts_more': contacts_more,
                           'index': start_index,
                           'token': token,
                           }
                          )

      return util.RedirectFlash(next_url, 'Contacts added.')
  
    elif 'upgrade_auth_token' in request.GET:
      validate.nonce(request, 'upgrade_auth_token')
      
      auth_token = google_contacts.auth_sub_token_from_request(request)
      session_token = google_contacts.upgrade_to_session_token(auth_token)
      
      next_url = util.qsa(util.here(request),
                          {'redirect_to': redirect_to,
                           'fetch_contacts': '',
                           'token': session_token.get_token_string(),
                           '_nonce': util.create_nonce(request.user, 
                                                       'fetch_contacts'),
                           }
                          )
      
      return http.HttpResponseRedirect(next_url)

    elif 'fetch_contacts' in request.REQUEST:
      validate.nonce(request, 'fetch_contacts')
      
      # start_index and max are gathered above
      session_token = google_contacts.auth_sub_token_from_request(request)
      
      # check for the "My Contacts" group, otherwise, fetch it
      my_contacts = memcache.client.get('%s/my_contacts' % token)
      if not my_contacts:
        my_contacts = google_contacts.get_system_group(session_token, 
                                                       'Contacts')
        memcache.client.set('%s/my_contacts' % token, my_contacts)


      rv, more = google_contacts.get_contacts_emails(session_token,
                                                     group=my_contacts,
                                                     index=start_index,
                                                     max=max)

      contacts = []

      for name, email in rv:
        logging.info('looking up "%s" %s', name, email)
        contacts.append(api.actor_lookup_email(request.user, email))

      contacts = [x for x in contacts if x]

      # for the template
      contacts_found = True
      contacts_more = more
      contacts_so_far = contacts_more - 1
      token = session_token.get_token_string()
      contacts_emails = rv

      # if no contacts were found and more are available, try some more
      if not contacts and contacts_more:
        next_url = util.qsa(util.here(request),
                            {'fetch_contacts': '',
                             'contacts_more': contacts_more,
                             'index': contacts_more,
                             'token': token,
                             '_nonce': util.create_nonce(request.user,
                                                         'fetch_contacts'),
                             'redirect_to': redirect_to,
                             }
                            )
        # TODO(termie): this can take a really long time, probably not really
        #               viable until we can do it with javascript
        #return util.MetaRefresh(next_url, message='Still working...', second=1)
        #return http.HttpResponseRedirect(next_url)

  except:
    exception.handle_exception(request)


  # set the progress
  welcome_photo = True
  welcome_mobile = True

  view = request.user
  page = 'contacts'

  area = 'welcome'
  c = template.RequestContext(request, locals())
  
  t = loader.get_template('join/templates/welcome_%s.html' % page)
  return http.HttpResponse(t.render(c))

def join_welcome_done(request):
  redirect_to = request.REQUEST.get('redirect_to', '/')

  # set the progress
  welcome_photo = True
  welcome_mobile = True
  welcome_contacts = True

  view = request.user
  page = 'done'

  area = 'welcome'
  c = template.RequestContext(request, locals())
  
  t = loader.get_template('join/templates/welcome_%s.html' % page)
  return http.HttpResponse(t.render(c))
