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

"""REST API server backend.

Creates and maintains the pipes params, updating params on the fly.
"""

import argparse
import json
import os
import sys
import time

from twisted.internet import reactor
from twisted.web import resource
from twisted.web import static
from twisted.web import server
from twisted.web import util

from . import command
from . import simulation


def create_site(params, pipes):
  source_dir = os.path.dirname(os.path.abspath(__file__))
  web_dir = os.path.join(source_dir, 'web')

  root = static.File(web_dir)
  root.putChild('pipes', PipeResource(params))
  root.putChild('events', EventsResource(pipes.event_log))
  return server.Site(root)


def parse_pipe_params(args, types=None):
  """Ensure pipe parameter args are of correct type.

  Args:
    args: {arg: value} dictionary where "arg" is a key in the types dict
    type: {arg: type(value)} dictionary; defaults to type of simulation.Pipe.PARAMS

  Returns:
    Cleaned {arg: value} dictionary, where value is of correct type

  Raises:
    ValueError in case of invalid cast result (raised from attempted
        typecast PARAM_TYPES[k]())
    TypeError in case of invalid cast type (raised from attempted typecast)
  """

  if types is None:
    types = {k: type(v) for (k, v) in simulation.Pipe.PARAMS.items()}

  return {k: types[k](v) for (k, v) in args.items() if k in types}


class PipeResource(resource.Resource):
  """RESTful API to handle changing the pipe parameters."""

  is_leaf = True

  def __init__(self, params):
    self.params = params
    self.param_types = {k: type(v) for (k, v) in params.items()}
    self.default = dict(params)  # read-only copy of initial params
    resource.Resource.__init__(self)

  def render_DELETE(self, request):
    """Resets params to initial state."""

    self.params.update(self.default)

    request.setHeader('Content-Type', 'application/json')
    return json.dumps(self.params)

  def render_GET(self, request):
    request.setHeader('Content-Type', 'application/json')
    return json.dumps(self.params)

  def render_PUT(self, request):
    """Updates the params object.

    Args:
      request: HTTP request object; request BODY is set to JSON query
          note that this is NOT canonical REST request/response, but done here
          for the sake of code brevity
    Returns:
      JSON string representing the page contents
    """
    content = request.content.read()
    request.setHeader('Content-Type', 'application/json')

    try:
      params = parse_pipe_params(json.loads(content), self.param_types)
    except (KeyError, ValueError):
      request.setResponseCode(400)
      response = {'error': 'Unable to parse parameters'}
      return json.dumps(response)
    else:
      self.params.update(params)
      return json.dumps(self.params)


class EventsResource(resource.Resource):
  """Provides a view of recent network simulation events."""

  is_leaf = True

  def __init__(self, event_log):
    self.event_log = event_log
    resource.Resource.__init__(self)

  def render_GET(self, request):
    events = self.event_log.get_pending()
    response = {'now': time.time(), 'events': events}
    return json.dumps(response)


def configure():
  params, pipes, args = command.configure(rest_server=True)
  port = args.rest_api_port

  reactor.listenTCP(port, create_site(params, pipes))
  @reactor.callWhenRunning
  def startup_message():
    print 'Packet Queue is running. Configure at http://localhost:%i' % port
    sys.stdout.flush()
