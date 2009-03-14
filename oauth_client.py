#!/usr/bin/env python
import httplib
import time
import oauth.oauth as oauth

SERVER = 'localhost'
PORT = 8080

BASE_URL = 'http://%s:%s' % (SERVER, PORT)

REQUEST_TOKEN_URL = BASE_URL + '/api/request_token'
ACCESS_TOKEN_URL = BASE_URL + '/api/access_token'
AUTHORIZATION_URL = BASE_URL + '/api/authorize'

CONSUMER_KEY = 'TESTDESKTOPCONSUMER'
CONSUMER_SECRET = 'secret'

try:
  from oauth import rsa as oauth_rsa
  USE_RSA=True
except ImportError:
  USE_RSA=False

# example client using httplib with headers
class SimpleOAuthClient(oauth.OAuthClient):
  def __init__(self, server, port, request_token_url, access_token_url,
         authorization_url):
    self.server = server
    self.port = port
    self.request_token_url = request_token_url
    self.access_token_url = access_token_url
    self.authorization_url = authorization_url
    self.connection = httplib.HTTPConnection("%s:%d" % (self.server, self.port))

  def fetch_request_token(self, oauth_request):
    # via headers
    # -> OAuthToken
    self.connection.request(oauth_request.http_method, self.request_token_url,
                            headers=oauth_request.to_header())
    print oauth_request.to_url()
    response = self.connection.getresponse()
    rv = response.read()
    print rv

    return oauth.OAuthToken.from_string(rv)

  def fetch_access_token(self, oauth_request):
    # via headers
    # -> OAuthToken
    self.connection.request(oauth_request.http_method, self.access_token_url,
                            headers=oauth_request.to_header())
    response = self.connection.getresponse()
    return oauth.OAuthToken.from_string(response.read())

  def authorize_token(self, oauth_request):
    # via url
    # -> typically just some okay response
    self.connection.request(oauth_request.http_method, oauth_request.to_url())
    response = self.connection.getresponse()
    return response.read()

  def access_resource(self, oauth_request):
    # via post body
    # -> some protected resources
    headers = {'Content-Type' :'application/x-www-form-urlencoded'}
    self.connection.request('POST', RESOURCE_URL,
                            body=oauth_request.to_postdata(), headers=headers)
    response = self.connection.getresponse()
    return response.read()

def main():
  import sys
  user_signature_method = (len(sys.argv) > 1
               and sys.argv[1].lower()
               or 'hmac-sha1')

  # setup
  client = SimpleOAuthClient(SERVER, PORT, REQUEST_TOKEN_URL, ACCESS_TOKEN_URL,
                             AUTHORIZATION_URL)
  consumer = oauth.OAuthConsumer(CONSUMER_KEY, CONSUMER_SECRET)

  signature_methods = {"plaintext": oauth.OAuthSignatureMethod_PLAINTEXT(),
             "hmac-sha1": oauth.OAuthSignatureMethod_HMAC_SHA1()
             }
  if USE_RSA:
    signature_methods['rsa-sha1'] = \
        oauth_rsa.TestOAuthSignatureMethod_RSA_SHA1()

  signature_method = signature_methods[user_signature_method]

  pause()

  # get request token
  print '* Obtain a request token ...'
  pause()
  oauth_request = oauth.OAuthRequest.from_consumer_and_token(
      consumer, http_url=client.request_token_url)
  oauth_request.sign_request(signature_method, consumer, None)
  print 'REQUEST (via headers)'
  print 'parameters: %s' % str(oauth_request.parameters)
  pause()
  token = client.fetch_request_token(oauth_request)
  print 'GOT'
  print 'key: %s' % str(token.key)
  print 'secret: %s' % str(token.secret)
  pause()

  print '* Authorize the request token ...'
  pause()
  auth_url = '%s?oauth_token=%s' % (AUTHORIZATION_URL, token.key)
  print auth_url
  rv = raw_input()
  pause()

  # get access token
  print '* Obtain an access token ...'
  pause()
  oauth_request = oauth.OAuthRequest.from_consumer_and_token(
      consumer, token=token, http_url=client.access_token_url)
  oauth_request.sign_request(signature_method, consumer, token)
  print 'REQUEST (via headers)'
  print 'parameters: %s' % str(oauth_request.parameters)
  pause()
  token = client.fetch_access_token(oauth_request)
  print 'GOT'
  print 'key: %s' % str(token.key)
  print 'secret: %s' % str(token.secret)
  pause()

  # access some protected resources
  print '* Access protected resources ...'
  pause()

  # resource specific params
  parameters = {
    'file': 'vacation.jpg',
    'size': 'original',
    'oauth_callback': CALLBACK_URL
  }
  oauth_request = oauth.OAuthRequest.from_consumer_and_token(
      consumer, token=token, http_method='POST', http_url=RESOURCE_URL,
      parameters=parameters)
  oauth_request.sign_request(signature_method, consumer, token)
  print 'REQUEST (via post body)'
  print 'parameters: %s' % str(oauth_request.parameters)
  pause()
  params = client.access_resource(oauth_request)
  print 'GOT'
  print 'non-oauth parameters: %s' % params
  pause()

def pause():
  print
  return
  time.sleep(1)

if __name__ == '__main__':
  try:
    main()
  except oauth.OAuthError, e:
    print e.message
    raise
  print 'Done.'

