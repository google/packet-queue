/**
 * Copyright 2016 Google Inc. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

var GRAPH_OPTIONS = {
  millisPerPixel: 40,
  minValue: 0
};

var BLUE_LINE_OPTIONS = {
  lineWidth: 3,
  strokeStyle: 'rgb(80, 120, 255)',
  fillStyle: 'rgba(80, 120, 255, 0.3)'
};

var RED_LINE_OPTIONS = {
  lineWidth: 3,
  strokeStyle: 'rgb(255, 120, 120)',
  fillStyle: 'rgba(255, 120, 120, 0.3)'
};

var timeSeriesMap = {
  up: {
    buffer: new TimeSeries(),
    latency: new TimeSeries(),
    deliver: new TimeSeries(),
    drop: new TimeSeries()
  },
  down: {
    buffer: new TimeSeries(),
    latency: new TimeSeries(),
    deliver: new TimeSeries(),
    drop: new TimeSeries()
  }
};

var byteCount = {
  up: {
    drop: 0,
    deliver: 0
  },
  down: {
    drop: 0,
    deliver: 0
  }
};

var toMillis = function(seconds) {
  return Math.floor(seconds * 1000);
};

var requestNewEvents = function() {
  var xhr = new XMLHttpRequest();
  xhr.responseType = 'json';
  xhr.open('GET', '/events');
  xhr.onload = onNewEvents;
  xhr.send();
};

var onNewEvents = function() {
  var events = this.response.events;
  var serverTime = toMillis(this.response.now);
  var timeDiff = Date.now() - serverTime;

  for (var i = 0; i < events.length; i++) {
    var e = events[i];
    var timeSeries = timeSeriesMap[e.pipe][e.type];

    if (e.type == 'drop' || e.type == 'deliver') {
      byteCount[e.pipe][e.type] += e.value;
      var value = byteCount[e.pipe][e.type];
    } else {
      var value = e.value;
    }

    var time = toMillis(e.time) + timeDiff;
    timeSeries.append(time, value);
  }
};

var initGraphs = function() {
  var canvasElements = document.getElementsByTagName('canvas');
  for (var i = 0; i < canvasElements.length; i++) {
    var element = canvasElements[i];
    var idParts = element.id.split('-');
    var pipe = idParts[0];
    var graphName = idParts[1];

    var graph = new SmoothieChart(GRAPH_OPTIONS);
    graph.streamTo(element, 1000);

    if (graphName == 'bytes') {
      var deliverTimeSeries = timeSeriesMap[pipe].deliver;
      var dropTimeSeries = timeSeriesMap[pipe].drop;
      graph.addTimeSeries(deliverTimeSeries, BLUE_LINE_OPTIONS);
      graph.addTimeSeries(dropTimeSeries, RED_LINE_OPTIONS);
    } else {
      var timeSeries = timeSeriesMap[pipe][graphName];
      graph.addTimeSeries(timeSeries, BLUE_LINE_OPTIONS);
    }
  }

  setInterval(requestNewEvents, 1000);
};

var onParamsSubmit = function(event) {
  event.preventDefault();
  showParamsError('');

  var params = {
    bandwidth: parseInt(this.elements.bandwidth.value),
    buffer: parseInt(this.elements.buffer.value),
    delay: parseFloat(this.elements.delay.value),
    loss: parseFloat(this.elements.loss.value)
  };

  var xhr = new XMLHttpRequest();
  xhr.responseType = 'json';
  xhr.open('PUT', '/pipes');
  xhr.onload = onParamsResponse;
  xhr.onerror = onParamsNetworkError;
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.send(JSON.stringify(params));
};

var onParamsResponse = function() {
  var response = this.response;
  if (response) {
    for (key in response) {
      var value = response[key];
      var inputElement = document.getElementById('param-' + key);
      var valueElement = document.getElementById('param-value-' + key);
      inputElement.value = value;
      valueElement.textContent = value;
    }
  } else {
    showParamsError('Updating params failed. Check the server log.')
  }
};

var onParamsNetworkError = function() {
  showParamsError('Network error. Is the packet queue running?');
};

var showParamsError = function(message) {
  element = document.getElementById('params-error');
  element.textContent = message;
};

var initParams = function() {
  var xhr = new XMLHttpRequest();
  xhr.responseType = 'json';
  xhr.open('GET', '/pipes');
  xhr.onload = onParamsResponse;
  xhr.send();

  var form = document.getElementById('params');
  form.addEventListener('submit', onParamsSubmit);
};

document.addEventListener('DOMContentLoaded', function(event) {
  initParams();
  initGraphs();
});
