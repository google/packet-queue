# Packet Queue

This is a configurable TCP/UDP packet impairment tool for Linux. It looks like
this:

<img alt="Screenshot" src="screenshot.png" width="440">

## Setup

Install the dependencies, including the Linux nfqueue library:

```
sudo apt-get install libnetfilter-queue-dev
sudo python setup.py develop
```

To get realistic network simulation on the loopback device, you probably want
to set the MTU to something small:

```
ip link show dev lo  # show current MTU
sudo ip link set dev lo mtu 2048
```

## Running

For example, to impair TCP traffic on loopback port 3000:

```
sudo scripts/impaired_network_server -p 3000
```

It can also run as a UDP proxy, without root, if you specify a proxy port:

```
scripts/impaired_network_server -l user -t udp -p 3000 -x 3001
```

To see all of the options:

```
scripts/impaired_network_server --help
```

Packet Queue will clean up its iptables rules on shutdown. If it ever doesn't
shut down gracefully, you can clear the rules like this:

```
sudo scripts/impaired_network_clear_iptables
```

## Tests

You can run most of the tests like this:

```
python -m unittest discover tests  # run all tests in the tests/ directory
```

Some of the end-to-end tests will be skipped with the above command because
they require root:

```
sudo python tests/test_e2e.py
```
