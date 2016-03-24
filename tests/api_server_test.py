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

import json
import StringIO

from twisted.trial import unittest
from twisted.web import http_headers

from twisted.internet.defer import succeed
from twisted.web.test import test_web

from packet_queue import api_server
from packet_queue import simulation


def ConstructDummyRequest(method="GET", data=""):
  request = test_web.DummyRequest([""])

  request.content = StringIO.StringIO(data)
  request.method = method  # checked by Twisted's resource.Resource.render

  return request


class DummyReactor(object):
  """Substitute for the Twisted reactor module.

  Executes callbacks immediately or not at all.
  """
  def __init__(self):
    self.execute = True

  def callLater(self, delay, callback):
    if self.execute:
      callback()


class PipeParamsTest(unittest.TestCase):
  def testNullCase(self):
    self.assertEqual(api_server.ParsePipeParams({}), {})

  def testInvalidKey(self):
    self.assertEqual(api_server.ParsePipeParams({"foo": 0}), {})

  def testInvalidCast(self):
    self.assertRaises(ValueError, api_server.ParsePipeParams, {"bandwidth": "foobar"})
    self.assertRaises(ValueError, api_server.ParsePipeParams, {"bandwidth": "1.5"})
    self.assertRaises(TypeError, api_server.ParsePipeParams, {"bandwidth": {}})
    self.assertRaises(TypeError, api_server.ParsePipeParams, {"bandwidth": ()})
    self.assertRaises(TypeError, api_server.ParsePipeParams, {"bandwidth": None})

  def testNormalCase(self):
    expected = {"bandwidth": -1}
    actual = api_server.ParsePipeParams({"bandwidth": "-1"})
    self.assertEqual(actual, expected)

    expected = {"loss": 0.5}
    actual = api_server.ParsePipeParams({"loss": ".5"})
    self.assertEqual(actual, expected)

  def testNonDefaultTypes(self):
    types = {"some_int": int, "some_float": float}
    actual = api_server.ParsePipeParams({"some_int": "1"}, types)
    self.assertEqual(actual, {"some_int": 1})

    actual = api_server.ParsePipeParams({"some_float": "1.0"}, types)
    self.assertEqual(actual, {"some_float": 1.0})


class PipeResourceTest(unittest.TestCase):

  BASE_PARAMS = {"foo": 100, "bar": 107}  # base params reference

  def setUp(self):
    # mutable reference, mirrors Resource
    self.params = dict(self.BASE_PARAMS)

    self.resource = api_server.PipeResource(params=self.params)

  def testGetInitState(self):
    request = ConstructDummyRequest()
    content = self.resource.render(request)
    self.assertEqual(json.loads(content), self.BASE_PARAMS)

  def testPutNoContent(self):
    request = ConstructDummyRequest(method="PUT", data="")
    self.resource.render(request)
    self.assertEqual(request.responseCode, 400)

  def testPutEmptyParams(self):
    request = ConstructDummyRequest(method="PUT", data="{}")
    content = self.resource.render(request)
    self.assertEqual(json.loads(content), self.BASE_PARAMS)

  def testPutInvalidRequest(self):
    """Invalid param types should be caught by handler and indicated in response.

    We are not testing the full suite of possible bad params possible --
    this should be already tested in simulation.ParsePipeParams unit tests.
    """

    new = {"foo": "blaaaaaah"}
    request = ConstructDummyRequest(method="PUT", data=json.dumps(new))
    content = self.resource.render(request)

    self.assertEqual(request.responseCode, 400)
    data = json.loads(content)
    self.assertTrue("request" in data)
    self.assertEqual(json.loads(data["request"]), new)

  def testPutValidRequest(self):
    """Assert PUT requests actually change the simulation parameters."""

    new = {"foo": 128}
    expected = {"foo": 128, "bar": 107}

    request = ConstructDummyRequest(method="PUT", data=json.dumps(new))
    content = self.resource.render(request)

    # return proper state
    self.assertEqual(json.loads(content), expected)

    # correctly set params
    self.assertEqual(self.params, expected)

  def testDeleteRequest(self):
    new = {"foo": 128}

    self.resource.render(
        ConstructDummyRequest(method="PUT", data=json.dumps(new)))

    request = ConstructDummyRequest(method="DELETE")
    content = self.resource.render(request)

    self.assertEqual(json.loads(content), self.BASE_PARAMS)


class MeterResourceTest(unittest.TestCase):
  def setUp(self):
    self.pipes = simulation.PipePair(simulation.Pipe.PARAMS)
    self.resource = api_server.MeterResource(self.pipes)

    self.reactor = DummyReactor()
    simulation.reactor = self.reactor

  def testGet(self):
    self.pipes.Up(lambda: None, 1024)
    self.reactor.execute = False
    self.pipes.Down(lambda: None, 2048)

    expected = {
        "up_bytes_attempted": 1024,
        "up_bytes_delivered": 1024,
        "down_bytes_attempted": 2048,
        "down_bytes_delivered": 0,
    }

    request = ConstructDummyRequest(method="GET")
    content = self.resource.render(request)
    self.assertEqual(json.loads(content), expected)
