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

"""Setup module for packet queue"""

from setuptools import setup, find_packages
from codecs import open
from os import path

setup(
    name='packet_queue',
    version='0.1.0',
    zip_safe=False,  # python-iptables doesn't work well wtih eggs

    description='Packet-based impaired network library',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    install_requires=[
        'twisted', 'python-iptables', 'netifaces',
    ],
    scripts=[
        'scripts/impaired_network_server',
        'scripts/impaired_network_shell',
        'scripts/impaired_network_clear_iptables',
    ]
)
