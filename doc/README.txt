JaikuEngine
===========


Getting the code
----------------

You can download the latest released version of JaikuEngine from the 
Google Code project at: http://code.google.com/p/jaikuengine

Use this command to anonymously check out the latest project source code:
# Non-members may check out a read-only working copy anonymously over HTTP.
svn checkout http://jaikuengine.googlecode.com/svn/trunk/ jaikuengine-read-only

If you plan to make changes, use this command to check out the code as yourself using HTTPS:
# Project members authenticate over HTTPS to allow committing changes.
svn checkout https://jaikuengine.googlecode.com/svn/trunk/ jaikuengine --username adewale

When prompted, enter your generated googlecode.com password.


Dependencies
------------
  
  * Python 2.4 or 2.5
  * docutils: http://docutils.sourceforge.net/
  * Everything else should be included in the checkout :)

Quickstart
----------

To get a development version running:

   1. Check out the repository (it's somewhat large due to image binaries):
  
      ``svn checkout http://jaikuengine.googlecode.com/svn/trunk/ jaikuengine``
    
   2. Run the server with some test data pre-loaded:

      ``python manage.py testserver common/fixtures/*.json``
   
   3. Browse to localhost:8080 and log in with popular/password


To deploy to Google App Engine

   1. Create an application, you can do this on appspot.com

   2. Check out the repository (it's somewhat large due to image binaries):
  
      ``svn checkout http://jaikuengine.googlecode.com/svn/trunk/ jaikuengine``

   3. Edit your ``app.yaml`` and change your application to use the
      application identifier you just created

   4. Set up some basic config stuff using the helper tool:

      ``python manage.py config --write-to-file``

   5. Deploy

      ``python manage.py update``

   6. Go to your app and create the initial data by going to the url
      (you'll need to be logged in to appspot.com as an admin of your
      application):

      ``http://yourapp.appspot.com/install``

Getting Running
---------------

JaikuEngine uses the Django framework as well as most of its development 
process, so most actions go through manage.py.

To run the development server::

  python manage.py runserver 8080

But most of the time you'll be wanting to load some basic test data, this can
be done with the testserver command (and specifying the data to load)::

  ``python manage.py testserver common/fixtures/*.json``

Both of these will start a server running at http://localhost:8080.  

If you would like to start a server that binds to all interfaces, use::

  python manage.py runserver 0.0.0.0:8080


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
