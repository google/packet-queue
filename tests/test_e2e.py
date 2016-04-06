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

"""End-to-end tests for nfqueue and UDP proxy integration."""
import multiprocessing
import os
import select
import socket
import unittest

from packet_queue import nfqueue
from packet_queue import simulation
from packet_queue import udp_proxy

from twisted.internet import reactor


def root_required(method):
  decorator = unittest.skipIf(os.getuid() != 0, 'root required')
  return decorator(method)


class FakeApp(object):
  """Networked client-server app to run simulation on.

  Consists of a client and a server. The client sends a single packet to the
  server, and the server echoes it back.
  """
  def __init__(self):
    self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

  def start_server(self):
    self.server.bind(('127.0.0.1', 0))
    return self.server.getsockname()[1]

  def send_packet(self, port):
    """Send a test packet from client to server."""
    self.client.connect(('127.0.0.1', port))
    self.client.send('test')

  def send_response(self):
    """Process an expected packet from the client and respond."""
    data, address = self.server.recvfrom(4)
    self.server.sendto(data, address)

  def get_readable(self):
    """See whether the server, client, or both are readable.

    This is potentially flaky since it uses a timeout, and might fail in
    slow environments.

    Returns a two-tuple of booleans representing the readable state of the
    server and client, in that order.
    """
    server = self.server.fileno()
    client = self.client.fileno()
    readable = select.select([server, client], [], [], 0.1)[0]
    return server in readable, client in readable


class EndToEndTest(unittest.TestCase):
  """Tests that run packet queue (either nfqueue or UDP proxy) as a child
  process, and run FakeApp in the current process.

  Multiprocessing is used instead of threading to keep Twisted happy, since it
  will complain if the reactor runs outside the main thread.
  """
  def setUp(self):
    self.app = FakeApp()
    self.port = self.app.start_server()
    self.params = dict(simulation.Pipe.PARAMS)
    self.child = None  # multiprocessing.Process
    self.ready = multiprocessing.Event()
    self.shared = multiprocessing.Manager().Namespace()

  def tearDown(self):
    if self.child:
      self.child.terminate()

  def set_ready(self):
    self.ready.set()

  def start_child(self, target):
    self.child = multiprocessing.Process(target=target)
    self.child.start()
    self.ready.wait(1.0)

  def run_nfqueue(self):
    pipes = simulation.PipePair(self.params)
    nfqueue.configure('udp', self.port, pipes, 'lo')
    reactor.callLater(0, self.set_ready)
    reactor.run()

  def run_proxy(self):
    pipes = simulation.PipePair(self.params)
    proxy_port = udp_proxy.configure(self.port, 0, pipes)
    self.shared.proxy_port = proxy_port
    reactor.callLater(0, self.set_ready)
    reactor.run()

  @root_required
  def test_nfqueue_deliver_all(self):
    self.start_child(self.run_nfqueue)

    self.app.send_packet(self.port)
    self.assertEqual(self.app.get_readable(), (True, False))

    self.app.send_response()
    self.assertEqual(self.app.get_readable(), (False, True))

  @root_required
  def test_nfqueue_drop_all(self):
    self.params['loss'] = 1.0
    self.start_child(self.run_nfqueue)

    self.app.send_packet(self.port)
    self.assertEqual(self.app.get_readable(), (False, False))

  def test_proxy_deliver_all(self):
    self.start_child(self.run_proxy)

    self.app.send_packet(self.port)
    self.assertEqual(self.app.get_readable(), (True, False))

    self.app.send_response()
    self.assertEqual(self.app.get_readable(), (False, True))

  def test_proxy_drop_all(self):
    self.params['loss'] = 1.0
    self.start_child(self.run_proxy)

    self.app.send_packet(self.shared.proxy_port)
    self.assertEqual(self.app.get_readable(), (False, False))


if __name__ == '__main__':
  unittest.main()
