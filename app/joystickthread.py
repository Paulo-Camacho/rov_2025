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
        self.claw_pw = 1500
        self.claw2_pw = 1500

        pygame.init()
        self._wait_for_joystick_timer = QTimer(self)
        self._wait_for_joystick_timer.timeout.connect(self._wait_for_joystick)

        if pygame.joystick.get_count() == 0:
            logger.warning("No joystick detected! Waiting for joysticks...")
            self._wait_for_joystick_timer.start(1000)
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
        if not commands.get("connected"):
            logger.warning("Joystick disconnected")

    def check_joystick_input(self):
        if self.__joystick is None or pygame.joystick.get_count() == 0:
            self.joystick_change_signal.emit({"connected": False})
            self.__connection_status_bar.setText("Joystick disconnected")
            self.__connection_status_bar.setStyleSheet(RED_TEXT_CSS)
            self._wait_for_joystick()
            return

        pygame.event.pump()

        # Read axis values
        horizontal_base = self.__joystick.get_axis(1) or 0
        h_discrete = self.__joystick.get_axis(0) or 0
        vertical_input = self.__joystick.get_axis(4) or 0
        v_discrete = self.__joystick.get_axis(3) or 0

        left_trigger = self.__joystick.get_axis(2) or 0
        right_trigger = self.__joystick.get_axis(5) or 0
        left_bumper = self.__joystick.get_button(4)
        right_bumper = self.__joystick.get_button(5)

        for event in pygame.event.get():
            if event.type == pygame.JOYBUTTONDOWN and event.button == 3:
                self.__video_thread.save_screenshot()

        axis_info = {
            "horizontal": horizontal_base,
            "vertical": vertical_input,
            "h_discrete": h_discrete,
            "v_discrete": v_discrete
        }

        pulsewidths = self.__calculate_pulsewidth(axis_info)
        self.__update_thrust_labels(pulsewidths)

        to_arduino = {
            "axisInfo": [
                pulsewidths.get("leftthruster"),
                pulsewidths.get("rightthruster"),
                pulsewidths.get("topleftthruster"),
                pulsewidths.get("toprightthruster")
            ],
            "left_trigger": left_trigger,
            "right_trigger": right_trigger,
            "claw_trigger": self.claw_pw,
            "claw_bumper": self.claw2_pw
        }

        CLAW_STEP = 7
        if left_trigger > 0.1:
            self.claw_pw = min(self.claw_pw + CLAW_STEP, 2100)
        elif right_trigger > 0.1:
            self.claw_pw = max(self.claw_pw - CLAW_STEP, 1100)
        if left_bumper:
            self.claw2_pw = min(self.claw2_pw + CLAW_STEP, 2100)
        elif right_bumper:
            self.claw2_pw = max(self.claw2_pw - CLAW_STEP, 1100)

        current_time = time.time()
        if current_time - self.__last_sent_time > ARDUINO_SEND_TIMER_MIN:
            self.__arduino_thread.handle_data(to_arduino)
            self.__last_sent_time = current_time

        axis_labels = {
            "Axis 0 (Left Stick X - Yaw)": h_discrete,
            "Axis 4 (Right Stick X - Vertical)": -vertical_input
        }

        self.joystick_change_signal.emit({
            "connected": "True",
            "joystickName": "Controller: " + self.__joystick.get_name(),
            "axis_readings": axis_labels,
            "axisInfo": to_arduino["axisInfo"],
            "claw_trigger": self.claw_pw,
            "claw_bumper": self.claw2_pw
        })

    def __calculate_pulsewidth(self, axis_info):
        horizontal_base = self.__map_to_pwm(axis_info.get("horizontal"))
        vertical_base = self.__map_to_pwm(axis_info.get("vertical"))
        h_offset = self.__map_to_differential(axis_info.get("h_discrete"))
        v_value = axis_info.get("v_discrete") or 0
        tilt_threshold = 0.5

        # Horizontal thrusters
        if h_offset >= 0:
            left_thruster = horizontal_base
            right_thruster = horizontal_base - h_offset
        else:
            left_thruster = horizontal_base - abs(h_offset)
            right_thruster = horizontal_base

        # Top thrusters (Axis 3 pitch + Axis 4 lift base)
        if v_value > tilt_threshold:
            left_top = self.__map_to_pwm(-v_value)
            right_top = vertical_base
        elif v_value < -tilt_threshold:
            left_top = vertical_base
            right_top = self.__map_to_pwm(v_value)
        else:
            left_top = right_top = vertical_base

        return {
            "leftthruster": round(left_thruster),
            "rightthruster": round(right_thruster),
            "topleftthruster": round(left_top),
            "toprightthruster": round(right_top)
        }

    def __map_to_pwm(self, val):
        if val is None or abs(val) < PWM_DEADZONE_MIN:
            return 1500
        return int(400 * (val + 1) + 1100)

    def __map_to_differential(self, val):
        if val is None or abs(val) < 0.05:
            return 0
        return self.__map_to_pwm(val) - 1500

    def __update_thrust_labels(self, pulsewidths):
        self.__left_right_thrust_label.setText(
            f"Top Left Thruster: {pulsewidths.get('topleftthruster')}\n\nLeft Thruster: {pulsewidths.get('leftthruster')}"
        )
        self.__vertical_thrust_label.setText(
            f"Top Right Thruster: {pulsewidths.get('toprightthruster')}\n\nRight Thruster: {pulsewidths.get('rightthruster')}"
        )
    # def __update_thrust_labels(self, pulsewidths):
    #     self.__left_right_thrust_label.setText(
    #         f"Left  Thruster:{pulsewidths.get('leftthruster')}\nRight Thruster:{pulsewidths.get('rightthruster')}"
    #     )
    #     self.__vertical_thrust_label.setText(
    #         f"Top Left  Thruster:{pulsewidths.get('topleftthruster')}\nTop Right Thruster:{pulsewidths.get('toprightthruster')}"
    #     )

