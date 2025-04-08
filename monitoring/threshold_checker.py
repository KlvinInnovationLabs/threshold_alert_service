"""Threshold detection logic for sensor readings."""

import time
from config.settings import YELLOW_SUSTENANCE_PERIOD, ORANGE_SUSTENANCE_PERIOD
from utils.db_interface import get_thresholds, get_entity_names
from utils.logging import get_logger
from monitoring.device_state import DeviceStateManager

logger = get_logger(__name__)

# Create a global device state manager
device_state_manager = DeviceStateManager()


def make_breach_object(
    device_id, sensor_reading, timestamp, threshold_type, threshold_value
):
    """
    Create a breach notification object.

    Args:
        device_id: Device identifier
        sensor_reading: Sensor reading data
        timestamp: Timestamp of the reading
        threshold_type: Type of threshold (red, orange, yellow)
        threshold_value: Value of the threshold that was breached

    Returns:
        dict: Breach notification object
    """
    factory_name, zone_name, machine_name = get_entity_names(device_id)

    return {
        "device_id": device_id,
        "sensor_id": sensor_reading["sensor_id"],
        "factory_name": factory_name,
        "zone_name": zone_name,
        "machine_name": machine_name,
        "sensor_name": sensor_reading["sensor_type"],
        "sensor_value": sensor_reading["value"],
        "timestamp": timestamp,
        "threshold_type": threshold_type.lower(),
        "threshold_value": threshold_value,
    }


def check_thresholds_against_data(
    device_id, device_readings, timestamp, critical_queue, warning_queue
):
    """
    Check sensor readings against thresholds and update device states.

    Args:
        device_id: Device identifier
        device_readings: List of sensor readings
        timestamp: Timestamp of the readings
        critical_queue: Queue for critical (red) breaches
        warning_queue: Queue for warning (yellow/orange) breaches
    """
    if not isinstance(device_readings, list):
        device_readings = [device_readings]

    logger.debug(
        f"Checking thresholds for device {device_id}, {len(device_readings)} readings"
    )

    # Process each sensor reading
    for sensor_reading in device_readings:
        sensor_id = sensor_reading["sensor_id"]
        sensor_value = float(sensor_reading["value"])

        # Get thresholds for this device/sensor
        try:
            threshold_yellow, threshold_orange, threshold_red = get_thresholds(
                device_id, sensor_id
            )
        except Exception as e:
            logger.error(f"Failed to get thresholds for {device_id}/{sensor_id}: {e}")
            continue

        # Check red threshold (immediate alert)
        if sensor_value >= threshold_red:
            breach = make_breach_object(
                device_id, sensor_reading, timestamp, "red", threshold_red
            )
            try:
                critical_queue.put(breach, block=False)
                logger.info(
                    f"Red threshold breach detected: {device_id}/{sensor_id}, value={sensor_value}"
                )
            except Exception as e:
                logger.error(f"Failed to queue red breach: {e}")

        # Check orange threshold (sustained monitoring)
        elif sensor_value >= threshold_orange:
            breach = make_breach_object(
                device_id, sensor_reading, timestamp, "orange", threshold_orange
            )
            device_state_manager.update_sensor_state(
                device_id, sensor_id, "orange", True, breach
            )

            # Check if orange threshold has been sustained
            is_sustained, breach = device_state_manager.check_sustained_breach(
                device_id, sensor_id, "orange", ORANGE_SUSTENANCE_PERIOD
            )

            if is_sustained and breach:
                try:
                    warning_queue.put(breach, block=False)
                    logger.info(
                        f"Sustained orange breach detected: {device_id}/{sensor_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to queue orange breach: {e}")

        # Check yellow threshold (sustained monitoring)
        elif sensor_value >= threshold_yellow:
            breach = make_breach_object(
                device_id, sensor_reading, timestamp, "yellow", threshold_yellow
            )
            device_state_manager.update_sensor_state(
                device_id, sensor_id, "yellow", True, breach
            )

            # Check if yellow threshold has been sustained
            is_sustained, breach = device_state_manager.check_sustained_breach(
                device_id, sensor_id, "yellow", YELLOW_SUSTENANCE_PERIOD
            )

            if is_sustained and breach:
                try:
                    warning_queue.put(breach, block=False)
                    logger.info(
                        f"Sustained yellow breach detected: {device_id}/{sensor_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to queue yellow breach: {e}")

        # Below all thresholds
        else:
            # Reset states
            device_state_manager.update_sensor_state(
                device_id, sensor_id, "yellow", False
            )
            device_state_manager.update_sensor_state(
                device_id, sensor_id, "orange", False
            )


def run_threshold_check(data, critical_queue, warning_queue):
    """
    Process device readings and check for threshold breaches.

    Args:
        data: Data from Socket.IO event
        critical_queue: Queue for critical (red) breaches
        warning_queue: Queue for warning (yellow/orange) breaches
    """
    try:
        sensor_data = data.get("readings", [])
        device_id = data.get("device_id")
        timestamp = data.get("time")

        check_thresholds_against_data(
            device_id, sensor_data, timestamp, critical_queue, warning_queue
        )

    except Exception as e:
        logger.error(f"Error in threshold check: {e}")
