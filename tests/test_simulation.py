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

import bisect
import unittest
from packet_queue import simulation


class FakeReactor(object):
  """Substitute for the Twisted reactor module.

  Allows tests to explicitly advance time to execute scheduled callbacks.
  """
  def __init__(self):
    self.queue = []
    self.time = 0.0

  def advance_time(self, seconds):
    self.time += seconds
    while self.queue:
      time, callback = self.queue[0]
      if time <= self.time:
        self.queue.pop(0)
        callback()
      else:
        break

  def callLater(self, delay, callback):
    bisect.insort(self.queue, (self.time + delay, callback))


class FakeReactorTest(unittest.TestCase):
  def setUp(self):
    self.reactor = FakeReactor()
    self.called = []

  def Add(self, obj):
    def callback():
      self.called.append(obj)
    return callback

  def test_callbacks(self):
    self.reactor.callLater(0.0, self.Add(1))
    self.reactor.callLater(0.5, self.Add(2))
    self.reactor.callLater(1.0, self.Add(3))
    self.assertItemsEqual(self.called, [])

    self.reactor.advance_time(0.0)
    self.assertItemsEqual(self.called, [1])

    self.reactor.advance_time(0.5)
    self.assertItemsEqual(self.called, [1, 2])
    self.reactor.callLater(0.5, self.Add(4))

    self.reactor.advance_time(0.5)
    self.assertItemsEqual(self.called, [1, 2, 3, 4])


class PipeTest(unittest.TestCase):
  def setUp(self):
    self.pipe = simulation.Pipe(dict(simulation.Pipe.PARAMS))
    self.received = []
    self.reactor = FakeReactor()
    simulation.reactor = self.reactor

  def configure(self, **kwargs):
    self.pipe.params.update(kwargs)

  def send(self, obj, size=0):
    def callback():
      self.received.append(obj)
    self.pipe.attempt(callback, size)

  def wait(self, seconds):
    self.reactor.advance_time(seconds)

  def expect(self, received):
    self.assertItemsEqual(self.received, received)

  def test_constant_delay(self):
    self.configure(delay=0.5)

    self.send(1)
    self.send(2)
    self.expect([])

    self.wait(0.5)
    self.send(3)
    self.expect([1, 2])

    self.wait(0.5)
    self.expect([1, 2, 3])

  def test_throttle(self):
    self.configure(bandwidth=4096)

    self.send(1, 1024)
    self.send(2, 2048)
    self.send(3, 0)
    self.expect([])

    self.wait(0.25)
    self.expect([1])

    self.wait(0.5)
    self.expect([1, 2, 3])

  def test_throttle_plus_constant_delay(self):
    self.configure(bandwidth=4096, delay=2.0)

    self.send(1, 2048)
    self.send(2, 2048)
    self.assertEqual(self.pipe.size, 4096)

    self.wait(1.0)
    self.expect([])
    self.assertEqual(self.pipe.size, 0)

    self.wait(2.0)
    self.expect([1, 2])

  def test_buffer_full(self):
    self.configure(bandwidth=1024, buffer=2048)

    self.send(1, 1024)
    self.send(2, 1024)
    self.send(3, 1024)
    self.assertEqual(self.pipe.size, 2048)

    self.wait(1.0)
    self.expect([1])
    self.assertEqual(self.pipe.size, 1024)
    self.send(4, 1024)

    self.wait(1.0)
    self.expect([1, 2])

    self.wait(1.0)
    self.expect([1, 2, 4])

  def test_drop_all(self):
    self.configure(delay=1.0, loss=1.0)

    self.send(1, 1024)
    self.wait(1.0)
    self.expect([])
    self.assertEqual(self.pipe.bytes_attempted, 1024)
    self.assertEqual(self.pipe.bytes_delivered, 0)

  def testMeteringAllDelivered(self):
    self.configure(delay=2.0)

    self.send(1, 1024)
    self.wait(1.0)
    self.assertEqual(self.pipe.bytes_attempted, 1024)
    self.assertEqual(self.pipe.bytes_delivered, 0)

    self.send(1, 1024)
    self.assertEqual(self.pipe.bytes_attempted, 2048)
    self.assertEqual(self.pipe.bytes_delivered, 0)

    self.wait(1.0)
    self.assertEqual(self.pipe.bytes_attempted, 2048)
    self.assertEqual(self.pipe.bytes_delivered, 1024)

    self.wait(1.0)
    self.assertEqual(self.pipe.bytes_attempted, 2048)
    self.assertEqual(self.pipe.bytes_delivered, 2048)
