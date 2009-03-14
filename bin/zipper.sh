#!/bin/sh
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

TOZIP=$1
TOZIP=`echo "$TOZIP" | sed "s/.zip//"`


rm -f "$TOZIP.zip"
zip $TOZIP `find $TOZIP -name .svn -prune -o -type f ! -name '*.pyc' ! -name '*.[pm]o' -print | grep -v -E 'contrib/(admin|gis|comments|localflavor|databrowse)'`
