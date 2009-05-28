"""an sms service that doesn't do anything"""
import logging

from common.protocol import sms

def send_message(to_list, message):
  logging.info("SMS_SERVICE: send_message(%s, %s)", to_list, message)


def from_request(cls, request):
  params = {'sender': request.REQUEST.get('sender'),
            'target': request.REQUEST.get('target'),
            'message': request.REQUEST.get('message'),
            }
  return cls(**params)
