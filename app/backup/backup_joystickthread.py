from PyQt5.QtCore import pyqtSignal, QThread, QTimer, pyqtSlot
import pygame
import logging
import coloredlogs
import time

coloredlogs.install(level=logging.DEBUG)
logger = logging.getLogger(__name__)

GREEN_TEXT_CSS = "color: green"
RED_TEXT_CSS = "color: red"
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
            logger.warning("No joystick detected! Waiting...")
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
        name = self.__joystick.get_name()
        logger.info(f"Joystick found: {name}")
        self.__connection_status_bar.setText(f"Joystick ({name}) connected")
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

        left_trigger = self.__joystick.get_axis(2) or 0
        right_trigger = self.__joystick.get_axis(5) or 0
        left_bumper = self.__joystick.get_button(4)
        right_bumper = self.__joystick.get_button(5)

        for event in pygame.event.get():
            if event.type == pygame.JOYBUTTONDOWN and event.button == 3:
                self.__video_thread.save_screenshot()

        forward_axis = self.__joystick.get_axis(1) or 0       # Axis 1
        turn_axis = self.__joystick.get_axis(0) or 0          # Axis 0
        vertical_axis = -(self.__joystick.get_axis(4) or 0)   # Axis 4 (reversed)
        pitch_axis = self.__joystick.get_axis(3) or 0         # Axis 3

        axis_info = {
            "forward": forward_axis,
            "turn": turn_axis,
            "vertical": vertical_axis,
            "pitch": pitch_axis
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
            "right_trigger": right_trigger
        }

        CLAW_STEP = 7

        if right_trigger > 0.1:
            self.claw_pw = min(self.claw_pw + CLAW_STEP, 2100)
        elif left_trigger > 0.1:
            self.claw_pw = max(self.claw_pw - CLAW_STEP, 1100)

        if right_bumper:
            self.claw2_pw = min(self.claw2_pw + CLAW_STEP, 2100)
        elif left_bumper:
            self.claw2_pw = max(self.claw2_pw - CLAW_STEP, 1100)

        to_arduino["claw"] = self.claw_pw
        to_arduino["claw2"] = self.claw2_pw

        current_time = time.time()
        if current_time - self.__last_sent_time > ARDUINO_SEND_TIMER_MIN:
            self.__arduino_thread.handle_data(to_arduino)
            self.__last_sent_time = current_time

        self.joystick_change_signal.emit({
            "connected": "True",
            "joystickName": self.__joystick.get_name(),
            "axisInfo": to_arduino["axisInfo"]
        })

    def __calculate_pulsewidth(self, axis_info):
        forward_pwm = self.__map_to_pwm(axis_info.get("forward"))
        turn_pwm = self.__map_to_pwm(axis_info.get("turn"))
        vertical_pwm = self.__map_to_pwm(axis_info.get("vertical"))
        pitch_val = axis_info.get("pitch") or 0

        # Horizontal thrusters
        left = int(forward_pwm + (turn_pwm - 1500))
        right = int(forward_pwm - (turn_pwm - 1500))
        right = 3000 - right  # Invert right motor

        # Vertical thrusters with discrete control from Axis 3
        if pitch_val > 0.05:
            topleft = vertical_pwm
            topright = 3000 - (vertical_pwm - self.__map_to_differential(pitch_val))
        elif pitch_val < -0.05:
            topleft = vertical_pwm + abs(self.__map_to_differential(pitch_val))
            topright = 3000 - vertical_pwm
        else:
            topleft = vertical_pwm
            topright = 3000 - vertical_pwm

        return {
            "leftthruster": round(left),
            "rightthruster": round(right),
            "topleftthruster": round(topleft),
            "toprightthruster": round(topright)
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
            f"Left Thruster: {pulsewidths['leftthruster']}, Right Thruster: {pulsewidths['rightthruster']}"
        )
        self.__vertical_thrust_label.setText(
            f"Top Left: {pulsewidths['topleftthruster']}, Top Right: {pulsewidths['toprightthruster']}"
        )
