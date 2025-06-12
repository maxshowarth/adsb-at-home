"""
Stream consumer for ADS-B messages.
Consumes messages from stdin, tracks aircraft states, and outputs complete aircraft to Kafka.
"""
import sys
import time
import argparse
from datetime import datetime
from stream1090.adsb_decoder import decode_message
from stream1090.SeenAircraft import SeenAircraft
from loguru import logger

def main():
    """Main stream consumption loop."""
    parser = argparse.ArgumentParser(description='Consume ADS-B stream and track aircraft states')
    parser.add_argument('--log-level', default='INFO',
                       choices=['TRACE', 'DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Set logging level')
    args = parser.parse_args()

    # Configure loguru logger
    logger.remove()  # Remove default handler
    logger.add(sys.stderr, level=args.log_level,
               format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

    seen_aircraft = SeenAircraft()
    last_cleanup = time.time()
    cleanup_interval = 60  # Cleanup every minute

    logger.info("Starting ADS-B stream consumer...")
    logger.info(f"Log level set to: {args.log_level}")
    logger.info("Listening for messages on stdin...")

    for line in sys.stdin:
        line = line.strip()
        if not line or not line.startswith("*"):
            continue

        try:
            # Decode the message
            decoded = decode_message(line)
            if not decoded or "error" in decoded:
                if "error" in decoded:
                    logger.error(f"Decode error: {decoded['error']}")
                continue

            # Update aircraft state
            aircraft = seen_aircraft.update_from_decoded_message(decoded)
            if aircraft and aircraft.is_complete():
                # Output complete aircraft to stdout (for Kafka)
                print(aircraft.to_dict())

            # Periodic cleanup of old aircraft
            current_time = time.time()
            if current_time - last_cleanup > cleanup_interval:
                seen_aircraft.cleanup_old_aircraft()
                last_cleanup = current_time

                # Status info
                total_count = seen_aircraft.get_aircraft_count()
                complete_count = seen_aircraft.get_complete_aircraft_count()
                logger.info(f"Aircraft tracked: {total_count}, Complete: {complete_count}")

        except Exception as e:
            logger.error(f"Error processing line: {line} | {e}")

if __name__ == "__main__":
    main()