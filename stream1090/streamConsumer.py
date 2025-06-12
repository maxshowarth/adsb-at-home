"""
Stream consumer for ADS-B messages.
Consumes messages from stdin, tracks aircraft states, and outputs complete aircraft to Kafka.
"""
import os
import sys
import time
import argparse
from datetime import datetime
from typing import Optional
from stream1090.adsb_decoder import decode_message
from stream1090.SeenAircraft import SeenAircraft
from loguru import logger


def configure_logging(log_level: Optional[str] = "INFO"):
    """Configure logging for the application.

    Args:
        log_level: The logging level to use. Defaults to INFO.
    """
    # Configure loguru logger
    logger.remove()  # Remove default handler
    logger.add(sys.stderr, level=log_level,
               format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


def consume_ten_ninty_stream(cleanup_interval_seconds: int = 3600):
    """
    Consumes a raw dump1090 TCP stream and processes the messages.

    Args:
        cleanup_interval_seconds: The interval in seconds to cleanup the seen aircraft. Defaults to 3600.

    Usage:
    nc -u 127.0.0.1 30005 | python streamConsumer.py
    """
    seen_aircraft = SeenAircraft()
    last_cleanup = time.time()
    cleanup_interval = cleanup_interval_seconds

    logger.info("Starting ADS-B stream consumer...")
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

    parser = argparse.ArgumentParser(description='Consume ADS-B stream and track aircraft states')
    parser.add_argument('--log-level', default='INFO',
                       choices=['TRACE', 'DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Set logging level')
    parser.add_argument('--cleanup-interval', type=int, default=3600,
                       help='The interval in seconds to cleanup the seen aircraft. Defaults to 3600.')
    args = parser.parse_args()

    configure_logging(args.log_level)
    logger.info("Starting stream consumer...")
    consume_ten_ninty_stream(args.cleanup_interval)