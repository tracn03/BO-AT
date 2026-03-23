"""
mavlink_connection.py
Manages a persistent MAVLink connection over the SiK telemetry radio.
Runs a background thread to read WIND messages from ArduRover and exposes
the latest data thread-safely via get_data().
"""

import threading
import time
import logging
from typing import Optional, Dict, Any
from pymavlink import mavutil

logger = logging.getLogger(__name__)

SERIAL_PORT = "/dev/cu.usbserial-DN05YS5Z"
BAUD_RATE = 57600
MS_TO_KNOTS = 1.94384

# ArduRover WIND MAVLink message ID
MAVLINK_MSG_ID_WIND = 168


class MAVLinkConnection:
    def __init__(self):
        self._connection: Optional[mavutil.mavfile] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {
            "connected": False,
            "wind_speed_knots": None,
            "wind_direction_deg": None,
            "timestamp": None,
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
            return dict(self._data)

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

            with self._lock:
                self._data["connected"] = True
            return True

        except Exception as exc:
            logger.error("Connection failed: %s", exc)
            return False

    def _read_loop(self):
        """Background thread: parse incoming MAVLink messages."""
        while self._running:
            if self._connection is None:
                time.sleep(0.5)
                continue
            try:
                msg = self._connection.recv_match(
                    type=["WIND", "HEARTBEAT"],
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

            except Exception as exc:
                logger.error("Read error: %s", exc)
                time.sleep(0.5)


# Module-level singleton used by the FastAPI app
mavlink_conn = MAVLinkConnection()
