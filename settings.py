# Copyright 2009 Google Inc.

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

import re
import os
import os.path

###
# Django related settings
###

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS


# This stuff is always going to be the same for an App Engine instance
DATABASE_ENGINE = 'appengine'  # 'appengine' is the only supported engine
DATABASE_NAME = ''             # Not used with appengine
DATABASE_USER = ''             # Not used with appengine
DATABASE_PASSWORD = ''         # Not used with appengine
DATABASE_HOST = ''             # Not used with appengine
DATABASE_PORT = ''             # Not used with appengine

# The appengine_django code doesn't care about the address of memcached
# because it is a built in API for App Engine
CACHE_BACKEND = 'memcached://'

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'UTC'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'I AM SO SECRET'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
    # 'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'middleware.domain.DomainMiddleware',
    'middleware.auth.AuthenticationMiddleware',
    'middleware.exception.ExceptionMiddleware',
    'middleware.cache.CacheMiddleware',
    'middleware.strip_whitespace.WhitespaceMiddleware',
    'middleware.profile.ProfileMiddleware',
)

ROOT_URLCONF = 'urls'

# Where the templates live, you probably don't want to change this unless you
# know what you're doing
TEMPLATE_DIRS = (
    os.path.dirname(__file__),
)


TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.debug',
    'django.core.context_processors.request',
    'common.context_processors.settings',
    'common.context_processors.flash',
    'common.context_processors.components',
)

# Only apps under INSTALLED_APPS will be automatically tested via 
# `python manage.py test` and the profiling code takes this list into
# account while filtering calls
INSTALLED_APPS = (
     'appengine_django',
     'common',
     'actor',
     'api',
     'channel',
     'explore',
     'join',
     'flat',
     'login',
     'front',
     'invite',
     'confirm',
     'components',
)

# We override the default test runner so that we can be Totally Awesome
TEST_RUNNER = 'common.test.runner.run_tests'


####
#
# Below this is custom for Jaiku Engine (not related to Django)
#
####


# This is a dynamic setting so that we can check whether we have been run
# locally, it is used mainly for making special testing-only tweaks. Ideally
# we wouldn't need this, but the alternatives so far have been tricky.
MANAGE_PY = os.path.exists('manage.py')

# This is the name of the site that will be used whenever it refers to itself
SITE_NAME = 'My-ku'
SUPPORT_CHANNEL = 'support'

# This is the colloquial name for an entry, mostly used for branding purposes
POST_NAME = 'Post'

# This is the name of the root user of the site
ROOT_NICK = 'root@example.com'


# This is the domain where this is installed on App Engine. It will be
# necessary to know this if you plan on enabling SSL for login and join.
GAE_DOMAIN = 'example.appspot.com'

# Enabling this means we expect to be spending most of our time on a 
# Hosted domain
HOSTED_DOMAIN_ENABLED = True

# This is the domain you intend to serve your site from, when using hosted
# domains. If SSL is enabled for login and join those requests will still 
# go to the GAE_DOMAIN above.
HOSTED_DOMAIN = 'example.com'

# App Engine requires you to serve with a subdomain
DEFAULT_HOSTED_SUBDOMAIN = 'www'

NS_DOMAIN = 'example.com'

# DOMAIN will be used wherever a url to this site needs to be created
# NS_DOMAIN will be used as the domain part of actor identifiers. 
# Note that changing this once you have deployed the site will likely result 
# in catastrophic failure.
if HOSTED_DOMAIN_ENABLED:
  DOMAIN = '%s.%s' % (DEFAULT_HOSTED_SUBDOMAIN, HOSTED_DOMAIN)
else:
  DOMAIN = GAE_DOMAIN




# Subdomains aren't supported all that nicely by App Engine yet, so you
# probably won't be able to enable WILDCARD_SUBDOMAINS below, but you can 
# still set up your app to use some of the static subdomains below.
# Subdomains are ignored unless HOSTED_DOMAIN_ENABLED is True.
SUBDOMAINS_ENABLED = False
WILDCARD_USER_SUBDOMAINS_ENABLED = False

# These are defined as { subdomain : url_conf, ...}
INSTALLED_SUBDOMAINS = {
    'api': 'api.urls',  # api-only urlconf
    'm': 'urls',          # default urlconf, but allow the subdomain
    }

# Enable SSL support for login and join, if using HOSTED_DOMAIN_ENABLED
# this means you will be redirecting through https://GAE_DOMAIN/login
# and https://GAE_DOMAIN/join for those respective actions.
SSL_LOGIN_ENABLED = False

#
# Appearance / Theme
#

# The default theme to use
DEFAULT_THEME = 'trotz'



#
# Cookie
#

# Cookie settings, pretty self explanatory, you shouldn't need to touch these.
USER_COOKIE = 'user'
PASSWORD_COOKIE = 'password'
COOKIE_DOMAIN = '.%s' % DOMAIN
COOKIE_PATH = '/'

#
# Blog
#

# Do you want /blog to redirect to your blog?
BLOG_ENABLED = False

# Where is your blog?
BLOG_URL = 'http://example.com'
BLOG_FEED_URL = 'http://example.com/feeds'


#
# API
#

# Setting this to True will make the public API accept all requests as being 
# from ROOT with no regard to actual authentication.
# Never this set to True on a production site.
API_DISABLE_VERIFICATION = False

# These next three determine which OAuth Signature Methods to allow.
API_ALLOW_RSA_SHA1 = True
API_ALLOW_HMAC_SHA1 = True
API_ALLOW_PLAINTEXT = False

# These three determine whether the ROOT use should be allowed to use these
# methods, if any at all. Setting all of these to False will disable the 
# ROOT user from accessing the public API
API_ALLOW_ROOT_RSA_SHA1 = True
API_ALLOW_ROOT_HMAC_SHA1 = True
API_ALLOW_ROOT_PLAINTEXT = False

# OAuth consumer key and secret values
ROOT_TOKEN_KEY = 'ROOT_TOKEN_KEY'
ROOT_TOKEN_SECRET = 'ROOT_TOKEN_SECRET'
ROOT_CONSUMER_KEY = 'ROOT_CONSUMER_KEY'
ROOT_CONSUMER_SECRET = 'ROOT_CONSUMER_SECRET'

# Allow support for legacy API authentication
API_ALLOW_LEGACY_AUTH = False
LEGACY_SECRET_KEY = 'I AM ALSO SECRET'

#
# SMS
#

# Enabling SMS will require a bit more than just making this True, please
# read the docs at http://code.google.com/p/jaikuengine/wiki/sms_support
SMS_ENABLED = False

# Most SMS vendors will provide a service that will post messages to a url
# on your site when an SMS has been received on their end, this setting allows
# you to add a secret value to that must exist in that url to prevent 
# malicious use.
SMS_VENDOR_SECRET = 'SMS_VENDOR'

# Valid numbers on which you expect to receive SMS
SMS_TARGET = '00000'

# Whitelist regular expression for allowable mobile-terminated targets
SMS_MT_WHITELIST = re.compile('\+\d+')

# Blacklist regular expression for blocked mobile-terminated targets
SMS_MT_BLACKLIST = None

# Turn on test mode for SMS
SMS_TEST_ONLY = False

# Numbers to use when testing live SMS so you don't spam all your users
SMS_TEST_NUMBERS = []


#
# XMPP / IM
#

# Enabling IM will require a bit more than just making this True, please
# read the docs at http://code.google.com/p/jaikuengine/wiki/im_support
IM_ENABLED = False

# This is the id (JID) of the IM bot that you will use to communicate with
# users of the IM interface
IM_BOT = 'root@example.com'

# Turn on test mode for IM
IM_TEST_ONLY = False

# JIDs to allow when testing live XMPP so you don't spam all your users
IM_TEST_JIDS = []

#
# Task Queue
#

# Enabling the queue will allow you to process posts with larger numbers
# of followers but will require you to set up a cron job that will continuously
# ping a special url to make sure the queue gets processed
QUEUE_ENABLED = True

# The secret to use for your cron job that processes your queue
QUEUE_VENDOR_SECRET = 'SECRET'


#
# Throttling Config
#

# This will control the max number of SMS to send over a 30-day period
THROTTLE_SMS_GLOBAL_MONTH = 10000




# Settings for remote services
IMAGE_UPLOAD_ENABLED = False
IMAGE_UPLOAD_URL = 'upload.example.com'

MAX_AVATAR_UPLOAD_KB = 300

# Settings for Google Contacts import
GOOGLE_CONTACTS_IMPORT_ENABLED = False



FEEDS_ENABLED = False
MARK_AS_SPAM_ENABLED = True
PRESS_ENABLED = False
BADGES_ENABLED = True
HIDE_COMMENTS_ENABLED = True
MULTIADMIN_ENABLED = False
PRIVATE_CHANNELS_ENABLED = False
MARKDOWN_ENABLED = False


PROFILE_DB = False

# Limit of avatar photo size in kilobytes
MAX_AVATAR_PHOTO_KB = 200

MAX_ACTIVATIONS = 10

# Email Test mode
EMAIL_TEST_ONLY = False

# Allowed email addresses for testing
EMAIL_TEST_ADDRESSES = []

# Email limiting, if this is set it will restrict users to those with 
# email addresses in this domain
EMAIL_LIMIT_DOMAIN = None

# Things to measure to taste
MAX_COMMENT_LENGTH = 2000


# Gdata Stuff
GDATA_CONSUMER_KEY = ''
GDATA_CONSUMER_SECRET = ''

def default_email_sender():
  try:
    return os.environ['DJANGO_DEFAULT_FROM_EMAIL']
  except KeyError:
    return 'termie@google.com'

DEFAULT_FROM_EMAIL = default_email_sender()
DEFAULT_UNITTEST_TO_EMAIL = 'unittests@example.com'

PROFILING_DATA_PATH = 'profiling/prof_db.csv'


# Set up the settings for the dev server if we are running it
if MANAGE_PY:
  try:
    from dev_settings import *
  except ImportError:
    pass

# Allow local overrides, useful for testing during development
try:
  from local_settings import *
except ImportError:
  pass
