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

UNAME=`uname`
if [ $UNAME == 'Darwin' ]
then
  OUTTYPE='quartz'
else
  OUTTYPE='cairo1'
fi

R -e 'INFILE <- "profiling/prof_db.csv"' \
  -e 'OUTFILE <- "profiling/prof_db.png"' \
  -e "OUTTYPE <- '$OUTTYPE'" \
  -e 'source("profiling/prof.r")'
