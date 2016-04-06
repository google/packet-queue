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

"""Network simulation adapter using a user-level UDP proxy."""
from twisted.internet import protocol
from twisted.internet import reactor


# Header bytes in each UDP packet. Used for bandwidth estimation.
OVERHEAD = 28


def Configure(port, proxy_port, pipes):
  """Starts a UDP proxy server on localhost.

  Returns the proxy port number, which is the same as the proxy_port param
  unless zero is passed in.
  """
  server = ProxyServer(port, pipes)
  port = reactor.listenUDP(proxy_port, server.udp)
  return port.getHost().port


class UDP(protocol.DatagramProtocol):
  """Lightweight interface for Twisted UDP functionality.

  This exists to make it easier to test the interesting stuff, by isolating all
  of the network interaction and Twisted inheritance.
  """
  def __init__(self, receiver):
    self.receiver = receiver

  def Send(self, data, address):
    self.transport.write(data, address)

  def datagramReceived(self, *args):
    """Invoked by Twisted."""
    self.receiver(*args)


class ProxyServer(object):
  """Proxies a UDP server. Incoming packets are from clients.

  Creates a UDP socket for each address it receives data from, and uses it as
  as a proxy client for the server. This is so that the port for an incoming
  packet from the server can be used to determine which client it should be
  relayed to.
  """
  def __init__(self, port, pipes):
    self.udp = UDP(self.Receive)
    self.server_address = ('127.0.0.1', port)
    self.proxy_clients = {}
    self.pipes = pipes

  def Receive(self, data, address):
    """Invoked by Twisted when a packet arrives at the client-facing port.

    Relays the packet to the server using the appropriate proxy client.
    """
    proxy_client = self._GetProxyClient(address)
    def callback():
      proxy_client.udp.Send(data, self.server_address)
    self.pipes.Up(callback, len(data) + OVERHEAD)

  def _GetProxyClient(self, address):
    """Gets a proxy client for a given client address.

    Returns the new proxy client, or an existing one if the address has been
    used before.
    """
    if address in self.proxy_clients:
      proxy_client = self.proxy_clients[address]
    else:
      proxy_client = ProxyClient(self, address)
      self.proxy_clients[address] = proxy_client
      reactor.listenUDP(0, proxy_client.udp)

    return proxy_client


class ProxyClient(object):
  """Proxies a UDP client. Incoming packets are from the server."""
  def __init__(self, proxy_server, relay_address):
    self.udp = UDP(self.Receive)
    self.proxy_server = proxy_server
    self.relay_address = relay_address

  def Receive(self, data, ignore_address):
    """Invoked by Twisted when a packet arrives from the server.

    Relays the packet to the actual client, via ProxyServer.
    """
    def callback():
      self.proxy_server.udp.Send(data, self.relay_address)
    self.proxy_server.pipes.Down(callback, len(data) + OVERHEAD)
