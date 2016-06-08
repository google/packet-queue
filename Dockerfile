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
#
#
# docker build -t <LABEL> .
# docker run --cap-add=NET_ADMIN -t <LABEL> -p <APP_PORT>,<API_PORT> \
# impaired_network_server -t tcp -l kernel -i auto -p <APP_PORT> -a <API_PORT>

FROM ubuntu:14.04

RUN apt-get -y update
RUN apt-get -y install python iptables git
RUN apt-get -y install python-setuptools python-dev build-essential python-pip

RUN apt-get -y install libnetfilter-queue-dev

RUN mkdir /src
WORKDIR /src

RUN git clone https://github.com/google/packet-queue.git

WORKDIR /src/packet-queue

RUN pip install .

WORKDIR /src
RUN rm -rf /src/packet-queue

RUN groupadd whiterabbit
RUN echo "%whiterabbit ALL=(root) NOPASSWD: "`which impaired_network_server` >> /etc/sudoers.d/whiterabbit
