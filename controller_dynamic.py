
import json
import os
import time

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import (
    CONFIG_DISPATCHER,
    MAIN_DISPATCHER,
    DEAD_DISPATCHER,
    set_ev_cls,
)
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib import hub
from os_ken.lib.packet import (
    packet,
    ethernet,
    ether_types,
    ipv4,
)


class DynamicMonitorController(app_manager.OSKenApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # Example thresholds for the college demonstration.
    THRESHOLD_MBPS = 1.0
    BLOCK_SECONDS = 30
    MONITOR_INTERVAL = 5
    TELEMETRY_MAX_AGE = 10

    TELEMETRY_FILE = "/tmp/sdn_telemetry.json"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.datapaths = {}
        self.mac_to_port = {}
        self.mac_to_ip = {}

        # (switch, source MAC, destination MAC, input port)
        # -> (previous byte counter, measurement time)
        self.previous_flow_bytes = {}

        # MAC -> expected block expiry timestamp
        self.blocked_macs = {}

        self.monitor_thread = hub.spawn(self.monitor)

    def add_flow(
        self,
        dp,
        priority,
        match,
        actions=None,
        hard_timeout=0,
    ):
        parser = dp.ofproto_parser
        ofproto = dp.ofproto

        instructions = []

        # No instructions means packets matching this rule
        # are dropped by the switch.
        if actions:
            instructions = [
                parser.OFPInstructionActions(
                    ofproto.OFPIT_APPLY_ACTIONS,
                    actions,
                )
            ]

        mod = parser.OFPFlowMod(
            datapath=dp,
            priority=priority,
            match=match,
            instructions=instructions,
            hard_timeout=hard_timeout,
        )

        dp.send_msg(mod)

    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER,
    )
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        parser = dp.ofproto_parser
        ofproto = dp.ofproto

        # Send unmatched packets to the controller.
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER,
            )
        ]

        self.add_flow(
            dp,
            priority=0,
            match=parser.OFPMatch(),
            actions=actions,
        )

        self.logger.info(
            "Switch %s connected", dp.id
        )

    @set_ev_cls(
        ofp_event.EventOFPStateChange,
        [MAIN_DISPATCHER, DEAD_DISPATCHER],
    )
    def state_change_handler(self, ev):
        dp = ev.datapath

        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dp.id] = dp

        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(dp.id, None)

    @set_ev_cls(
        ofp_event.EventOFPPacketIn,
        MAIN_DISPATCHER,
    )
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        parser = dp.ofproto_parser
        ofproto = dp.ofproto

        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None:
            return

        # Ignore LLDP packets.
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src = eth.src
        dst = eth.dst
        dpid = dp.id

        # Learn the source MAC address and input port.
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        # Associate IPv4 addresses with source MAC addresses.
        ip_pkt = pkt.get_protocol(ipv4.ipv4)

        if ip_pkt:
            self.mac_to_ip.setdefault(dpid, {})
            self.mac_to_ip[dpid][src] = ip_pkt.src

        # Forward to a known destination or flood.
        out_port = self.mac_to_port[dpid].get(
            dst,
            ofproto.OFPP_FLOOD,
        )

        actions = [
            parser.OFPActionOutput(out_port)
        ]

        # Install a forwarding rule for known destinations.
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(
                in_port=in_port,
                eth_src=src,
                eth_dst=dst,
            )

            self.add_flow(
                dp,
                priority=1,
                match=match,
                actions=actions,
            )

        data = None

        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=dp,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )

        dp.send_msg(out)

    def monitor(self):
        while True:
            for dp in list(self.datapaths.values()):
                request = (
                    dp.ofproto_parser.OFPFlowStatsRequest(dp)
                )
                dp.send_msg(request)

            hub.sleep(self.MONITOR_INTERVAL)

    def get_telemetry(self, source_ip):
        """Return a recent telemetry report for an IP."""
        try:
            with open(self.TELEMETRY_FILE, "r") as f:
                telemetry = json.load(f)

            report = telemetry.get(source_ip)

            if not report:
                return None

            age = time.time() - float(report["timestamp"])

            if age > self.TELEMETRY_MAX_AGE or age < 0:
                return None

            return report

        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
        ):
            return None

    @set_ev_cls(
        ofp_event.EventOFPFlowStatsReply,
        MAIN_DISPATCHER,
    )
    def flow_stats_reply_handler(self, ev):
        dp = ev.msg.datapath
        now = time.time()

        bytes_per_mac = {}

        for stat in ev.msg.body:

            # Skip the table-miss rule and other priorities.
            if stat.priority != 1:
                continue

            mac = stat.match.get("eth_src")

            if not mac:
                continue

            key = (
                dp.id,
                mac,
                stat.match.get("eth_dst"),
                stat.match.get("in_port"),
            )

            current_bytes = stat.byte_count
            previous = self.previous_flow_bytes.get(key)

            # The first sample establishes a baseline.
            if previous is None:
                delta = 0
            else:
                old_bytes, old_time = previous

                elapsed = now - old_time

                if current_bytes >= old_bytes:
                    delta = current_bytes - old_bytes
                else:
                    # Counter reset or switch flow replacement.
                    delta = current_bytes

                if elapsed > 0:
                    bytes_per_mac[mac] = (
                        bytes_per_mac.get(mac, 0.0)
                        + delta / elapsed
                    )

            self.previous_flow_bytes[key] = (
                current_bytes,
                now,
            )

        # Evaluate each source using both measurements.
        for mac, bytes_per_second in bytes_per_mac.items():

            flow_mbps = bytes_per_second * 8 / 1_000_000

            self.logger.info(
                "Flow source=%s rate=%.3f Mbps",
                mac,
                flow_mbps,
            )

            if flow_mbps <= self.THRESHOLD_MBPS:
                continue

            # Avoid repeatedly installing the same block.
            if self.blocked_macs.get(mac, 0) > now:
                continue

            source_ip = (
                self.mac_to_ip.get(dp.id, {}).get(mac)
            )

            if not source_ip:
                self.logger.info(
                    "No learned IPv4 address for %s; "
                    "cannot validate telemetry",
                    mac,
                )
                continue

            report = self.get_telemetry(source_ip)

            if report is None:
                self.logger.info(
                    "No recent telemetry for %s; "
                    "not blocking",
                    source_ip,
                )
                continue

            telemetry_mbps = float(
                report["telemetry_rate_mbps"]
            )

            self.logger.info(
                "Telemetry source=%s rate=%.3f Mbps",
                source_ip,
                telemetry_mbps,
            )

            # Both independent measurements must exceed
            # the threshold before triggering the response.
            if telemetry_mbps <= self.THRESHOLD_MBPS:
                self.logger.info(
                    "Telemetry threshold not exceeded for %s",
                    source_ip,
                )
                continue

            # Install a high-priority rule with no actions:
            # matching source-MAC traffic is dropped.
            match = dp.ofproto_parser.OFPMatch(
                eth_src=mac
            )

            self.add_flow(
                dp,
                priority=100,
                match=match,
                actions=[],
                hard_timeout=self.BLOCK_SECONDS,
            )

            self.blocked_macs[mac] = (
                now + self.BLOCK_SECONDS
            )

            self.logger.warning(
                "ALERT: %s (%s) exceeded both thresholds. "
                "Flow=%.3f Mbps, telemetry=%.3f Mbps. "
                "Traffic blocked for up to %s seconds.",
                mac,
                source_ip,
                flow_mbps,
                telemetry_mbps,
                self.BLOCK_SECONDS,
            )
