import logging
def send_message(to_jids, message, html_message=None):
  if html_message:
    logging.info('XMPP_SERVICE: send_message(%s, %s, html_message=%s)',
                 to_jids, message, html_message)
  else:
    logging.info('XMPP_SERVICE: send_message(%s, %s)', to_jids, message)

def from_request(cls, request):
  params = {'sender': request.POST.get('from'),
            'target': request.POST.get('to'),
            'message': request.POST.get('body')
            }
  return cls(**params)
