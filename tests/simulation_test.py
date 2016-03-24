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

  def AdvanceTime(self, seconds):
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

  def testCallbacks(self):
    self.reactor.callLater(0.0, self.Add(1))
    self.reactor.callLater(0.5, self.Add(2))
    self.reactor.callLater(1.0, self.Add(3))
    self.assertItemsEqual(self.called, [])

    self.reactor.AdvanceTime(0.0)
    self.assertItemsEqual(self.called, [1])

    self.reactor.AdvanceTime(0.5)
    self.assertItemsEqual(self.called, [1, 2])
    self.reactor.callLater(0.5, self.Add(4))

    self.reactor.AdvanceTime(0.5)
    self.assertItemsEqual(self.called, [1, 2, 3, 4])


class PipeTest(unittest.TestCase):
  def setUp(self):
    self.pipe = simulation.Pipe(dict(simulation.Pipe.PARAMS))
    self.received = []
    self.reactor = FakeReactor()
    simulation.reactor = self.reactor

  def Configure(self, **kwargs):
    self.pipe.params.update(kwargs)

  def Send(self, obj, size=0):
    def callback():
      self.received.append(obj)
    self.pipe(callback, size)

  def Wait(self, seconds):
    self.reactor.AdvanceTime(seconds)

  def Expect(self, received):
    self.assertItemsEqual(self.received, received)

  def testConstantDelay(self):
    self.Configure(delay=0.5)

    self.Send(1)
    self.Send(2)
    self.Expect([])

    self.Wait(0.5)
    self.Send(3)
    self.Expect([1, 2])

    self.Wait(0.5)
    self.Expect([1, 2, 3])

  def testThrottle(self):
    self.Configure(bandwidth=4096)

    self.Send(1, 1024)
    self.Send(2, 2048)
    self.Send(3, 0)
    self.Expect([])

    self.Wait(0.25)
    self.Expect([1])

    self.Wait(0.5)
    self.Expect([1, 2, 3])

  def testThrottlePlusConstantDelay(self):
    self.Configure(bandwidth=4096, delay=2.0)

    self.Send(1, 2048)
    self.Send(2, 2048)
    self.assertEqual(self.pipe.size, 4096)

    self.Wait(1.0)
    self.Expect([])
    self.assertEqual(self.pipe.size, 0)

    self.Wait(2.0)
    self.Expect([1, 2])

  def testBufferFull(self):
    self.Configure(bandwidth=1024, buffer=2048)

    self.Send(1, 1024)
    self.Send(2, 1024)
    self.Send(3, 1024)
    self.assertEqual(self.pipe.size, 2048)

    self.Wait(1.0)
    self.Expect([1])
    self.assertEqual(self.pipe.size, 1024)
    self.Send(4, 1024)

    self.Wait(1.0)
    self.Expect([1, 2])

    self.Wait(1.0)
    self.Expect([1, 2, 4])

  def testDropAll(self):
    self.Configure(delay=1.0, loss=1.0)

    self.Send(1, 1024)
    self.Wait(1.0)
    self.Expect([])
    self.assertEqual(self.pipe.bytes_attempted, 1024)
    self.assertEqual(self.pipe.bytes_delivered, 0)

  def testMeteringAllDelivered(self):
    self.Configure(delay=2.0)

    self.Send(1, 1024)
    self.Wait(1.0)
    self.assertEqual(self.pipe.bytes_attempted, 1024)
    self.assertEqual(self.pipe.bytes_delivered, 0)

    self.Send(1, 1024)
    self.assertEqual(self.pipe.bytes_attempted, 2048)
    self.assertEqual(self.pipe.bytes_delivered, 0)

    self.Wait(1.0)
    self.assertEqual(self.pipe.bytes_attempted, 2048)
    self.assertEqual(self.pipe.bytes_delivered, 1024)

    self.Wait(1.0)
    self.assertEqual(self.pipe.bytes_attempted, 2048)
    self.assertEqual(self.pipe.bytes_delivered, 2048)
