from PyQt5.QtCore import pyqtSignal, QThread, QTimer, pyqtSlot
import pygame
import logging
import coloredlogs
import time

coloredlogs.install(level=logging.DEBUG)
logger = logging.getLogger(__name__)

GREEN_TEXT_CSS = "color: green"
RED_TEXT_CSS = "color: red"
RESTING_PULSEWIDTH = 1500.00
DEADZONE_MIN = 0.75
PWM_DEADZONE_MIN = 0.1
ARDUINO_SEND_TIMER_MIN = 0.5

class JoystickThread(QThread):
    joystick_change_signal = pyqtSignal(dict)

    def __init__(self, forward_backward_thrust_label, left_right_thrust_label, vertical_thrust_label, pitch_thrust_label, status_bar, arduino_thread, video_thread):
        super().__init__()
        logger.info("Joystick thread initialized")
        self.__run_flag = True
        self.__joystick = None
        self.__forward_backward_thrust_label = forward_backward_thrust_label
        self.__left_right_thrust_label = left_right_thrust_label
        self.__vertical_thrust_label = vertical_thrust_label
        self.__pitch_thrust_label = pitch_thrust_label
        self.__connection_status_bar = status_bar
        self.__arduino_thread = arduino_thread
        self.__video_thread = video_thread

        self.__last_sent_time = time.time()

        self.claw_pw = 1500  # Neutral hold position for first claw
        self.claw2_pw = 1500  # Neutral hold position for second claw

        pygame.init()

        self._wait_for_joystick_timer = QTimer(self)
        self._wait_for_joystick_timer.timeout.connect(self._wait_for_joystick)

        if pygame.joystick.get_count() == 0:
            logger.warn("No joystick detected! Waiting for joysticks...")
            self._wait_for_joystick_timer.start(1000)  # Check every second
        else:
            self._initialize_joystick()

        self.joystick_change_signal.connect(self.handle_joystick)
        self.start()

        self.__joystick_timer = QTimer(self)
        self.__joystick_timer.timeout.connect(self.check_joystick_input)
        self.__joystick_timer.start(10)

    def stop(self):
        self.__run_flag = False
        self.wait()

    def _wait_for_joystick(self):
        pygame.quit()
        pygame.init()
        if pygame.joystick.get_count() > 0:
            self._initialize_joystick()
            self._wait_for_joystick_timer.stop()

    def _initialize_joystick(self):
        self.__joystick = pygame.joystick.Joystick(0)
        self.__joystick.init()
        logger.info(f"Joystick found! Name: {self.__joystick.get_name()}")
        self.__connection_status_bar.setText(f"Joystick ({self.__joystick.get_name()}) connected")
        self.__connection_status_bar.setStyleSheet(GREEN_TEXT_CSS)

    @pyqtSlot(dict)
    def handle_joystick(self, commands):
        is_joystick_connected = commands.get("connected")
        if not is_joystick_connected:
            logger.warn("Joystick disconnected")
        else:
            pass

    def check_joystick_input(self):
        if self.__joystick is not None and pygame.joystick.get_count() > 0:
            pygame.event.pump()

            # Get values for triggers and bumpers (these remain untouched)
            left_trigger = self.__joystick.get_axis(2) or 0
            right_trigger = self.__joystick.get_axis(5) or 0
            left_bumper = self.__joystick.get_button(4)   # Claw2 close
            right_bumper = self.__joystick.get_button(5)  # Claw2 open

            for event in pygame.event.get():
                if event.type == pygame.JOYBUTTONDOWN and event.button == 3:  # Y button for screenshot
                    self.__video_thread.save_screenshot()

            # === Thruster Axis Mappings ===
            # Horizontal thruster control:
            #   - Common base value from Axis 1.
            #   - Differential control from Axis 0.
            horizontal_base = self.__joystick.get_axis(1) or 0
            h_discrete = self.__joystick.get_axis(0) or 0

            # Vertical (top) thruster control:
            #   - Common base value from Axis 4.
            #   - Differential control from Axis 3.
            vertical_base = self.__joystick.get_axis(4) or 0
            v_discrete = self.__joystick.get_axis(3) or 0

            # Build a dictionary with our axis inputs.
            axis_info = {
                "horizontal": horizontal_base,
                "vertical": vertical_base,
                "h_discrete": h_discrete,
                "v_discrete": v_discrete
            }

            # Calculate thruster pulsewidths using our mapping functions.
            pulsewidths = self.__calculate_pulsewidth(axis_info)
            self.__update_thrust_labels(pulsewidths)

            # Build JSON data for Arduino.
            to_arduino = {
                "axisInfo": [
                    pulsewidths.get("leftthruster"),
                    pulsewidths.get("rightthruster"),
                    pulsewidths.get("topleftthruster"),
                    pulsewidths.get("toprightthruster")
                ],
                "left_trigger": left_trigger,
                "right_trigger": right_trigger
            }

            # # --- Claw Control (Triggers remain unchanged) ---
            # if right_trigger > 0.1:
            #     self.claw_pw = 2100  # Open claw fully
            #     logger.debug(f"Right Trigger Pressed: Claw Opening to {self.claw_pw}")
            # elif left_trigger > 0.1:
            #     self.claw_pw = 1100  # Close claw fully
            #     logger.debug(f"Left Trigger Pressed: Claw Closing to {self.claw_pw}")
            # else:
            #     self.claw_pw = 1500  # Hold position
            #     logger.debug(f"No Trigger Pressed: Claw Holding at {self.claw_pw}")

            # # --- Claw2 Control (Bumpers remain unchanged) ---
            # if right_bumper:
            #     self.claw2_pw = 2100  # Fully open
            #     logger.debug(f"Right Bumper Pressed: Claw2 Opening to {self.claw2_pw}")
            # elif left_bumper:
            #     self.claw2_pw = 1100  # Fully close
            #     logger.debug(f"Left Bumper Pressed: Claw2 Closing to {self.claw2_pw}")
            # else:
            #     self.claw2_pw = 1500  # Hold position
            #     logger.debug(f"No Bumper Pressed: Claw2 Holding at {self.claw2_pw}")

            # to_arduino["claw"] = self.claw_pw
            # to_arduino["claw2"] = self.claw2_pw

            # --- Claw Control (Triggers increment position) ---
            CLAW_STEP = 7  # Adjust this value to fine-tune the step size
            CLAW_STEP_2 = 7

            if right_trigger > 0.1:
                self.claw_pw = min(self.claw_pw + CLAW_STEP, 2100)  # Increment up to max open
                logger.debug(f"Right Trigger Pressed: Claw Opening to {self.claw_pw}")
            elif left_trigger > 0.1:
                self.claw_pw = max(self.claw_pw - CLAW_STEP, 1100)  # Decrement down to fully closed
                logger.debug(f"Left Trigger Pressed: Claw Closing to {self.claw_pw}")

            # --- Claw2 Control (Bumpers increment position) ---
            if right_bumper:
                self.claw2_pw = min(self.claw2_pw + CLAW_STEP_2, 2100)  # Increment up to max open
                logger.debug(f"Right Bumper Pressed: Claw2 Opening to {self.claw2_pw}")
            elif left_bumper:
                self.claw2_pw = max(self.claw2_pw - CLAW_STEP_2, 1100)  # Decrement down to fully closed
                logger.debug(f"Left Bumper Pressed: Claw2 Closing to {self.claw2_pw}")

            # Preserve last claw positions
            to_arduino["claw"] = self.claw_pw
            to_arduino["claw2"] = self.claw2_pw



            current_time = time.time()
            if current_time - self.__last_sent_time > ARDUINO_SEND_TIMER_MIN:
                self.__arduino_thread.handle_data(to_arduino)
                self.__last_sent_time = current_time

            # Emit joystick info signal.
            joystick_info = {
                "connected": "True",
                "joystickName": self.__joystick.get_name(),
                "axisInfo": to_arduino["axisInfo"]
            }
            self.joystick_change_signal.emit(joystick_info)
        else:
            self.joystick_change_signal.emit({"connected": False})
            self.__connection_status_bar.setText("Joystick disconnected")
            self.__connection_status_bar.setStyleSheet(RED_TEXT_CSS)
            self._wait_for_joystick()

    def __calculate_pulsewidth(self, axis_info):
        # Convert the base axis values to PWM.
        horizontal_base = self.__map_to_pwm(axis_info.get("horizontal"))
        vertical_base = self.__map_to_pwm(axis_info.get("vertical"))
        # Calculate the differential offsets.
        h_offset = self.__map_to_differential(axis_info.get("h_discrete"))
        v_offset = self.__map_to_differential(axis_info.get("v_discrete"))

        # --- Horizontal Thrusters ---
        # Apply discrete (asymmetrical) control:
        # If h_offset is positive, only adjust the right thruster.
        # If h_offset is negative, only adjust the left thruster.
        if h_offset >= 0:
            left_thruster = horizontal_base         # remains at base
            right_thruster = horizontal_base - h_offset  # adjusted downward
        else:
            left_thruster = horizontal_base + abs(h_offset) # adjusted upward
            right_thruster = horizontal_base         # remains at base

        # --- Vertical (Top) Thrusters ---
        # Use the same asymmetrical approach:
        if v_offset >= 0:
            topleft_thruster = vertical_base             # remains at base
            topright_thruster = vertical_base - v_offset   # adjusted downward
        else:
            topleft_thruster = vertical_base + abs(v_offset) # adjusted upward
            topright_thruster = vertical_base             # remains at base

        return {
            "leftthruster": round(left_thruster),
            "rightthruster": round(right_thruster),
            "topleftthruster": round(topleft_thruster),
            "toprightthruster": round(topright_thruster)
        }

    def __map_to_pwm(self, val):
        # Map a joystick value in [-1, 1] to a PWM pulsewidth.
        if val is None or (val >= -PWM_DEADZONE_MIN and val <= PWM_DEADZONE_MIN):
            return 1500
        else:
            return 400 * (val + 1) + 1100

    def __map_to_differential(self, val):
        # Increase deadzone for differential inputs to ignore small noise.
        if val is None or abs(val) < 0.05:
            return 0
        else:
            return self.__map_to_pwm(val) - 1500

    def __update_thrust_labels(self, pulsewidths):
        # Update your GUI labels as desired.
        self.__left_right_thrust_label.setText(
            f"Left Thruster: {pulsewidths.get('leftthruster')}, Right Thruster: {pulsewidths.get('rightthruster')}"
        )
        self.__vertical_thrust_label.setText(
            f"Top Left: {pulsewidths.get('topleftthruster')}, Top Right: {pulsewidths.get('toprightthruster')}"
        )
