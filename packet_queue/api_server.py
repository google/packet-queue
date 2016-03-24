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

from twisted.internet import reactor
from twisted.web import resource
from twisted.web import server
from twisted.web import util

from . import command
from . import simulation


def CreateSite(params, pipes):
  root = resource.Resource()
  root.putChild("pipes", PipeResource(params))
  root.putChild("bytes", MeterResource(pipes))
  return server.Site(root)


def ParsePipeParams(args, types=None):
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

    request.setHeader("Content-Type", "application/json")
    return json.dumps(self.params)

  def render_GET(self, request):
    request.setHeader("Content-Type", "application/json")
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

    content = request.content.read()  # request BODY

    try:
      args = ParsePipeParams(json.loads(content), self.param_types)
    except (ValueError, TypeError):
      request.setResponseCode(400)
      return json.dumps({"error": "Malformed parameter value", "request": content})

    self.params.update(args)

    request.setHeader("Content-Type", "application/json")
    return json.dumps(self.params)


class MeterResource(resource.Resource):
  """Provides the number of bytes attempted and delivered."""

  is_leaf = True

  def __init__(self, pipes):
    """Args:
      pipes: simulation.Pipe instance
    """
    self.pipes = pipes
    resource.Resource.__init__(self)

  def render_GET(self, request):
    response = {
        "up_bytes_attempted": self.pipes.Up.bytes_attempted,
        "up_bytes_delivered": self.pipes.Up.bytes_delivered,
        "down_bytes_attempted": self.pipes.Down.bytes_attempted,
        "down_bytes_delivered": self.pipes.Down.bytes_delivered,
    }

    request.setHeader("Content-Type", "application/json")
    return json.dumps(response)


def Configure():
  params, pipes, args = command.Configure(rest_server=True)
  reactor.listenTCP(args.rest_api_port, CreateSite(params, pipes))
