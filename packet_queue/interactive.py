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

"""Interactive shell for network simulation."""

from IPython.terminal import embed
from twisted.internet import reactor
from twisted.internet import threads
from . import command


BANNER = '\n'.join([
  'Network simulation!',
  '',
  'You have an object, p, that you can use to change parameters on the fly.',
  'For example, to delay all packets by 300ms each direction:',
  '  p.delay = 0.3',
  '',
  'You also have any object called m, which does byte metering:',
  '  m',
  'Reset the numbers to zero with the reset() method:',
  '  m.reset()',
])


class ParamsProxy(object):
  def __init__(self, params):
    self.__dict__['_params'] = params

  def __getattr__(self, name):
    return self._params[name]

  def __setattr__(self, name, value):
    if name not in self._params:
      raise AttributeError(name)
    reactor.callFromThread(self._params.__setitem__, name, value)

  def __repr__(self):
    return repr(self._params)


class MeterProxy(object):
  def __init__(self, pipes):
    self.pipes = pipes

  def reset(self):
    reactor.callFromThread(self._atomic_reset)

  def _atomic_reset(self):
    self.pipes.Up.ResetMeter()
    self.pipes.Down.ResetMeter()

  def __repr__(self):
    return '\n'.join([
      'up:',
      '  attempted: {}'.format(self.pipes.Up.bytes_attempted),
      '  delivered: {}'.format(self.pipes.Up.bytes_delivered),
      'down:',
      '  attempted: {}'.format(self.pipes.Down.bytes_attempted),
      '  delivered: {}'.format(self.pipes.Down.bytes_delivered),
    ])


def Main():
  params, pipes, _ = command.Configure()
  shell = embed.InteractiveShellEmbed()
  shell.confirm_exit = False

  def run_shell():
    shell_vars = {
        'p': ParamsProxy(params),
        'm': MeterProxy(pipes),
    }
    shell.mainloop(shell_vars, display_banner=BANNER)

  deferred = threads.deferToThread(run_shell)
  deferred.addCallback(lambda result: reactor.stop())
  reactor.run()
