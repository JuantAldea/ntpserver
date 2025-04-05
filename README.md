# Python NTP Server in Network Namespaces

A tool for running multiple NTP (Network Time Protocol) servers with customizable time offsets in isolated network namespaces.

## Overview

This project provides a Bash script for easily creating and managing NTP servers running in Linux network namespaces. Each server can be configured with different parameters like time offsets, stratum levels, and leap second indicators. The servers are isolated in their own network namespaces, allowing multiple servers to coexist on a single host.

## Features

- Create isolated NTP servers in network namespaces
- Configure time offsets, stratum levels, and leap second indicators
- Create multiple NTP servers at once with batch mode
- Easy management with command-line interface
- View logs of running NTP servers
- Cleanup capabilities to easily remove all created resources

## Requirements

- Python 3
- Linux with network namespace support
- Root access (for network namespace operations)
- `iproute2` package

## Usage

### Basic Commands

Run the script without arguments to see the help message:

```bash
./ntp_server_namespace_manager
```

### Creating an NTP Server

Create a single NTP server:

```bash
sudo ./ntp_server_namespace_manager create -i 1
```

Create an NTP server with custom parameters:

```bash
sudo ./ntp_server_namespace_manager create -i 2 -s 10.0.0 -o 3600 -t 1 -l 0
```

Where:
- `-i, --instance`: Instance number (default: 1)
- `-s, --subnet`: Subnet base address (default: 192.168.100)
- `-o, --offset`: Time offset in seconds (default: 0)
- `-t, --stratum`: NTP stratum level (default: 2)
- `-l, --leap`: Leap second indicator (default: 0)

### Batch Creation of Multiple Servers

Create multiple NTP servers at once:

`sudo bash ntp_server_namespace_manager.bash batch --start 1 --end 3 -s 192.168.100 -o 3600`
```
Creating multiple NTP server namespaces from instance 1 to 3
Using subnet 192.168.100, time offset 3600 seconds, stratum 2
=== Creating instance 1 ===
Creating namespace: py_ntp_ns_1 with IP: 192.168.100.1
Creating bridge br0
Creating namespace: py_ntp_ns_1 and veth pair: veth1_host <-> veth1_ns
Starting Python NTP server in namespace py_ntp_ns_1
IP: 192.168.100.1, Time offset: 3600 seconds, Stratum: 2, Leap: 0
Python NTP server started successfully with PID 953597
Namespace py_ntp_ns_1 created with IP 192.168.100.1 and running Python NTP server.

=== Creating instance 2 ===
Creating namespace: py_ntp_ns_2 with IP: 192.168.100.2
Creating namespace: py_ntp_ns_2 and veth pair: veth2_host <-> veth2_ns
Starting Python NTP server in namespace py_ntp_ns_2
IP: 192.168.100.2, Time offset: 3600 seconds, Stratum: 2, Leap: 0
Python NTP server started successfully with PID 953637
Namespace py_ntp_ns_2 created with IP 192.168.100.2 and running Python NTP server.

=== Creating instance 3 ===
Creating namespace: py_ntp_ns_3 with IP: 192.168.100.3
Creating namespace: py_ntp_ns_3 and veth pair: veth3_host <-> veth3_ns
Starting Python NTP server in namespace py_ntp_ns_3
IP: 192.168.100.3, Time offset: 3600 seconds, Stratum: 2, Leap: 0
Python NTP server started successfully with PID 953667
Namespace py_ntp_ns_3 created with IP 192.168.100.3 and running Python NTP server.

Batch creation complete: 3 instances created successfully, 0 failures.
Use 'ntp_server_namespace_manager.bash list' to see all namespaces.
Use 'ntp_server_namespace_manager.bash logs -i <instance>' to view logs for a specific server.
```

This creates 5 servers with IPs 10.0.0.1 through 10.0.0.5, all with a 1-hour time offset.

### Managing NTP Servers

List all created NTP servers:


`sudo ./ntp_server_namespace_manager list`
```
NTP namespaces:
py_ntp_ns_2 (id: 1)
py_ntp_ns_1 (id: 0)
```

View logs for a specific NTP server:

`sudo ./ntp_server_namespace_manager logs -i 1`

```
Instance directory: /tmp/py_ntp_ns_1
Log file: /tmp/py_ntp_ns_1/server.log
Namespace: py_ntp_ns_1
Instance: 1
Showing logs for NTP server in namespace: 1
PID: 949192
Found Python process with PID 949192 in namespace py_ntp_ns_1
Process information:
UID          PID    PPID  C STIME TTY          TIME CMD
root      949192       1  0 23:40 ?        00:00:00 python3 ./ntpserver.py --ip 192.168.100.1 --offset 0 --stratum 2 --leap 0 --lo

Server log:2025-04-05 23:40:49,573 - INFO - NTP server started on 192.168.100.1:123
2025-04-05 23:40:49,573 - INFO - Stratum: 2
2025-04-05 23:40:49,573 - INFO - Time offset: 0 seconds
2025-04-05 23:40:49,573 - INFO - Reference ID: 0x966223b0
2025-04-05 23:40:49,573 - INFO - Leap second indicator: 0: no warning
2025-04-05 23:40:49,573 - INFO - Press Ctrl+C to exit
2025-04-05 23:40:49,655 - DEBUG - Received 1 packets
2025-04-05 23:40:49,655 - INFO - Responded to 192.168.100.254:40268
2025-04-05 23:40:55,517 - DEBUG - Received 1 packets
2025-04-05 23:40:55,518 - INFO - Responded to 192.168.100.254:38389
2025-04-05 23:41:01,379 - DEBUG - Received 1 packets
2025-04-05 23:41:01,379 - INFO - Responded to 192.168.100.254:56599
```

Delete a specific NTP server:

`sudo ./ntp_server_namespace_manager delete -i 1`

```
Deleting namespace: py_ntp_ns_1
Stopping Python NTP server with PID 949192 in namespace py_ntp_ns_1
Deleting temporary directory: /tmp/py_ntp_ns_1
Namespace py_ntp_ns_1 deleted.
```

Clean up all NTP servers and resources:

`sudo ./ntp_server_namespace_manager cleanup`

```
Cleaning up all Python2 NTP namespaces and resources
Deleting namespace: py_ntp_ns_1
Stopping Python NTP server with PID 951401 in namespace py_ntp_ns_1
Deleting temporary directory: /tmp/py_ntp_ns_1
Namespace py_ntp_ns_1 deleted.
Deleting namespace: py_ntp_ns_3
Stopping Python NTP server with PID 951235 in namespace py_ntp_ns_3
Deleting temporary directory: /tmp/py_ntp_ns_3
Namespace py_ntp_ns_3 deleted.
Deleting namespace: py_ntp_ns_2
Stopping Python NTP server with PID 950325 in namespace py_ntp_ns_2
Deleting temporary directory: /tmp/py_ntp_ns_2
Namespace py_ntp_ns_2 deleted.
Deleting bridge: br0
Cleaning up temporary directories
All NTP namespaces and resources have been cleaned up.
```

## Readings of twenty servers created with a 3600s offset

```
MS Name/IP address         Stratum Poll Reach LastRx Last sample               
===============================================================================
^? time2.google.com              1  10   377     1   +81.0s[ +81.0s] +/-   18ms
^? 192.168.100.1                 2   1   337     5   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.2                 2   1    37     3   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.3                 2   1   337     3   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.4                 2   1   337     2   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.5                 2   1   337     5   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.6                 2   1   277     0   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.7                 2   1   337     5   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.8                 2   1   337     3   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.9                 2   1   317     4   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.10                2   1   237     1   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.11                2   1   337     1   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.12                2   1   237     1   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.13                2   1   317     5   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.14                2   1   317     3   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.15                2   1   337     1   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.16                2   1   317     5   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.17                2   1   237     0   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.18                2   1   317     2   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.19                2   1   307     4   -3600s[ -3600s] +/- 1500ms
^? 192.168.100.20                2   1   217     0   -3600s[ -3600s] +/- 1500ms
```

## NTP Server Options

The Python NTP server supports the following options:

- `--ip`: IP address to bind to (default: 0.0.0.0)
- `--port`: Port to bind to (default: 123)
- `--ref_id`: Reference ID (4-byte integer, can use hex with 0x prefix)
- `--offset`: Time offset in seconds (default: 0)
- `--stratum`: NTP stratum level (default: 2)
- `--leap`: Leap second indicator (default: 0)
- `--log_level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Credits

- Forked from https://github.com/limifly/ntpserver
- Based on ntplib https://pypi.python.org/pypi/ntplib/
