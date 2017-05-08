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


def packet_handler(manager, pipe):
  def on_packet(packet):
    def accept():
      manager.set_verdict(packet, libnetfilter_queue.NF_ACCEPT)
    def drop():
      manager.set_verdict(packet, libnetfilter_queue.NF_DROP)
    pipe.attempt(accept, drop, packet.size)
  return on_packet


def configure(protocol, ports, pipes, interface, direction, use_ipv4, use_ipv6):
  remove_all()
  reactor.addSystemEventTrigger('after', 'shutdown', remove_all)

  # gets default (outward-facing) network interface (e.g. deciding which of
  # eth0, eth1, wlan0 is being used by the system to connect to the internet)
  if interface == 'auto':
    interface = netifaces.gateways()['default'][netifaces.AF_INET][1]
  else:
    if interface not in netifaces.interfaces():
      raise ValueError('Given interface does not exist.', interface)

  for port in ports:
    add(protocol, port, interface, direction, use_ipv4, use_ipv6)

  manager = libnetfilter_queue.Manager()
  manager.bind(UP_QUEUE, packet_handler(manager, pipes.up))
  manager.bind(DOWN_QUEUE, packet_handler(manager, pipes.down))

  reader = abstract.FileDescriptor()
  reader.doRead = manager.process
  reader.fileno = lambda: manager.fileno
  reactor.addReader(reader)


def add(protocol, port, interface, direction, use_ipv4, use_ipv6):
  """Adds iptables NFQUEUE rules: one each for INPUT/OUTPUT/IPv4/IPv6."""
  # Add IPv4 handlers
  if use_ipv4:
    _add(protocol, port, interface, direction, iptc.Table, iptc.Rule)
  # Add IPv6 handlers
  if use_ipv6:
    _add(protocol, port, interface, direction, iptc.Table6, iptc.Rule6)


def _add(protocol, port, interface, direction, table_cls, rule_cls):
  """Adds iptables NFQUEUE rules: one each for INPUT and OUTPUT."""
  table = table_cls(iptc.Table.FILTER)

  if direction == 'inbound':
    ports = ('dport', 'sport')
  else:
    ports = ('sport', 'dport')

  params = [
    ('INPUT', 'in_interface', ports[0], UP_QUEUE),
    ('OUTPUT', 'out_interface', ports[1], DOWN_QUEUE),
  ]

  for chain_name, interface_attr, port_attr, queue_num in params:
    chain = iptc.Chain(table, chain_name)
    rule = rule_cls()
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
  def remove_rules(table):
    # Deleting multiple rules on a queue with autocommit on fails
    # due to the fact that the table is updated on each delete
    # which causes the list to change and iteration to fail.
    table.autocommit = False
    try:
      for chain_name in ['INPUT', 'OUTPUT']:
        chain = iptc.Chain(table, chain_name)
        for rule in chain.rules:
          for match in rule.matches:
            if match.comment and match.comment.startswith('white rabbit'):
              chain.delete_rule(rule)
              break
    finally:
      table.commit()
      table.autocommit = True

  # ip v4 rules
  remove_rules(iptc.Table(iptc.Table.FILTER))
  # ip v6 rules
  remove_rules(iptc.Table6(iptc.Table6.FILTER))
