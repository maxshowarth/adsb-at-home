"""
Utility for decoding hex-encoded ADS-B messages.

Usage:
    python adsbDecoder.py <hex-encoded-message>
    python adsbDecoder.py --stream  # consume from stdin
"""

import sys
import argparse
import pyModeS as pms
from bitstring import BitArray

def decode_message(msg):
    """Decode a single ADS-B message and return decoded data as JSON.

    Args:
        msg (str): The hex-encoded ADS-B message.

    Returns:
        dict: Decoded message data, or None if decoding fails
    """

    if msg.startswith("*"):
        msg = msg[1:]
    if msg.endswith(";"):
        msg = msg[:-1]

    try:
        df = pms.df(msg)
        icao = pms.icao(msg)

        result = {
            "msg": msg,
            "df": df,
            "icao": icao,
            "msg_type": None,
            "data": {}
        }

        # Handle different DF (Downlink Format) types
        if df == 17 or df == 18:  # ADS-B messages
            tc = pms.typecode(msg)
            result["typecode"] = tc

            if 1 <= tc <= 4:
                # Aircraft identification
                result["msg_type"] = "identity"
                callsign = pms.adsb.callsign(msg)
                if callsign:
                    result["data"]["callsign"] = callsign.strip()

            elif 5 <= tc <= 8:
                # Surface position
                result["msg_type"] = "surface_position"
                result["data"]["cpr_odd_flag"] = pms.adsb.oe_flag(msg)
                result["data"]["cpr_frame_type"] = "odd" if result["data"]["cpr_odd_flag"] else "even"
                # TODO: Add surface movement and ground track if available

            elif 9 <= tc <= 18:
                # Airborne position (barometric altitude)
                result["msg_type"] = "position"
                altitude = pms.adsb.altitude(msg)
                if altitude is not None:
                    result["data"]["altitude"] = altitude
                result["data"]["cpr_odd_flag"] = pms.adsb.oe_flag(msg)
                result["data"]["cpr_frame_type"] = "odd" if result["data"]["cpr_odd_flag"] else "even"

            elif tc == 19:
                # Airborne velocities
                result["msg_type"] = "velocity"
                velocity = pms.adsb.velocity(msg)
                if velocity and len(velocity) >= 3:
                    speed, heading, vertical_rate = velocity[0], velocity[1], velocity[2]
                    if speed is not None:
                        result["data"]["speed"] = speed
                    if heading is not None:
                        result["data"]["heading"] = heading
                    if vertical_rate is not None:
                        result["data"]["vertical_rate"] = vertical_rate
                    if len(velocity) >= 4 and velocity[3]:
                        result["data"]["velocity_type"] = velocity[3]

            elif 20 <= tc <= 22:
                # Airborne position (GNSS height)
                result["msg_type"] = "position_gnss"
                altitude = pms.adsb.altitude(msg)
                if altitude is not None:
                    result["data"]["altitude"] = altitude
                result["data"]["cpr_odd_flag"] = pms.adsb.oe_flag(msg)
                result["data"]["cpr_frame_type"] = "odd" if result["data"]["cpr_odd_flag"] else "even"

            elif tc == 28:
                # Aircraft status
                result["msg_type"] = "status"
                # Try to extract emergency data if API exists
                try:
                    result["data"]["emergency_state"] = pms.adsb.emergency_state(msg)
                except AttributeError:
                    pass
                try:
                    result["data"]["emergency_squawk"] = pms.adsb.emergency_squawk(msg)
                except AttributeError:
                    pass

            elif tc == 29:
                # Target state and status info
                result["msg_type"] = "target_state"
                # Extract target state data if available

            elif tc == 31:
                # Aircraft operation status
                result["msg_type"] = "operation_status"
                # Extract operational status if available

            else:
                result["msg_type"] = "adsb_other"
                result["data"]["typecode"] = tc

        elif df == 0:
            # Short air-air surveillance
            result["msg_type"] = "short_acas"
            result["data"]["altitude"] = pms.common.altcode(msg)

        elif df == 4 or df == 5:
            # Surveillance altitude reply
            result["msg_type"] = "surveillance_alt"
            # altcode() only supports DF 0, 4, 16, 20 - not DF 5
            if df == 4:
                try:
                    result["data"]["altitude"] = pms.common.altcode(msg)
                except Exception:
                    pass
            elif df == 5:
                # DF=5 is surveillance identity reply - different format
                result["msg_type"] = "surveillance_identity"
                try:
                    result["data"]["squawk"] = pms.common.idcode(msg)
                except Exception:
                    pass

        elif df == 11:
            # All-call reply
            result["msg_type"] = "all_call"

        elif df == 16:
            # Long air-air surveillance
            result["msg_type"] = "long_acas"
            result["data"]["altitude"] = pms.common.altcode(msg)

        elif df == 20 or df == 21:
            # Comm-B altitude reply
            result["msg_type"] = "commb_alt"
            result["data"]["altitude"] = pms.common.altcode(msg)

        else:
            # Unknown DF type
            result["msg_type"] = "unknown_df"
            result["data"]["df"] = df

        return result

    except Exception as e:
        # Try to extract DF for better error reporting
        try:
            df = pms.df(msg)
            return {"error": f"Error decoding message {msg} (DF={df}): {e}"}
        except:
            return {"error": f"Error decoding message {msg}: {e}"}

def main():
    parser = argparse.ArgumentParser(description='Decode ADS-B messages')
    parser.add_argument('message', nargs='?', help='Hex-encoded ADS-B message to decode')
    parser.add_argument('--stream', action='store_true', help='Consume messages from stdin')

    args = parser.parse_args()

    if args.stream:
        # Stream mode - consume from stdin
        for line in sys.stdin:
            line = line.strip()
            if not line or not line.startswith("*"):
                continue
            try:
                decoded = decode_message(line)
                if decoded:
                    print(decoded)
            except Exception as e:
                print(f"Error decoding line: {line} | {e}", file=sys.stderr)

    elif args.message:
        # Single message mode
        decoded = decode_message(args.message)
        if decoded:
            print(decoded)
        else:
            print("Failed to decode message", file=sys.stderr)
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
