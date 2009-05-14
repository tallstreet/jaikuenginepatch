#!/bin/sh
PATCH_ID=$1
PATCH_NAME=$2
[ -z $PATCH_NAME ] && PATCH_NAME="raw_patch.diff"

# Download the page and find the diff url

RAW_PATCH=`curl -s http://rietku.appspot.com/$1/show \
  | grep -B 1 'Download raw' \
  | head -n 1 \
  | cut -d '"' -f 2`

echo $RAW_PATCH
curl -s -o $PATCH_NAME http://rietku.appspot.com$RAW_PATCH
