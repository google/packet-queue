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

"""Network simulation adapter using NFQUEUE on Linux."""
import os
import netifaces
import struct
import iptc
import netfilterqueue
from twisted.internet import abstract
from twisted.internet import reactor


class NFQueueReader(abstract.FileDescriptor):
  """Twisted Reader that wraps netfilterqueue.NetfilterQueue."""
  def __init__(self, queue):
    self.queue = queue
    super(NFQueueReader, self).__init__()

  def doRead(self):
    self.queue.run(block=False)

  def fileno(self):
    return self.queue.get_fd()


def configure(protocol, port, pipes, interface):
  remove_all()
  reactor.addSystemEventTrigger('after', 'shutdown', remove_all)

  # gets default (outward-facing) network interface (e.g. deciding which of
  # eth0, eth1, wlan0 is being used by the system to connect to the internet)
  if interface == "auto":
    interface = netifaces.gateways()['default'][netifaces.AF_INET][1]
  else:
    if interface not in netifaces.interfaces():
      raise ValueError("Given interface does not exist.", interface)

  add(protocol, port, interface)
  queue = netfilterqueue.NetfilterQueue()

  def handle(packet):
    # python-netfilterqueue doesn't seem to handle multiple queues correctly,
    # so filter packets based on destination port as they come in.
    # TODO: Support IPv6.
    dport = struct.unpack('!H', packet.get_payload()[22:24])[0]
    size = packet.get_payload_len()
    pipe = (pipes.up if dport == port else pipes.down)
    pipe.attempt(packet.accept, size)

  queue.bind(1, handle)
  reactor.addReader(NFQueueReader(queue))


def add(protocol, port, interface):
  """Adds iptables NFQUEUE rules: one each for INPUT and OUTPUT."""
  table = iptc.Table(iptc.Table.FILTER)

  params =  [
    ('INPUT', 'in_interface', 'dport'),
    ('OUTPUT', 'out_interface', 'sport'),
  ]

  for chain_name, interface_attr, port_attr in params:
    chain = iptc.Chain(table, chain_name)
    rule = iptc.Rule()
    setattr(rule, interface_attr, interface)
    rule.protocol = protocol

    comment_match = rule.create_match('comment')
    comment_match.comment = 'white rabbit, pid: {}'.format(os.getpid())

    protocol_match = rule.create_match(protocol)
    setattr(protocol_match, port_attr, str(port))

    rule.target = rule.create_target('NFQUEUE')
    rule.target.set_parameter('queue-num', '1')
    chain.insert_rule(rule)


def remove_all():
  """Removes all iptables INPUT/OUTPUT rules commented for deletion."""
  table = iptc.Table(iptc.Table.FILTER)
  for chain_name in ['INPUT', 'OUTPUT']:
    chain = iptc.Chain(table, chain_name)
    for rule in chain.rules:
      for match in rule.matches:
        if match.comment and match.comment.startswith('white rabbit'):
          chain.delete_rule(rule)
          break

