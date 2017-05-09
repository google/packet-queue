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

import argparse
import netifaces
import sys
from . import monitoring
from . import simulation
from . import udp_proxy


def verify_packet_drop_range(arg):
  """Verifies the packet drop argument range is 0-1.

  Args:
    arg: The command line arg as a string
  Returns:
    The float value
  Raises:
    argparse.ArgumentTypeError: If the value is not a float or is out of range
  """
  try:
    arg = float(arg)
  except ValueError():
    raise argparse.ArgumentTypeError('expected packet loss must be a float')
  if arg < 0 or arg > 1.0:
    raise argparse.ArgumentTypeError('expected packet loss range is 0.0-1.0')
  return arg


def configure(rest_server=False):
  """Core startup routine.

  Args:
    rest_server: boolean specifying if the API server will be initialized
  Returns:
    A params dictionary object, the PairPipes instance, and results from argparse
  """
  parser = argparse.ArgumentParser()

  parser.add_argument(
      '-t', '--transport', type=str, choices=['tcp', 'udp'], default='tcp',
      help='transport protocol')
  parser.add_argument(
      '-l', '--level', type=str, choices=['kernel', 'user'], default='kernel',
      help='permissions level at which network interference will occur')
  parser.add_argument(
      '-i', '--interface', type=str, default='lo',
      help=('impaired TCP interface, defaults to "lo"; set to "auto" to '
            'impair the default outward-facing interface (e.g. eth0)'))
  parser.add_argument(
      '-x', '--proxy_port', type=int,
      help=('proxy port for receiving all inbound traffic if -luser'
            'is specified'))
  parser.add_argument(
      '-p', '--port', type=int, action='append', dest='ports', required=True,
      help='flaky inbound/outbound traffic occurs on specified port')
  parser.add_argument(
      '-b', '--bandwidth', type=int, default=-1,
      help='The bandwidth in bytes per second')
  parser.add_argument(
      '-d', '--delay', type=float, default=0,
      help='The one-way delay in seconds')
  parser.add_argument(
      '-B', '--buffer', type=int, default=-1,
      help='The size of the buffer in bytes')
  parser.add_argument(
      '-L', '--loss', type=verify_packet_drop_range, default=0.0,
      help='The packet drop ratio. must be in range 0.0-1.0')
  parser.add_argument(
      '-D', '--direction', default='inbound',
      choices=['inbound', 'outbound'],
      help='The direction of the connection to throttle. This pertains to the '
      'direction of the original connection request. Inbound means the '
      'connection must be remote->local. Outbound means the connection must be '
      'local->remote')
  parser.add_argument(
      '-V', '--ip_version', choices=['ipv4', 'ipv6'],
      action='append', default=[], dest='ip_versions',
      help='ip v[4,6] to use. Default is ipv4. Either or both can be specified')

  if rest_server:
    parser.add_argument(
        '-a', '--rest_api_port', type=int, default=9000,
        help='port which REST API server will listen on')

  args = parser.parse_args()

  # Set the default ip version if not specified
  if not args.ip_versions:
    args.ip_versions = ['ipv4']

  params = {
      'bandwidth': args.bandwidth,
      'buffer': args.buffer,
      'delay': args.delay,
      'loss': args.loss
  }

  event_log = monitoring.EventLog()
  pipes = simulation.PipePair(params, event_log)

  if args.level == 'kernel':
    import nfqueue # Makes imports that only work on Linux.
    nfqueue.configure(args.transport, args.ports, pipes, args.interface,
                      args.direction, 'ipv4' in args.ip_versions,
                      'ipv6' in args.ip_versions)
  else:
    if args.transport == 'tcp':
      print 'Can\'t proxy TCP packets at the user level :('
      sys.exit(1)
    if not args.proxy_port:
      print '--proxy_port is required'
      sys.exit(1)
    # UDP proxy is not setup for multiple ports. Only the first
    # will be used. This maintains the original behavior.
    udp_proxy.configure(args.ports[0], args.proxy_port, pipes)

  return params, pipes, args
