"""
mavlink_connection.py
Manages a persistent MAVLink connection over the SiK telemetry radio.
Runs a background thread to read WIND messages from ArduRover and exposes
the latest data thread-safely via get_data().
Also supports uploading mission waypoints to the Pixhawk via the MAVLink
mission upload protocol.
"""

import math
import threading
import time
import logging
from typing import Optional, Dict, Any, List
from pymavlink import mavutil

logger = logging.getLogger(__name__)

SERIAL_PORT = "/dev/cu.usbserial-DN05YS5Z"
BAUD_RATE = 57600
MS_TO_KNOTS = 1.94384

# ArduRover MAVLink message IDs
MAVLINK_MSG_ID_WIND = 168
MAVLINK_MSG_ID_GLOBAL_POSITION_INT = 33

# GPS fix considered stale after this many seconds without a new message
GPS_STALE_TIMEOUT = 5.0


class MAVLinkConnection:
    def __init__(self):
        self._connection: Optional[mavutil.mavfile] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._upload_paused = threading.Event()
        self._gps_last_update: Optional[float] = None
        self._data: Dict[str, Any] = {
            "connected": False,
            "wind_speed_knots": None,
            "wind_direction_deg": None,
            "timestamp": None,
            "current_waypoint_seq": None,
            "mission_count": None,
            "gps_lat": None,
            "gps_lon": None,
            "gps_alt_m": None,
            "gps_heading_deg": None,
            "gps_speed_knots": None,
        }

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def start(self) -> bool:
        """Connect and start the background reader thread."""
        if not self._connect():
            return False
        self._running = True
        self._thread = threading.Thread(
            target=self._read_loop, daemon=True, name="mavlink-reader"
        )
        self._thread.start()
        return True

    def stop(self):
        """Stop the reader and close the connection."""
        self._running = False
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
        with self._lock:
            self._data["connected"] = False

    def get_data(self) -> Dict[str, Any]:
        """Return a snapshot of the latest telemetry (thread-safe)."""
        with self._lock:
            data = dict(self._data)
            last_update = self._gps_last_update
        # gps_fix is derived at read-time so it reflects real staleness
        if last_update is not None:
            data["gps_fix"] = (time.time() - last_update) < GPS_STALE_TIMEOUT
        else:
            data["gps_fix"] = False
        return data

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _connect(self) -> bool:
        try:
            logger.info("Connecting to %s at %d baud...", SERIAL_PORT, BAUD_RATE)
            self._connection = mavutil.mavlink_connection(
                SERIAL_PORT,
                baud=BAUD_RATE,
                source_system=255,
            )
            logger.info("Waiting for heartbeat (timeout 15 s)...")
            hb = self._connection.wait_heartbeat(timeout=15)
            if hb is None:
                logger.error("No heartbeat received — check radio link and Pixhawk power.")
                return False

            logger.info(
                "Heartbeat from system %d, component %d.",
                self._connection.target_system,
                self._connection.target_component,
            )

            # Request WIND messages at 4 Hz using the targeted MAVLink v2 command
            self._connection.mav.command_long_send(
                self._connection.target_system,
                self._connection.target_component,
                mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                0,                      # confirmation
                MAVLINK_MSG_ID_WIND,    # message ID
                250_000,                # interval in microseconds (4 Hz)
                0, 0, 0, 0, 0,
            )

            # Also request the EXTRA1 stream as a fallback for older firmwares
            self._connection.mav.request_data_stream_send(
                self._connection.target_system,
                self._connection.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_EXTRA1,
                4,  # 4 Hz
                1,  # start
            )

            # Request GLOBAL_POSITION_INT at 4 Hz for live GPS
            self._connection.mav.command_long_send(
                self._connection.target_system,
                self._connection.target_component,
                mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                0,
                MAVLINK_MSG_ID_GLOBAL_POSITION_INT,
                250_000,  # interval in microseconds (4 Hz)
                0, 0, 0, 0, 0,
            )

            # Also request the POSITION stream as fallback
            self._connection.mav.request_data_stream_send(
                self._connection.target_system,
                self._connection.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_POSITION,
                4,  # 4 Hz
                1,  # start
            )

            with self._lock:
                self._data["connected"] = True
            return True

        except Exception as exc:
            logger.error("Connection failed: %s", exc)
            return False

    def upload_mission(self, waypoints: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Upload mission waypoints to ArduRover via the MAVLink mission protocol.
        Pauses the background read loop during transfer so it doesn't consume
        the MISSION_REQUEST / MISSION_ACK messages we need.

        waypoints: list of dicts with keys latitude, longitude, altitude,
                   command, frame, param1-4, autocontinue (matching DB schema).
        Returns {'success': bool, 'message': str}.
        """
        if not self._connection:
            return {"success": False, "message": "Not connected to Pixhawk"}

        count = len(waypoints)
        if count == 0:
            return {"success": False, "message": "No waypoints to upload"}

        # Signal the read loop to yield, then wait briefly for it to do so
        self._upload_paused.set()
        time.sleep(0.15)

        try:
            target_sys = self._connection.target_system
            target_comp = self._connection.target_component

            logger.info("Uploading %d waypoints to system %d...", count, target_sys)
            self._connection.mav.mission_count_send(target_sys, target_comp, count)

            while True:
                msg = self._connection.recv_match(
                    type=["MISSION_REQUEST", "MISSION_REQUEST_INT", "MISSION_ACK"],
                    blocking=True,
                    timeout=5.0,
                )
                if msg is None:
                    return {"success": False, "message": "Timeout waiting for Pixhawk response"}

                msg_type = msg.get_type()

                if msg_type == "MISSION_ACK":
                    if msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                        logger.info("Mission upload accepted by Pixhawk.")
                        with self._lock:
                            self._data["mission_count"] = count
                        return {"success": True, "message": f"Uploaded {count} waypoints successfully"}
                    else:
                        return {"success": False, "message": f"Mission upload rejected by Pixhawk (code {msg.type})"}

                if msg_type in ("MISSION_REQUEST", "MISSION_REQUEST_INT"):
                    seq = msg.seq
                    if seq >= count:
                        return {
                            "success": False,
                            "message": f"Pixhawk requested seq {seq} but only {count} waypoints exist",
                        }

                    wp = waypoints[seq]
                    # Waypoint 0 is always home — must use absolute frame (MAV_FRAME_GLOBAL = 0)
                    is_home = seq == 0
                    frame = 0 if is_home else int(wp.get("frame", 3))

                    self._connection.mav.mission_item_int_send(
                        target_sys,
                        target_comp,
                        seq,
                        frame,
                        int(wp.get("command", 16)),
                        1 if is_home else 0,        # current (1 = home)
                        int(wp.get("autocontinue", 1)),
                        float(wp.get("param1", 0.0)),
                        float(wp.get("param2", 2.0)),
                        float(wp.get("param3", 0.0)),
                        float(wp.get("param4", 0.0)),
                        int(float(wp["latitude"]) * 1e7),
                        int(float(wp["longitude"]) * 1e7),
                        float(wp.get("altitude", 0.0)),
                        mavutil.mavlink.MAV_MISSION_TYPE_MISSION,
                    )
                    logger.debug("Sent MISSION_ITEM_INT seq=%d", seq)

        except Exception as exc:
            logger.error("Mission upload error: %s", exc)
            return {"success": False, "message": f"Upload error: {exc}"}

        finally:
            self._upload_paused.clear()

    def _read_loop(self):
        """Background thread: parse incoming MAVLink messages."""
        while self._running:
            # Yield while a mission upload is in progress
            if self._upload_paused.is_set():
                time.sleep(0.1)
                continue

            if self._connection is None:
                time.sleep(0.5)
                continue
            try:
                msg = self._connection.recv_match(
                    type=["WIND", "HEARTBEAT", "MISSION_CURRENT", "MISSION_ITEM_REACHED",
                          "GLOBAL_POSITION_INT"],
                    blocking=True,
                    timeout=2.0,
                )
                if msg is None:
                    continue

                msg_type = msg.get_type()

                if msg_type == "WIND":
                    with self._lock:
                        self._data.update(
                            {
                                "connected": True,
                                # speed is m/s from the modified firmware; convert to knots
                                "wind_speed_knots": round(msg.speed * MS_TO_KNOTS, 2),
                                # direction: degrees the wind is coming FROM (0 = N)
                                "wind_direction_deg": round(msg.direction % 360, 1),
                                "timestamp": time.time(),
                            }
                        )

                elif msg_type == "HEARTBEAT":
                    with self._lock:
                        self._data["connected"] = True

                elif msg_type == "MISSION_CURRENT":
                    with self._lock:
                        self._data["current_waypoint_seq"] = msg.seq

                elif msg_type == "MISSION_ITEM_REACHED":
                    logger.info("Waypoint seq=%d reached.", msg.seq)

                elif msg_type == "GLOBAL_POSITION_INT":
                    lat = msg.lat / 1e7          # degE7 → decimal degrees
                    lon = msg.lon / 1e7
                    alt = msg.alt / 1000.0        # mm → metres
                    # vx/vy are in cm/s; derive ground speed in knots
                    speed_ms = math.sqrt(msg.vx ** 2 + msg.vy ** 2) / 100.0
                    speed_knots = round(speed_ms * MS_TO_KNOTS, 2)
                    # hdg: 0–35999 cdeg (0.01 deg resolution); 65535 = unknown
                    heading = None if msg.hdg == 65535 else round(msg.hdg / 100.0, 1)
                    with self._lock:
                        self._data["gps_lat"] = round(lat, 7)
                        self._data["gps_lon"] = round(lon, 7)
                        self._data["gps_alt_m"] = round(alt, 1)
                        self._data["gps_speed_knots"] = speed_knots
                        self._data["gps_heading_deg"] = heading
                        self._gps_last_update = time.time()

            except Exception as exc:
                logger.error("Read error: %s", exc)
                time.sleep(0.5)


# Module-level singleton used by the FastAPI app
mavlink_conn = MAVLinkConnection()
