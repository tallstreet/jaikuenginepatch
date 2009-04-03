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

"""helper functions for image handling
"""

__author__ = 'mikie@google.com (Mika Raento)'

def _debug(s):
  #print s
  pass

def _read_2byte(img_data, pos):
  return (ord(img_data[pos]) << 8) + ord(img_data[pos + 1])

def _size_from_jpeg(img_data):
  """A very crude JPEG reader so that we can get the image size"""
  # JPEG format:
  # 0xff 0xd8 (Start of Image)
  # repeated
  #   block marker (0xff 0x??)
  #   length (?? ??) of block
  #   length - 2 bytes data
  #
  # the image data block has marker 0xff 0xc0
  # the image data format is:
  #   ?? ?? length
  #   1 byte precision
  #   ?? ?? height
  #   ?? ?? width
  pos = 0
  # SOI 0xff 0xd8
  if (ord(img_data[pos]) != 0xff or ord(img_data[pos + 1]) != 0xd8):
    _debug('SOI not found %u %u' % (ord(img_data[pos]), ord(img_data[pos + 1])))
    return None
  pos += 2
  # start of stream
  sos = False
  while not sos:
    # marker
    if (ord(img_data[pos]) != 0xff):
      _debug('marker not found at pos %d' % (pos))
      return None
    if (ord(img_data[pos + 1]) == 0xc0):
      sos = True
      pos += 2
    else:
      pos += 2
      len = _read_2byte(img_data, pos)
      _debug('len %d' % len)
      pos += len
  pos += 3
  _debug('h %x %x' % (ord(img_data[pos]), ord(img_data[pos+1])))
  height = _read_2byte(img_data, pos)
  pos += 2
  width = _read_2byte(img_data, pos)
  return (width, height)

def size_from_jpeg(img_data):
  """Get the dimensions of an image from the jpeg data.
  """
  # _size_from_jpeg may throw an exception if the data is malformed, we then
  # return None
  try:
    return _size_from_jpeg(img_data)
  except:
    return None
