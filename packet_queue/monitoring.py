# Copyright 2016 Google Inc. All Rights Reserved.
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


class EventLog(object):
  """Records network simulation events for reporting to the web UI.

  This implementation assumes a single client, and deletes events that have
  been sent.
  """

  max_size = 9000

  def __init__(self):
    self.next_id = 1
    self.events = []

  def add(self, time, pipe_name, event_type, value):
    event = {
      'id': self.next_id,
      'time': time,
      'pipe': pipe_name,
      'type': event_type,
      'value': value,
    }
    self.next_id += 1
    self.events.append(event)

    if len(self.events) > self.max_size:
      self.events = self.events[-self.max_size:]

  def get_pending(self):
    events = self.events
    self.events = []
    return events
