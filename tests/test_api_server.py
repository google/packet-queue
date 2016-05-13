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


def construct_dummy_request(method="GET", data=""):
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

  def test_null_case(self):
    self.assertEqual(api_server.parse_pipe_params({}), {})

  def test_invalid_key(self):
    self.assertEqual(api_server.parse_pipe_params({"foo": 0}), {})

  def test_invalid_cast(self):
    self.assertRaises(ValueError, api_server.parse_pipe_params, {"bandwidth": "foobar"})
    self.assertRaises(ValueError, api_server.parse_pipe_params, {"bandwidth": "1.5"})
    self.assertRaises(TypeError, api_server.parse_pipe_params, {"bandwidth": {}})
    self.assertRaises(TypeError, api_server.parse_pipe_params, {"bandwidth": ()})
    self.assertRaises(TypeError, api_server.parse_pipe_params, {"bandwidth": None})

  def test_normal_case(self):
    expected = {"bandwidth": -1}
    actual = api_server.parse_pipe_params({"bandwidth": "-1"})
    self.assertEqual(actual, expected)

    expected = {"loss": 0.5}
    actual = api_server.parse_pipe_params({"loss": ".5"})
    self.assertEqual(actual, expected)

  def test_non_default_types(self):
    types = {"some_int": int, "some_float": float}
    actual = api_server.parse_pipe_params({"some_int": "1"}, types)
    self.assertEqual(actual, {"some_int": 1})

    actual = api_server.parse_pipe_params({"some_float": "1.0"}, types)
    self.assertEqual(actual, {"some_float": 1.0})


class PipeResourceTest(unittest.TestCase):

  BASE_PARAMS = {"foo": 100, "bar": 107}  # base params reference

  def setUp(self):
    # mutable reference, mirrors Resource
    self.params = dict(self.BASE_PARAMS)

    self.resource = api_server.PipeResource(params=self.params)

  def test_get_init_state(self):
    request = construct_dummy_request()
    content = self.resource.render(request)
    self.assertEqual(json.loads(content), self.BASE_PARAMS)

  def test_put_no_content(self):
    request = construct_dummy_request(method="PUT", data="")
    self.resource.render(request)
    self.assertEqual(request.responseCode, 400)

  def test_put_empty_params(self):
    request = construct_dummy_request(method="PUT", data="{}")
    content = self.resource.render(request)
    self.assertEqual(json.loads(content), self.BASE_PARAMS)

  def test_put_invalid_request(self):
    """Invalid param types should be caught by handler and indicated in response.

    We are not testing the full suite of possible bad params possible --
    this should be already tested in simulation.parse_pipe_params unit tests.
    """

    new = {"foo": "blaaaaaah"}
    request = construct_dummy_request(method="PUT", data=json.dumps(new))
    content = self.resource.render(request)

    self.assertEqual(request.responseCode, 400)
    data = json.loads(content)
    self.assertTrue("error" in data, data)

  def test_put_valid_request(self):
    """Assert PUT requests actually change the simulation parameters."""

    new = {"foo": 128}
    expected = {"foo": 128, "bar": 107}

    request = construct_dummy_request(method="PUT", data=json.dumps(new))
    content = self.resource.render(request)

    # return proper state
    self.assertEqual(json.loads(content), expected)

    # correctly set params
    self.assertEqual(self.params, expected)

  def test_delete_request(self):
    new = {"foo": 128}

    self.resource.render(
        construct_dummy_request(method="PUT", data=json.dumps(new)))

    request = construct_dummy_request(method="DELETE")
    content = self.resource.render(request)

    self.assertEqual(json.loads(content), self.BASE_PARAMS)
