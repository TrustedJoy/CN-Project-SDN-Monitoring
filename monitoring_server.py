import json
import os
import socket
import time
from datetime import datetime

HOST = "10.0.0.1"
PORT = 9999
TELEMETRY_FILE = "/tmp/sdn_telemetry.json"

previous = {}
latest = {}

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((HOST, PORT))
server.settimeout(1.0)

def save_telemetry():
    temporary = TELEMETRY_FILE + ".tmp"
    with open(temporary, "w") as f:
        json.dump(latest, f)
    os.replace(temporary, TELEMETRY_FILE)

print(f"Monitoring server listening on {HOST}:{PORT}")

try:
    while True:
        try:
            data, address = server.recvfrom(4096)
            message = json.loads(data.decode())

            host = message["host"]
            source_ip = address[0]
            now = time.time()
            total = (
                int(message["bytes_sent"])
                + int(message["bytes_received"])
            )

            rate = 0.0
            if host in previous:
                old_total, old_time = previous[host]
                elapsed = now - old_time
                if elapsed > 0:
                    rate = max(0, total - old_total) * 8 / elapsed / 1e6

            previous[host] = (total, now)
            latest[source_ip] = {
                "host": host,
                "source_ip": source_ip,
                "timestamp": now,
                "bytes_sent": int(message["bytes_sent"]),
                "bytes_received": int(message["bytes_received"]),
                "telemetry_rate_mbps": rate,
            }

            save_telemetry()

            print(
                f"{datetime.now():%H:%M:%S} | {host} "
                f"({source_ip}) | {rate:.3f} Mbps"
            )

        except socket.timeout:
            continue
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            print(f"Invalid telemetry: {e}")

except KeyboardInterrupt:
    print("\nMonitoring server stopped.")
finally:
    server.close()
