"""An object that represents the state of an aircraft.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple
import pyModeS as pms

class AircraftState:
    """Stores the identity, position, and velocity of an aircraft.

    Can be initialized with minimal data (just ICAO) and updated
    as more information arrives from different ADS-B message types.
    """

    def __init__(self, icao: str, callsign: Optional[str] = None):
        self.icao = icao
        self._callsign = callsign
        self._lat: Optional[float] = None
        self._lon: Optional[float] = None
        self._alt: Optional[int] = None
        self._speed: Optional[float] = None
        self._heading: Optional[float] = None
        self._vertical_rate: Optional[float] = None
        self._velocity_type: Optional[str] = None

        # CPR frame storage for position decoding
        self._cpr_even_frame: Optional[str] = None
        self._cpr_odd_frame: Optional[str] = None
        self._cpr_even_timestamp: Optional[datetime] = None
        self._cpr_odd_timestamp: Optional[datetime] = None

        # Simple timestamp tracking
        self.first_seen = datetime.now(timezone.utc)
        self.last_seen = datetime.now(timezone.utc)
        self.message_count = 1

    def _update_timestamp(self):
        """Helper method to update timestamp and message count"""
        self.last_seen = datetime.now(timezone.utc)
        self.message_count += 1

    def update_position_from_message(self, raw_msg: str, altitude: Optional[int], cpr_odd_flag: bool) -> bool:
        """Update position from a position message with CPR decoding.

        Args:
            raw_msg: Raw ADS-B message hex string
            altitude: Altitude from message (if available)
            cpr_odd_flag: Whether this is an odd CPR frame

        Returns:
            bool: True if lat/lon was successfully decoded, False otherwise
        """
        # Always update altitude if provided
        if altitude is not None:
            self._alt = altitude

        # Always count this as a processed message
        self._update_timestamp()

        # Handle CPR frame storage and decoding
        current_time = datetime.now(timezone.utc)

        if cpr_odd_flag:
            self._cpr_odd_frame = raw_msg
            self._cpr_odd_timestamp = current_time
        else:
            self._cpr_even_frame = raw_msg
            self._cpr_even_timestamp = current_time

        # Attempt CPR decoding if we have both frames
        if self._cpr_even_frame and self._cpr_odd_frame:
            time_diff = abs((self._cpr_even_timestamp - self._cpr_odd_timestamp).total_seconds())
            if time_diff < 10:
                try:
                    lat_lon = pms.adsb.airborne_position(
                        self._cpr_even_frame,
                        self._cpr_odd_frame,
                        self._cpr_even_timestamp.timestamp(),
                        self._cpr_odd_timestamp.timestamp()
                    )

                    if lat_lon:
                        lat, lon = lat_lon
                        self._lat = lat
                        self._lon = lon
                        return True
                except Exception:
                    # CPR decoding failed, but don't crash
                    pass

        return False

    @property
    def callsign(self) -> Optional[str]:
        return self._callsign

    @callsign.setter
    def callsign(self, value: Optional[str]):
        if value:  # Only update if value is not None/empty
            self._callsign = value
            self._update_timestamp()

    @property
    def lat(self) -> Optional[float]:
        return self._lat

    @property
    def lon(self) -> Optional[float]:
        return self._lon

    @property
    def alt(self) -> Optional[int]:
        return self._alt

    @property
    def speed(self) -> Optional[float]:
        return self._speed

    @speed.setter
    def speed(self, value: Optional[float]):
        self._speed = value
        self._update_timestamp()

    @property
    def heading(self) -> Optional[float]:
        return self._heading

    @heading.setter
    def heading(self, value: Optional[float]):
        self._heading = value
        self._update_timestamp()

    @property
    def vertical_rate(self) -> Optional[float]:
        return self._vertical_rate

    @vertical_rate.setter
    def vertical_rate(self, value: Optional[float]):
        self._vertical_rate = value
        self._update_timestamp()

    @property
    def velocity_type(self) -> Optional[str]:
        return self._velocity_type

    @velocity_type.setter
    def velocity_type(self, value: Optional[str]):
        self._velocity_type = value
        self._update_timestamp()

    def is_complete(self) -> bool:
        """Check if aircraft state has all essential data for Kafka publishing.

        Returns:
            bool: True if has callsign, position (lat/lon/alt), and velocity data
        """
        has_identity = self.callsign is not None
        has_position = all([self.lat is not None, self.lon is not None, self.alt is not None])
        has_velocity = all([self.speed is not None, self.heading is not None, self.vertical_rate is not None])

        return has_identity and has_position and has_velocity

    def to_dict(self) -> dict:
        """Convert to dictionary format suitable for Kafka message"""
        return {
            "icao": self.icao,
            "timestamp": self.last_seen.isoformat() + "Z",
            "callsign": self.callsign,
            "position": {
                "latitude": self.lat,
                "longitude": self.lon,
                "altitude_ft": self.alt
            } if any([self.lat, self.lon, self.alt]) else None,
            "velocity": {
                "ground_speed_kts": self.speed,
                "heading_deg": self.heading,
                "vertical_rate_fpm": self.vertical_rate,
                "velocity_type": self.velocity_type
            } if any([self.speed, self.heading, self.vertical_rate, self.velocity_type]) else None,
            "metadata": {
                "first_seen": self.first_seen.isoformat() + "Z",
                "last_seen": self.last_seen.isoformat() + "Z",
                "message_count": self.message_count
            }
        }

    def touch(self):
        """Public method to update last seen timestamp and increment message count."""
        self._update_timestamp()
