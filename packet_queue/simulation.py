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

import random
import time
from twisted.internet import reactor


class PipePair(object):
  """Holds two Pipe instances sharing a parameter dictionary and event log."""
  def __init__(self, params, event_log):
    self.event_log = event_log
    self.up = Pipe('up', params, event_log)
    self.down = Pipe('down', params, event_log)


class Pipe(object):
  """Takes packets, represented by a callback and a size in bytes, and possibly
  invokes the callback later.

  Limits bandwidth by holding packets in a "buffer", and rejects packets when
  the buffer is full.

  Applies constant random packet loss prior to packets joining the buffer, and
  constant delay after they are released.
  """

  PARAMS = {
      'bandwidth': -1,  # bytes per second, defaults to infinity
      'buffer': -1,  # max bytes allowed, defaults to infinity
      'delay': 0.0,
      'loss': 0.0,
  }

  def __init__(self, name, params, event_log):
    self.name = name
    self.params = params
    self.events = event_log
    self.size = 0

  def attempt(self, deliver_callback, drop_callback, size):
    """Possibly invoke a callback representing a packet.

    The callback may be invoked later using the Twisted reactor, simulating
    network latency, or it may be ignored entirely, simulating packet loss.
    """
    attempt_time = time.time()

    def deliver():
      delivery_time = time.time()
      latency = delivery_time - attempt_time
      self.events.add(delivery_time, self.name, 'deliver', size)
      self.events.add(delivery_time, self.name, 'latency', latency)
      deliver_callback()

    if self.params['buffer'] > 0 and self.size + size > self.params['buffer']:
      self.events.add(attempt_time, self.name, 'drop', size)
      drop_callback()
      return

    if random.random() < self.params['loss']:
      self.events.add(attempt_time, self.name, 'drop', size)
      drop_callback()
      return

    self.size += size
    self.events.add(attempt_time, self.name, 'buffer', self.size)

    def release_buffer():
      release_time = time.time()
      self.size -= size
      self.events.add(release_time, self.name, 'buffer', self.size)

    # Delay has two components: throttled (proportional to size) and constant.
    #
    # Throttle delay is calculated by estimating the time it will take all of
    # the enqueued packets to be released, including the current one. Release
    # the current packet (subtract its size) after this period of time.
    #
    # After the packet is released, there is an additional period of constant
    # delay, so schedule a second event to finally call the packet's callback.
    throttle_delay = 0
    if self.params['bandwidth'] > 0:
      throttle_delay = float(self.size) / self.params['bandwidth']
    constant_delay = self.params['delay']

    reactor.callLater(throttle_delay, release_buffer)
    reactor.callLater(throttle_delay + constant_delay, deliver)
