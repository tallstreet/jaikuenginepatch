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

from django.conf import settings

from cleanliness import encoding

from common import exception
from common import throttle
from common import component
from common.protocol import base

class SmsMessage(object):
  sender = None
  target = None
  message = None

  def __init__(self, sender, target, message):
    self.sender = sender
    self.target = target
    self.message = message

  @classmethod
  def from_request(cls, request):
    sms_service = component.best['sms_service']
    return sms_service.from_request(cls, request)

class SmsConnection(base.Connection):
  def filter_targets(self, to_list, message):
    if settings.SMS_MT_WHITELIST:
      to_list = [x for x in to_list if settings.SMS_MT_WHITELIST.match(x)]

    if settings.SMS_MT_BLACKLIST:
      to_list = [x for x in to_list if not settings.SMS_MT_BLACKLIST.match(x)]

    if settings.SMS_TEST_ONLY:
      to_list = [x for x in to_list if x in settings.SMS_TEST_NUMBERS]

    if len(to_list) == 0:
      raise exception.ServiceError('All requested SMS targets are blocked')
    
    return to_list


  def send_message(self, to_list, message):
    if not to_list:
      return

    try:
      to_list = self.filter_targets(to_list, message)
    except exception.Error:
      exception.log_warning()
      return

    # global monthly sms limit
    # TODO(termie): this means that no messages will be sent if any
    #               will go over the limit, is this really the behavior
    #               we want?
    for i in range(0, len(to_list)):
      throttle.throttle(None, 
                        'sms_global_send', 
                        month=settings.THROTTLE_SMS_GLOBAL_MONTH)
  
    message = encoding.smart_str(message)
    sms_service = component.best['sms_service']
    sms_service.send_message(to_list, message)

