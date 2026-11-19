# SDN Network Monitoring and Alert System

A Software Defined Networking (SDN) based network monitoring system built using **Mininet, Open vSwitch, OpenFlow 1.3, and OS-Ken**.

The system monitors network traffic, collects host-level telemetry, detects unusually high traffic rates, and automatically blocks traffic from a source MAC address when the configured threshold is exceeded.

## 1. Project Overview

This project implements a simple SDN-based network monitoring and alert system.

It uses two sources of traffic information:

- **OpenFlow flow statistics:** Collected from the Open vSwitch switch by the SDN controller.
- **Host telemetry:** Collected from individual Mininet hosts using a Python telemetry agent and sent to a monitoring server through UDP.

When both measurements exceed the configured traffic threshold, the controller installs a high-priority blocking rule for the source MAC address.

The blocking rule automatically expires after 30 seconds.

## 2. Features

- SDN controller using OS-Ken.
- OpenFlow 1.3 communication.
- MAC address learning and packet forwarding.
- Periodic collection of OpenFlow flow statistics.
- Host-level network traffic monitoring.
- UDP-based telemetry communication.
- JSON-based telemetry storage.
- Traffic rate calculation in Mbps.
- Automatic detection of high traffic.
- Automatic traffic blocking using OpenFlow rules.
- Automatic recovery after the blocking timeout.

## 3. Technologies Used

| Technology | Purpose |
|---|---|
| Python 3 | Implementation of controller and monitoring programs |
| OS-Ken | SDN controller framework |
| Mininet | Network emulation |
| Open vSwitch | Software-defined switch |
| OpenFlow 1.3 | Controller-switch communication protocol |
| iperf3 | Network traffic generation and testing |
| UDP sockets | Host telemetry communication |
| JSON | Telemetry data storage |

## 4. Repository Structure

```text
CN-Project-SDN-Monitoring/
│
├── controller.py
├── controller_dynamic.py
├── monitoring_server.py
├── telemetry_agent.py
├── .gitignore
└── README.md
```

### Description of Python files

| File | Description |
|---|---|
| `controller.py` | Basic SDN controller with MAC learning and packet forwarding. |
| `controller_dynamic.py` | Dynamic SDN controller with flow monitoring, telemetry verification, and automatic blocking. |
| `monitoring_server.py` | Receives telemetry reports from hosts, calculates traffic rates, and saves the latest reports. |
| `telemetry_agent.py` | Collects network interface byte counters and periodically sends telemetry reports to the monitoring server. |

## 5. System Requirements

Recommended operating system:

- Ubuntu 22.04 LTS or Ubuntu 24.04 LTS.
- Linux Mint (Ubuntu-based versions).

Recommended hardware:

- 2 CPU cores.
- 4 GB RAM or more.
- 10 GB available storage.

A Linux environment is required because Mininet and Open vSwitch use Linux networking features.

## 6. Installation

### Step 1: Update the system

```bash
sudo apt update
sudo apt upgrade -y
```

### Step 2: Install Python and development tools

```bash
sudo apt install -y python3 python3-pip python3-venv git build-essential
```

### Step 3: Install Mininet

```bash
sudo apt install -y mininet
```

Verify the installation:

```bash
sudo mn --version
```

### Step 4: Install Open vSwitch

```bash
sudo apt install -y openvswitch-switch
```

Enable and start the service:

```bash
sudo systemctl enable --now openvswitch-switch
```

Check its status:

```bash
sudo systemctl status openvswitch-switch
```

### Step 5: Install iperf3 and networking utilities

```bash
sudo apt install -y iperf3 iproute2 net-tools iputils-ping tcpdump
```

### Step 6: Clone the repository

```bash
git clone https://github.com/TrustedJoy/CN-Project-SDN-Monitoring.git
```

Enter the project directory:

```bash
cd CN-Project-SDN-Monitoring
```

### Step 7: Create a Python virtual environment

```bash
python3 -m venv ~/sdn-venv
```

Activate it:

```bash
source ~/sdn-venv/bin/activate
```

### Step 8: Install OS-Ken

```bash
pip install --upgrade pip
pip install os-ken
```

Verify the installation:

```bash
python -c "import os_ken; print('OS-Ken installed successfully')"
```

**Note:** Activate the virtual environment whenever you want to run the SDN controller.

## 7. Network Topology

The project uses a single-switch Mininet topology with three hosts.

```text
                 SDN Controller
                   (OS-Ken)
                       |
                       |
                 Open vSwitch
                     (s1)
                       |
          +------------+------------+
          |            |            |
         h1           h2           h3
      10.0.0.1     10.0.0.2     10.0.0.3
          |            |            |
      Monitoring   Telemetry    Telemetry
       Server       Agent        Agent
                    + Traffic    + Traffic
                    Source       Destination
```

### Host configuration

| Host | IP Address | Role |
|---|---|---|
| h1 | 10.0.0.1 | Monitoring server |
| h2 | 10.0.0.2 | Telemetry agent and traffic source |
| h3 | 10.0.0.3 | Telemetry agent and traffic destination |
| s1 | — | Open vSwitch switch |

## 8. Running the Project

The following instructions run the dynamic monitoring and alert system.

Open multiple terminal windows so that the controller, Mininet, and monitoring programs can run simultaneously.

### Terminal 1: Start the SDN Controller

Navigate to the repository directory:

```bash
cd ~/CN-Project-SDN-Monitoring
```

Activate the Python virtual environment:

```bash
source ~/sdn-venv/bin/activate
```

Start the dynamic controller:

```bash
osken-manager controller_dynamic.py
```

The controller listens for OpenFlow connections on port 6653.

Keep this terminal running.

### Terminal 2: Start Mininet

Start the Mininet topology:

```bash
sudo mn --topo single,3 --mac --switch ovsk --controller remote,ip=127.0.0.1,port=6653 --protocols OpenFlow13
```

This creates:

- One Open vSwitch switch.
- Three Mininet hosts.
- A remote connection to the OS-Ken controller.
- OpenFlow 1.3 communication.

Check the topology:

```bash
nodes
```

Check network connections:

```bash
net
```

Test connectivity:

```bash
pingall
```

Keep the Mininet CLI running.

### Terminal 3: Start the Monitoring Server

Inside the Mininet CLI, run:

```bash
h1 python3 ~/CN-Project-SDN-Monitoring/monitoring_server.py &
```

The monitoring server listens on:

```text
IP Address: 10.0.0.1
UDP Port: 9999
```

It receives telemetry reports from the other hosts and saves the latest information to:

```text
/tmp/sdn_telemetry.json
```

### Terminal 4: Start the Telemetry Agent on h2

Inside the Mininet CLI, run:

```bash
h2 python3 ~/CN-Project-SDN-Monitoring/telemetry_agent.py h2 10.0.0.1 &
```

This starts the telemetry agent on h2.

It reads network interface counters and sends telemetry reports to h1 every 2 seconds.

### Start the Telemetry Agent on h3

Inside the Mininet CLI, run:

```bash
h3 python3 ~/CN-Project-SDN-Monitoring/telemetry_agent.py h3 10.0.0.1 &
```

This starts the telemetry agent on h3.

The monitoring server should now receive reports from both h2 and h3.

## 9. Testing the System

### Test 1: Check network connectivity

Inside Mininet:

```bash
pingall
```

All hosts should be able to communicate with one another.

### Test 2: Check telemetry reports

From a normal Linux terminal:

```bash
cat /tmp/sdn_telemetry.json
```

To monitor telemetry continuously:

```bash
watch -n 1 cat /tmp/sdn_telemetry.json
```

The file should contain telemetry information for the reporting hosts.

### Test 3: Generate TCP traffic

Inside Mininet, start an iperf3 server on h3:

```bash
h3 iperf3 -s -D
```

Generate TCP traffic from h2:

```bash
h2 iperf3 -c 10.0.0.3 -t 20
```

This generates TCP traffic from h2 to h3 for 20 seconds.

### Test 4: Generate UDP traffic

Start the iperf3 server on h3 if it is not already running:

```bash
h3 iperf3 -s -D
```

Generate UDP traffic from h2:

```bash
h2 iperf3 -c 10.0.0.3 -u -b 5M -t 20
```

This command:

- Uses h2 as the iperf3 client.
- Sends traffic to h3 (10.0.0.3).
- Uses UDP.
- Targets a bandwidth of 5 Mbps.
- Runs for 20 seconds.

### Test 5: Observe traffic detection

Watch the controller terminal.

The controller displays flow and telemetry traffic rates.

Example output:

```text
Flow source=... rate=4.500 Mbps
Telemetry source=10.0.0.2 rate=5.100 Mbps

ALERT: ... exceeded both thresholds.
Traffic blocked for up to 30 seconds.
```

The actual measured rates may differ.

### Test 6: Verify the blocking rule

Open another Linux terminal:

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

Look for a high-priority rule matching the source MAC address.

The blocking rule uses priority 100 and a hard timeout of 30 seconds.

### Test 7: Verify packet blocking

Inside Mininet:

```bash
h2 ping -c 10 10.0.0.3
```

While the blocking rule is active, packets from h2 should be dropped.

### Test 8: Verify recovery

Wait approximately 30 seconds for the blocking rule to expire.

Then run:

```bash
h2 ping -c 5 10.0.0.3
```

Connectivity should be restored after the blocking rule expires.

