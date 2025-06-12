"""
Class for tracking seen aircraft and updating their states.
"""
from typing import Dict, Optional
from datetime import datetime, timezone
from AircraftState import AircraftState
from loguru import logger

class SeenAircraft:
    """Tracks all seen aircraft and updates their states based on decoded messages."""

    def __init__(self):
        self.aircraft: Dict[str, AircraftState] = {}
        self.cleanup_threshold_seconds = 300  # Remove aircraft not seen for 5 minutes

    def update_from_decoded_message(self, decoded_msg: dict) -> Optional[AircraftState]:
        """Update aircraft state from a decoded message.

        Args:
            decoded_msg: Decoded message dict from decode_message()

        Returns:
            AircraftState: Updated aircraft state, or None if message invalid
        """
        if not decoded_msg or "icao" not in decoded_msg:
            return None

        icao = decoded_msg["icao"]

        # Get or create aircraft state
        if icao not in self.aircraft:
            self.aircraft[icao] = AircraftState(icao)

        aircraft = self.aircraft[icao]
        msg_type = decoded_msg.get("msg_type")
        data = decoded_msg.get("data", {})

        logger.debug(f"[{icao}]: Processing {msg_type} message with data: {data}")

        # Update based on message type - use property setters to trigger timestamp updates
        if msg_type == "identity" and "callsign" in data:
            old_callsign = aircraft.callsign
            aircraft.callsign = data["callsign"]  # This triggers the setter and _update_timestamp
            logger.debug(f"[{icao}]: Callsign update: {old_callsign} -> {aircraft.callsign}")

        elif msg_type in ["position", "position_gnss", "surface_position"]:
            # Handle all position message types
            raw_msg = decoded_msg.get("msg")
            altitude = data.get("altitude")
            cpr_odd_flag = data.get("cpr_odd_flag", False)

            logger.debug(f"[{icao}]: {msg_type} - alt={altitude}, cpr_odd={cpr_odd_flag}, has_raw_msg={raw_msg is not None}")

            if raw_msg:
                # Delegate to AircraftState to handle position updates and CPR decoding
                if msg_type in ["position", "position_gnss"]:
                    # Airborne position - use CPR decoding
                    success = aircraft.update_position_from_message(raw_msg, altitude, cpr_odd_flag)
                    logger.debug(f"[{icao}]: CPR decoding {'succeeded' if success else 'failed/incomplete'}")
                else:
                    # Surface position - just update altitude if available
                    if altitude is not None:
                        aircraft._alt = altitude
                        aircraft._update_timestamp()
                        logger.debug(f"[{icao}]: Surface altitude update: -> {aircraft.alt}")
                    else:
                        aircraft._update_timestamp()
            else:
                # No raw message but still count it
                aircraft._update_timestamp()
                logger.debug(f"[{icao}]: Position message without raw data")

        elif msg_type == "velocity":
            logger.debug(f"[{icao}]: Velocity message")
            if "speed" in data:
                old_speed = aircraft.speed
                aircraft.speed = data["speed"]  # Use property setter
                logger.debug(f"[{icao}]: Speed update: {old_speed} -> {aircraft.speed}")
            if "heading" in data:
                old_heading = aircraft.heading
                aircraft.heading = data["heading"]  # Use property setter
                logger.debug(f"[{icao}]: Heading update: {old_heading} -> {aircraft.heading}")
            if "vertical_rate" in data:
                old_vr = aircraft.vertical_rate
                aircraft.vertical_rate = data["vertical_rate"]  # Use property setter
                logger.debug(f"[{icao}]: Vertical rate update: {old_vr} -> {aircraft.vertical_rate}")
            if "velocity_type" in data:
                old_vt = aircraft.velocity_type
                aircraft.velocity_type = data["velocity_type"]  # Use property setter
                logger.debug(f"[{icao}]: Velocity type update: {old_vt} -> {aircraft.velocity_type}")

            # If no velocity data, still count the message
            if not any(k in data for k in ["speed", "heading", "vertical_rate", "velocity_type"]):
                aircraft._update_timestamp()

        elif msg_type in ["surveillance_alt", "commb_alt", "short_acas", "long_acas"]:
            # Surveillance messages with altitude
            logger.debug(f"[{icao}]: {msg_type} message")
            if "altitude" in data and data["altitude"] is not None:
                old_alt = aircraft.alt
                aircraft._alt = data["altitude"]
                aircraft._update_timestamp()
                logger.debug(f"[{icao}]: Surveillance altitude update: {old_alt} -> {aircraft.alt}")
            else:
                aircraft._update_timestamp()
                logger.debug(f"[{icao}]: {msg_type} without altitude")

        elif msg_type == "surveillance_identity":
            # DF=5 surveillance identity reply with squawk code
            logger.debug(f"[{icao}]: {msg_type} message")
            if "squawk" in data and data["squawk"] is not None:
                logger.debug(f"[{icao}]: Squawk code: {data['squawk']}")
            aircraft._update_timestamp()

        elif msg_type in ["status", "target_state", "operation_status", "all_call", "adsb_other", "unknown_df"]:
            # Other message types - still count them
            logger.debug(f"[{icao}]: {msg_type} message with data: {data}")
            aircraft._update_timestamp()

        else:
            # Completely unknown message type - but still count it!
            logger.warning(f"[{icao}]: UNKNOWN message type: {msg_type} with data: {data}")
            aircraft._update_timestamp()

        # Show completion status
        complete_status = aircraft.is_complete()
        logger.debug(f"[{icao}]: Complete: {complete_status}, Message count: {aircraft.message_count}")

        # Return aircraft if it's complete
        return aircraft if aircraft.is_complete() else None

    def get_complete_aircraft(self) -> Dict[str, AircraftState]:
        """Get all aircraft with complete data.

        Returns:
            Dict[str, AircraftState]: ICAO -> AircraftState for complete aircraft
        """
        return {icao: aircraft for icao, aircraft in self.aircraft.items()
                if aircraft.is_complete()}

    def cleanup_old_aircraft(self):
        """Remove aircraft that haven't been seen recently."""
        now = datetime.now(timezone.utc)
        to_remove = []

        for icao, aircraft in self.aircraft.items():
            time_since_last_seen = (now - aircraft.last_seen).total_seconds()
            if time_since_last_seen > self.cleanup_threshold_seconds:
                to_remove.append(icao)

        for icao in to_remove:
            del self.aircraft[icao]

    def get_aircraft_count(self) -> int:
        """Get total number of tracked aircraft."""
        return len(self.aircraft)

    def get_complete_aircraft_count(self) -> int:
        """Get number of aircraft with complete data."""
        return len(self.get_complete_aircraft())