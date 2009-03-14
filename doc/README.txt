JaikuEngine
===========


Getting the code
----------------

You can download the latest released version of JaikuEngine from the 
Google Code project at: http://code.google.com/p/jaikuengine

You can check out the latest version of JaikuEngine directly from
the SVN repository with the following command::

  svn co https://jaikuengine.googlecode.com/svn/trunk/ jaikuengine


Dependencies
------------
  
  * Python 2.4 or 2.5
  * docutils: http://docutils.sourceforge.net/
  * Everything else should be included in the checkout :)

Quickstart
----------

   1. Check out the repository (it's somewhat large due to image binaries):
  
      ``svn checkout https://jaikuengine.googlecode.com/svn/trunk/ jaikuengine``

   2. Copy local_settings.example.py to local_settings.py 
   
   2. Run the server with some test data pre-loaded:

      ``./bin/testserver.sh``
   
   3. Browse to localhost:8000 and log in with popular/password

Getting Running
---------------

JaikuEngine uses the Django framework as well as most of its development 
process, so most actions go through manage.py.

To run the development server::

  python manage.py runserver

But most of the time you'll be wanting to load some basic test data, this can
be done with the testserver command (and specifying the data to load)::

  ./bin/testserver.sh

Both of these will start a server running at http://localhost:8000.  

If you would like to start a server that binds to all interfaces, use::

  python manage.py runserver 0.0.0.0:8000


Contributing to the project
---------------------------

We would be happy to consider any additions or bugfixes that you would like to
add to the helper. Please add them as a patch, in unified diff format to the
Issue Tracker at: http://code.google.com/p/jaikuengine/issues/list

Before we can accept your code you will need to have signed the Google
Contributer License. You can find this at:

http://code.google.com/legal/individual-cla-v1.0.html
or
http://code.google.com/legal/corporate-cla-v1.0.html

If you are an Individual contributor you will be able to electronically sign
and submit the form at the URL above. Please ensure that you use the same email
address to submit your patch as you used to sign the CLA.


Reporting Bugs and Requesting Features
--------------------------------------

If you find a bug or would like to request a feature you may do so at the
Google Code issue tracker for this project:

http://code.google.com/p/jaikuengine/issues/entry
