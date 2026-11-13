import json
import socket
import time
import sys

if len(sys.argv) != 3:
    print("Usage: python3 telemetry_agent.py HOST_NAME SERVER_IP")
    sys.exit(1)

HOST_NAME = sys.argv[1]
SERVER_IP = sys.argv[2]
SERVER_PORT = 9999
INTERVAL = 2

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def read_interface_bytes():
    sent = 0
    received = 0

    with open("/proc/net/dev", "r") as file:
        for line in file:
            if ":" not in line:
                continue

            interface, values = line.split(":", 1)
            interface = interface.strip()

            if interface == "lo":
                continue

            fields = values.split()
            if len(fields) >= 9:
                received += int(fields[0])
                sent += int(fields[8])

    return sent, received

print(f"Telemetry agent {HOST_NAME} -> {SERVER_IP}:{SERVER_PORT}")

try:
    while True:
        sent, received = read_interface_bytes()

        message = {
            "host": HOST_NAME,
            "timestamp": time.time(),
            "bytes_sent": sent,
            "bytes_received": received,
        }

        sock.sendto(
            json.dumps(message).encode(),
            (SERVER_IP, SERVER_PORT)
        )

        print(f"Sent telemetry: tx={sent}, rx={received}")
        time.sleep(INTERVAL)

except KeyboardInterrupt:
    print("\nTelemetry agent stopped.")
finally:
    sock.close()
