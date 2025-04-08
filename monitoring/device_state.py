"""Device state tracking for threshold monitoring."""

import time
import threading
from utils.logging import get_logger

logger = get_logger(__name__)


class DeviceStateManager:
    """
    Manages the state of devices and sensors for threshold monitoring.

    Tracks whether sensor values exceed yellow or orange thresholds
    and for how long they've been in that state.
    """

    def __init__(self):
        self.states = {}  # Main state dictionary
        self.last_access = {}  # Last access timestamps for cleanup
        self.lock = threading.Lock()

        # Start cleanup thread
        self._start_cleanup_thread()

    def get_sensor_state(self, device_id, sensor_id):
        """
        Get the current state for a device/sensor combination.

        Args:
            device_id: Device identifier
            sensor_id: Sensor identifier

        Returns:
            dict: Current state for the sensor
        """
        with self.lock:
            # Initialize device state if needed
            if device_id not in self.states:
                self.states[device_id] = {}
                self.last_access[device_id] = time.time()

            # Initialize sensor state if needed
            if sensor_id not in self.states[device_id]:
                self.states[device_id][sensor_id] = {
                    "yellow": {
                        "above_threshold": False,
                        "since_timestamp": None,
                        "breach": None,
                    },
                    "orange": {
                        "above_threshold": False,
                        "since_timestamp": None,
                        "breach": None,
                    },
                }

            self.last_access[device_id] = time.time()
            return self.states[device_id][sensor_id]

    def update_sensor_state(
        self, device_id, sensor_id, threshold_type, is_above_threshold, breach=None
    ):
        """
        Update the state for a device/sensor/threshold combination.

        Args:
            device_id: Device identifier
            sensor_id: Sensor identifier
            threshold_type: Type of threshold (yellow, orange)
            is_above_threshold: Whether the value exceeds the threshold
            breach: Breach data to store if threshold is newly exceeded

        Returns:
            dict: Updated state
        """
        threshold_type = threshold_type.lower()
        if threshold_type not in ("yellow", "orange"):
            raise ValueError(f"Invalid threshold type: {threshold_type}")

        sensor_state = self.get_sensor_state(device_id, sensor_id)
        current_time = time.time()

        with self.lock:
            state = sensor_state[threshold_type]

            if is_above_threshold:
                if not state["above_threshold"]:
                    # First time exceeding threshold
                    state["above_threshold"] = True
                    state["since_timestamp"] = current_time
                    state["breach"] = breach
            else:
                # Reset state
                state["above_threshold"] = False
                state["since_timestamp"] = None
                state["breach"] = None

        return sensor_state

    def check_sustained_breach(
        self, device_id, sensor_id, threshold_type, required_duration
    ):
        """
        Check if a threshold has been exceeded for the required duration.

        Args:
            device_id: Device identifier
            sensor_id: Sensor identifier
            threshold_type: Type of threshold (yellow, orange)
            required_duration: Required duration in seconds

        Returns:
            tuple: (is_sustained_breach, breach_data)
        """
        threshold_type = threshold_type.lower()
        sensor_state = self.get_sensor_state(device_id, sensor_id)
        current_time = time.time()

        with self.lock:
            state = sensor_state[threshold_type]

            if (
                state["above_threshold"]
                and state["since_timestamp"] is not None
                and current_time - state["since_timestamp"] >= required_duration
            ):

                # Reset the state to avoid repeated notifications
                breach = state["breach"]
                state["above_threshold"] = False
                state["since_timestamp"] = None
                state["breach"] = None

                return True, breach

        return False, None

    def _start_cleanup_thread(self, max_age_seconds=3600, cleanup_interval=1800):
        """Start a background thread that periodically removes stale device states.

        Args:
            max_age_seconds (int): Maximum age (in seconds) a state can be idle before removal.
            cleanup_interval (int): Interval (in seconds) between cleanup runs.
        """

        def cleanup_job():
            while True:
                try:
                    current_time = time.time()
                    with self.lock:
                        for device_id in list(self.last_access.keys()):
                            if (
                                current_time - self.last_access[device_id]
                                > max_age_seconds
                            ):
        # Remove the device state if it exists and its last access timestamp.
                                if device_id in self.states:
                                    del self.states[device_id]
                                del self.last_access[device_id]
                    time.sleep(cleanup_interval)
                except Exception as e:
                    logger.error(f"Error in device state cleanup: {e}")

        cleanup_thread = threading.Thread(target=cleanup_job, daemon=True)
        cleanup_thread.start()
