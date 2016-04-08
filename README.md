# Packet Queue

This is a network simulator that can work in one of two ways:

- As a UDP proxy server, where a proxy port stands in for the real port and
  packets are forwarded to the server and back to the client.
- As a Linux [NFQUEUE](http://www.netfilter.org/projects/libnetfilter_queue/)
  implementation, handling all incoming and outgoing packets on a given port.

Both of these share the same set of network simulation parameters and behaviors,
abstracting the concept of a packet from IP and UDP.

## Installation

```
apt-get install libnetfilter-queue-dev
python setup.py build sdist
pip install dist/packet_queue-0.1.0.tar.gz
```

Set MTU on the loopback device to something small. This is also required
for bandwidth throttling to work correctly with NFQUEUE:

```
ip link show dev lo  # show current MTU (2 ** 16 by default)
ip link set dev lo mtu 2048  # reset on next restart
```

In addition, this package will install several scripts into `PATH`:

* `impaired_network_server` which starts up an impaired network and an API
  server to communicate with the network
* `impaired_network_shell` which starts up an impaired network and an external
  shell to communicate with the network
* `impaired_network_clear_ip_tables` resets `iptables` and removes all impaired
  network rules

## Unit tests

You can run most of the tests like this:

```
python -m unittest discover tests  # run all tests in the tests/ directory
```

Some of the end-to-end tests will be skipped with the above command because
they require root:

```
sudo python tests/test_e2e.py
```

## Trying it out: UDP proxy

There's an interactive mode where you can change settings on the fly inside a
Python shell. Right now it support constant-probability packet loss and constant
packet delay.

For a simple UDP application to test, you can use the
[QUIC server and client](https://www.chromium.org/quic/playing-with-quic) from
Chromium.

Then run the proxy. This command proxies a UDP server running on local port
6121, using 6122 as the proxy port:

```
impaired_network_shell -l user -t udp -p 6121 -x 6122
```

## Trying it out: NFQUEUE

The NFQUEUE implementation has the same interactive interface as the UDP proxy.
This command handles packets to/from a local TCP server running on port 8000:

```
sudo impaired_network_shell -l kernel -t tcp -p 8000
```
