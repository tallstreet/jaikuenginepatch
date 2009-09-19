import logging
def send_message(to_jids, message, html_message=None, atom_message=None, raw_xml=False):
  logging.info('XMPP_SERVICE: send_message(%s, %s, html_message=%s,'
               ' atom_message=%s, raw_xml=%s)',
               to_jids, message, html_message, atom_message, raw_xml)

def from_request(cls, request):
  params = {'sender': request.POST.get('from'),
            'target': request.POST.get('to'),
            'message': request.POST.get('body')
            }
  return cls(**params)
