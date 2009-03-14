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

def prep_stream(stream, actors):
  stream.owner_ref = actors[stream.owner]
  return stream

def prep_entry(entry, streams, actors):
  """function to append the applicable referenced items to the entry"""
  entry.stream_ref = streams[entry.stream]
  entry.owner_ref = actors[entry.owner]
  entry.actor_ref = actors[entry.actor]
  return entry

def prep_entry_entry(entry, entries):
  return entry
  if entry.entry:
    entry.entry_ref = entries[entry.entry]
  return entry

def prep_stream_dict(stream_dict, actors):
  streams = dict([(k, prep_stream(v, actors)) 
                 for (k, v) in stream_dict.items()])
  return streams

def prep_entry_list(entry_list, streams, actors):
  entries = [prep_entry(e, streams, actors) for e in entry_list]
  entries_by_keyname = dict([(e.key().name(), e) for e in entries])
  entries = [prep_entry_entry(e, entries_by_keyname) for e in entries]
  return entries


def prep_comment(comment, actors):
  """function to append the applicable referenced items to the comment"""
  comment.owner_ref = actors[comment.owner]
  comment.actor_ref = actors[comment.actor]
  return comment

def prep_comment_list(comment_list, actors):
  comments = [prep_comment(e, actors) for e in comment_list]
  return comments

DEFAULT_AVATARS = [{'name': 'animal_%s' % i, 'path': 'default/animal_%s' % i}
                   for i in xrange(1,17)]

ICONS = {
  '101': ('feed-blog', 'blog', ''),
  '102': ('feed-bookmark', 'bookmark', ''),
  '103': ('feed-bookwish', 'book wish', ''),
  '104': ('feed-event', 'event', ''),
  '105': ('feed-music', 'music', ''),
  '106': ('feed-photo', 'photo', ''),
  '107': ('feed-places', 'places', ''),
  '108': ('feed-atom', 'atom', ''),
  '109': ('feed-video', 'video', ''),
  '200': ('jaiku-presence', 'presence', ''),
  '201': ('jaiku-comment', 'comment', ''),
  '202': ('jaiku-message', 'message', ''),
  '203': ('jaiku-new-user', 'new user', ''),
  '204': ('jaiku-sms', 'sms', ''),
  '205': ('jaiku-contact-added', 'contact added', ''),
  '300': ('web-speechbubble', 'speech bubble', ''),
  '301': ('web-car', 'car', ''),
  '302': ('web-alarmclock', 'alarm clock', ''),
  '303': ('web-loudspeaker', 'loudspeaker', ''),
  '304': ('web-tram', 'tram', ''),
  '305': ('web-casette', 'casette', ''),
  '306': ('web-underware', 'underwear', ''),
  '307': ('web-rollerblade', 'rollerblade', ''),
  '308': ('web-uzi', 'uzi', ''),
  '309': ('web-scoop', 'scoop', ''),
  '310': ('web-bomb', 'bomb', ''),
  '311': ('web-bra', 'bra', ''),
  '312': ('web-videotape', 'videotape', ''),
  '313': ('web-cigarettes', 'cigarettes', ''),
  '314': ('web-vinyl', 'vinyl', ''),
  '315': ('web-champaign', 'champaign', ''),
  '316': ('web-airplain', 'airport', ''),
  '317': ('web-bus', 'bus', ''),
  '318': ('web-grumpy', 'grumpy', ''),
  '319': ('web-coffee', 'coffee', ''),
  '320': ('web-camera', 'camera', ''),
  '321': ('web-basketball', 'basketball', ''),
  '322': ('web-beer', 'beer', ''),
  '323': ('web-binoculars', 'binoculars', ''),
  '324': ('web-boiler', 'boiler', ''),
  '325': ('web-walk', 'walk', ''),
  '326': ('web-wallclock', 'wallclock', ''),
  '327': ('web-trashcan', 'trashcan', ''),
  '328': ('web-tv', 'tv', ''),
  '329': ('web-computing', 'computer', ''),
  '330': ('web-videocamera', 'videocamera', ''),
  '331': ('web-game', 'game', ''),
  '332': ('web-cone', 'cone', ''),
  '333': ('web-driller', 'driller', ''),
  '334': ('web-popcorn', 'popcorn', ''),
  '335': ('web-playshirt', 'play', ''),
  '336': ('web-disc', 'disc', ''),
  '337': ('web-event', 'event', ''),
  '338': ('web-exclamationmark', 'exclamationmark', ''),
  '339': ('web-football', 'football', ''),
  '340': ('web-footballshoe', 'football shoe', ''),
  '341': ('web-eat', 'fork', ''),
  '342': ('web-gameboy', 'gameboy', ''),
  '343': ('web-grenade', 'grenade', ''),
  '344': ('web-hand', 'hand', ''),
  '345': ('web-hanger', 'hanger', ''),
  '346': ('web-hearingprotector', 'ear muffs', ''),
  '347': ('web-love', 'love', ''),
  '348': ('web-balloons', 'balloons', ''),
  '349': ('web-clock', 'clock', ''),
  '350': ('web-barrier', 'barrier', ''),
  '351': ('web-laptop', 'laptop', ''),
  '352': ('web-megaphone', 'megaphone', ''),
  '353': ('web-microwave', 'microwave', ''),
  '354': ('web-book', 'book', ''),
  '355': ('web-middlefinger', 'middle finger', ''),
  '356': ('web-notes', 'notes', ''),
  '357': ('web-question', 'question', ''),
  '358': ('web-rollator', 'rollator', ''),
  '359': ('web-shuttlecock', 'shuttlecock', ''),
  '360': ('web-salt', 'salt', ''),
  '361': ('web-scull', 'scull', ''),
  '362': ('web-sk8', 'sk8', ''),
  '363': ('web-sleep', 'leep', ''),
  '364': ('web-snorkeling', 'snorkeling', ''),
  '365': ('web-snowflake', 'snowflake', ''),
  '366': ('web-soda', 'soda', ''),
  '367': ('web-song', 'song', ''),
  '368': ('web-spraycan', 'spray', ''),
  '369': ('web-sticks', 'sticks', ''),
  '370': ('web-storm', 'storm', ''),
  '371': ('web-straitjacket', 'straitjacket', ''),
  '372': ('web-metro', 'metro', ''),
  '373': ('web-luggage', 'luggage', ''),
  '374': ('web-sun', 'sun', ''),
  '375': ('web-taxi', 'taxi', ''),
  '376': ('web-technics', 'technics', ''),
  '377': ('web-toaster', 'toaster', ''),
  '378': ('web-train', 'train', ''),
  '379': ('web-wheelchair', 'wheelchair', ''),
  '380': ('web-zippo', 'zippo', ''),
  '381': ('web-icecream', 'ice cream', ''),
  '382': ('web-movie', 'movie', ''),
  '383': ('web-makeup', 'makeup', ''),
  '384': ('web-bandaid', 'bandaid', ''),
  '385': ('web-wine', 'wine', ''),
  '386': ('web-clean', 'clean', ''),
  '387': ('web-blading', 'blading', ''),
  '388': ('web-bike', 'bike', ''),
  '389': ('web-pils', 'pils', ''),
  '390': ('web-picnic', 'picnic', ''),
  '391': ('web-lifejacket', 'lifejacket', ''),
  '392': ('web-home', 'home', ''),
  '393': ('web-happy', 'happy', ''),
  '394': ('web-toiletpaper', 'toiletpaper', ''),
  '395': ('web-theatre', 'theatre', ''),
  '396': ('web-shop', 'shop', ''),
  '397': ('web-search', 'search', ''),
  '398': ('web-cloudy', 'cloudy', ''),
  '399': ('web-hurry', 'Hurry', ''),
  '400': ('web-morning', 'Morning', ''),
  '401': ('web-car', 'Car', ''),
  '402': ('web-baby-boy', 'Itsaboy', ''),
  '403': ('web-baby-girl', 'Itsagirl', ''),
}

ICONS_BY_ID = dict([(v[0], v) for k, v in ICONS.iteritems()])

SELECTABLE_ICONS = dict([(k, v) for k, v in ICONS.iteritems()
                                if k > '300'])

del SELECTABLE_ICONS['340']
del SELECTABLE_ICONS['351']
del SELECTABLE_ICONS['401']
del SELECTABLE_ICONS['403']
