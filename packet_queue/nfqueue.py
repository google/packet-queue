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
import iptc
from twisted.internet import abstract
from twisted.internet import reactor

from packet_queue import libnetfilter_queue


UP_QUEUE = 1
DOWN_QUEUE = 2


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
  manager = libnetfilter_queue.Manager()

  def on_up(packet):
    def accept():
      manager.set_verdict(packet, libnetfilter_queue.NF_ACCEPT)
    pipes.up.attempt(accept, packet.size)

  def on_down(packet):
    def accept():
      manager.set_verdict(packet, libnetfilter_queue.NF_ACCEPT)
    pipes.down.attempt(accept, packet.size)

  manager.bind(UP_QUEUE, on_up)
  manager.bind(DOWN_QUEUE, on_down)

  reader = abstract.FileDescriptor()
  reader.doRead = manager.process
  reader.fileno = lambda: manager.fileno
  reactor.addReader(reader)


def add(protocol, port, interface):
  """Adds iptables NFQUEUE rules: one each for INPUT and OUTPUT."""
  table = iptc.Table(iptc.Table.FILTER)

  params =  [
    ('INPUT', 'in_interface', 'dport', UP_QUEUE),
    ('OUTPUT', 'out_interface', 'sport', DOWN_QUEUE),
  ]

  for chain_name, interface_attr, port_attr, queue_num in params:
    chain = iptc.Chain(table, chain_name)
    rule = iptc.Rule()
    setattr(rule, interface_attr, interface)
    rule.protocol = protocol

    comment_match = rule.create_match('comment')
    comment_match.comment = 'white rabbit, pid: {}'.format(os.getpid())

    protocol_match = rule.create_match(protocol)
    setattr(protocol_match, port_attr, str(port))

    rule.target = rule.create_target('NFQUEUE')
    rule.target.set_parameter('queue-num', str(queue_num))
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
