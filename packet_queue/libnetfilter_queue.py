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

"""ctypes adapter for libnetfilter_queue on Linux."""
import collections
import ctypes
import socket


BUFFER_SIZE = 0xffff  # Largest possible IP packet.
NF_DROP = 0
NF_ACCEPT = 1
NFQNL_COPY_PACKET = 2
Packet = collections.namedtuple('Packet', ['id', 'size', 'payload', 'qh'])
nfq = ctypes.cdll.LoadLibrary('libnetfilter_queue.so')

class nfq_data(ctypes.Structure):
  pass

class msg_packet_header(ctypes.Structure):
  _fields_ = [('packet_id', ctypes.c_uint32)]

nfq.nfq_get_msg_packet_hdr.restype = ctypes.POINTER(msg_packet_header)

nfq_callback_type = ctypes.CFUNCTYPE(ctypes.c_int,
                                     ctypes.c_void_p,
                                     ctypes.c_void_p,
                                     ctypes.POINTER(nfq_data),
                                     ctypes.c_void_p)

@nfq_callback_type
def nfq_callback(qh, unused_nfmsg, nfad, unused_data):
  packet = nfq.nfq_get_msg_packet_hdr(nfad).contents
  packet_id = socket.ntohl(packet.packet_id)

  payload_pointer = ctypes.c_void_p()
  size = nfq.nfq_get_payload(nfad, ctypes.byref(payload_pointer))
  payload = ctypes.string_at(payload_pointer, size)

  packet = Packet(packet_id, size, payload, qh)
  py_callbacks[qh](packet)
  return 0

# Maps queue handles to user-specified callbacks.
py_callbacks = {}


class Manager(object):
  """Manages multiple queues."""

  def __init__(self):
    self.handle = nfq.nfq_open()
    self.fileno = nfq.nfq_fd(self.handle)
    self.socket = socket.fromfd(self.fileno, socket.AF_UNIX, socket.SOCK_RAW)

    if nfq.nfq_unbind_pf(self.handle, socket.AF_INET) < 0:
      raise OSError('nfq_unbind_pf() failed. Are you root?')

    if nfq.nfq_bind_pf(self.handle, socket.AF_INET) < 0:
      raise OSError('nfq_bind_pf() failed. Are you root?')

  def set_verdict(self, packet, verdict):
    """Set the verdict on a Packet instance: NF_ACCEPT or NF_DROP."""
    payload_buffer = ctypes.create_string_buffer(packet.payload)
    nfq.nfq_set_verdict(packet.qh,
                        packet.id,
                        verdict,
                        packet.size,
                        payload_buffer)

  def bind(self, queue_num, callback):
    """Bind a queue number to a callback.

    The callback should take a single argument: a Packet instance.
    """
    qh = nfq.nfq_create_queue(self.handle, queue_num, nfq_callback, None)
    if qh <= 0:
      raise OSError('nfq_create_queue() failed. Is packet queue already running?')

    py_callbacks[qh] = callback
    nfq.nfq_set_mode(qh, NFQNL_COPY_PACKET, BUFFER_SIZE)

  def process(self):
    """Without blocking, read available packets and invoke their callbacks."""
    data = self.socket.recv(BUFFER_SIZE, socket.MSG_DONTWAIT)
    buf = ctypes.create_string_buffer(data)
    nfq.nfq_handle_packet(self.handle, buf, len(data))
