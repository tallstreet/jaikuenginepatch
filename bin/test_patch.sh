#!/bin/sh

# Note: this script depends on git and expects you to have set up your repo
#       with a command something like:
# git svn clone https://jaikuengine.googlecode.com/svn/trunk/ jaikuengine-git
# cd jaikuengine-git
# cp -r ../jaikuengine-clean/vendor/* vendor
# cp -r ../jaikuengine-clean/appengine_django ./
# cp -r ../jaikuengine-clean/.google_appengine ./
# cat > .gitignore
#   vendor/*
#   *.swp
#   *.pyc
#   .*
#   appengine_django/*
#   *.zip
#   raw.diff

PATCH_ID=$1
if [ -z $PATCH_ID ]
then
  echo "Usage: ./bin/test_patch.sh <patch_id>"
  exit 1
fi
PATCH_NAME=raw.diff

# Step 1: Make a new branch based on master [master]
git checkout -b "patch_$1" master

# Step 2: Grab the patch
./bin/download_diff.sh $1 $PATCH_NAME

# Step 3: Apply!
patch -p0 -U < $PATCH_NAME
