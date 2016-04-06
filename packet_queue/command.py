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
from . import simulation
from . import udp_proxy


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
      '-p', '--port', type=int, required=True,
      help='flaky inbound/outbound traffic occurs on specified port')

  if rest_server:
    parser.add_argument(
        '-a', '--rest_api_port', type=int,
        help='port which REST API server will listen on')

  params = simulation.Pipe.PARAMS
  pipes = simulation.PipePair(params)

  args = parser.parse_args()

  if args.level == 'kernel':
    import nfqueue # Makes imports that only work on Linux.
    nfqueue.configure(args.transport, args.port, pipes, args.interface)
  else:
    if args.transport == 'tcp':
      print 'Can\'t proxy TCP packets at the user level :('
      sys.exit(1)
    if not args.proxy_port:
      print '--proxy_port is required'
      sys.exit(1)
    udp_proxy.configure(args.port, args.proxy_port, pipes)

  return params, pipes, args
