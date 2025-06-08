from PyQt5.QtCore import pyqtSignal, QThread, QTimer, pyqtSlot
import pygame
import logging
import coloredlogs
import _thread as thread
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
        self.__connection_status_bar.setText(
            f"Joystick ({self.__joystick.get_name()}) connected")
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



            # Left joystick:
            #     Axis 0 → Left/Right movement (X-axis)
            #     Axis 1 → Up/Down movement (Y-axis)
            # Right joystick:
            #     Axis 3 → Left/Right movement (X-axis)
            #     Axis 4 → Up/Down movement (Y-axis)

            left_trigger = self.__joystick.get_axis(2)
            right_trigger = self.__joystick.get_axis(5)

            # This controls the VERTICAL TWO TOP THRUSTERS and in parrallel makes them go and down
            right_horizontal_thumbstick = self.__joystick.get_axis(4) 
            # This is controlling H Left right now
            left_horizontal_thumbstick = self.__joystick.get_axis(0)

            left_thumbstick_up_down = self.__joystick.get_axis(1) 
            right_thumbstick_left_right = self.__joystick.get_axis(3)


            for event in pygame.event.get():
                if event.type == pygame.JOYBUTTONDOWN and event.button == 4:
                    self.__video_thread.save_screenshot()

            if abs(right_horizontal_thumbstick) < DEADZONE_MIN:
                right_horizontal_thumbstick = 0
            if abs(left_thumbstick_up_down) < DEADZONE_MIN:
                left_thumbstick_up_down = 0
            if abs(right_thumbstick_left_right) < DEADZONE_MIN:
                right_thumbstick_left_right = 0
            if abs(left_horizontal_thumbstick) < DEADZONE_MIN:
                left_horizontal_thumbstick = 0

            axis_info = {
            "tLeft_LeftRight": right_horizontal_thumbstick,  
            "tLeft_UpDown": left_thumbstick_up_down,        
            "tRight_LeftRight": right_thumbstick_left_right,
            "tRight_UpDown": left_horizontal_thumbstick
            } 

            pulsewidths = self.__calculate_pulsewidth(axis_info)
            self.__update_thrust_labels(pulsewidths)

            joystick_info = {
                "connected": "True",
                "joystickName": self.__joystick.get_name(),
                "axisInfo": [
                    pulsewidths.get("forward_backward_pulsewidth"),
                    pulsewidths.get("left_pulsewidth"),
                    pulsewidths.get("right_pulsewidth"),
                    pulsewidths.get("ascend_descend_pulsewidth"),
                    pulsewidths.get("pitch_left_pulsewidth"),
                    pulsewidths.get("pitch_right_pulsewidth")
                ]
            }
            to_arduino = {
                "axisInfo": [
                    pulsewidths.get("forward_backward_pulsewidth"),
                    pulsewidths.get("left_pulsewidth"),
                    pulsewidths.get("right_pulsewidth"),
                    pulsewidths.get("ascend_descend_pulsewidth"),
                    pulsewidths.get("pitch_left_pulsewidth"),
                    pulsewidths.get("pitch_right_pulsewidth")
                ],
                "left_trigger": left_trigger,
                "right_trigger": right_trigger
            }

            if right_trigger >  0.1:
                claw_pw = 4000 # open
            elif left_trigger  >  0.1:
                claw_pw = 1500   # close
            else:
                claw_pw = 1500   # hold
            to_arduino["claw"] = claw_pw


            current_time = time.time()
            if current_time - self.__last_sent_time > ARDUINO_SEND_TIMER_MIN:
                self.__arduino_thread.handle_data(to_arduino)
                self.__last_sent_time = current_time

            self.joystick_change_signal.emit(joystick_info)
        else:
            self.joystick_change_signal.emit({"connected": False})
            self.__connection_status_bar.setText(f"Joystick disconnected")
            self.__connection_status_bar.setStyleSheet(RED_TEXT_CSS)
            self._wait_for_joystick()
    # 1100: Full reverse thrust
    # 1500: No thrust
    # 1900: Full forward thrust
    def __calculate_pulsewidth(self, axis_info):

        right_horizontal_thumbstick = axis_info.get("tLeft_LeftRight")
        left_thumbstick_up_down = axis_info.get("tLeft_UpDown")
        right_thumbstick_left_right = axis_info.get("tRight_LeftRight")
        left_horizontal_thumbstick = axis_info.get("tRight_UpDown")

        forward_backward_pulsewidth = RESTING_PULSEWIDTH
        left_pulsewidth = RESTING_PULSEWIDTH
        right_pulsewidth = RESTING_PULSEWIDTH
        ascend_descend_pulsewidth = RESTING_PULSEWIDTH
        pitch_left_pulsewidth = RESTING_PULSEWIDTH
        pitch_right_pulsewidth = RESTING_PULSEWIDTH

        if left_thumbstick_up_down < 0:
            forward_backward_pulsewidth = self.__map_to_pwm(
                left_thumbstick_up_down)
        elif left_thumbstick_up_down > 0:
            forward_backward_pulsewidth = self.__map_to_pwm(
                left_thumbstick_up_down)

        if right_horizontal_thumbstick < 0:
            left_pulsewidth = self.__map_to_pwm(right_horizontal_thumbstick)
            right_pulsewidth = self.__map_to_pwm(
                -right_horizontal_thumbstick)
        elif right_horizontal_thumbstick > 0:
            left_pulsewidth = self.__map_to_pwm(right_horizontal_thumbstick)
            right_pulsewidth = self.__map_to_pwm(
                -right_horizontal_thumbstick)

        if left_horizontal_thumbstick < 0:  # Thumbstick down (descend)
            ascend_descend_pulsewidth = self.__map_to_pwm(
                left_horizontal_thumbstick)
        else:
            ascend_descend_pulsewidth = self.__map_to_pwm(
                left_horizontal_thumbstick)

        if right_thumbstick_left_right < 0:  # Pitch ccw
            pitch_left_pulsewidth = self.__map_to_pwm(
                right_thumbstick_left_right)
            pitch_right_pulsewidth = self.__map_to_pwm(
                -right_thumbstick_left_right)
        else:
            pitch_left_pulsewidth = self.__map_to_pwm(
                right_thumbstick_left_right)
            pitch_right_pulsewidth = self.__map_to_pwm(
                -right_thumbstick_left_right)

        forward_backward_pulsewidth = round(forward_backward_pulsewidth)
        left_pulsewidth = round(left_pulsewidth)
        right_pulsewidth = round(right_pulsewidth)
        ascend_descend_pulsewidth = round(ascend_descend_pulsewidth)
        pitch_left_pulsewidth = round(pitch_left_pulsewidth)
        pitch_right_pulsewidth = round(pitch_right_pulsewidth)

        return {
            "forward_backward_pulsewidth": round(forward_backward_pulsewidth),
            "left_pulsewidth": round(left_pulsewidth),
            "right_pulsewidth": round(right_pulsewidth),
            "ascend_descend_pulsewidth": round(ascend_descend_pulsewidth),
            "pitch_left_pulsewidth": round(pitch_left_pulsewidth),
            "pitch_right_pulsewidth": round(pitch_right_pulsewidth)
        }

    def __map_to_pwm(self, val):
        if val >= -PWM_DEADZONE_MIN and val <= PWM_DEADZONE_MIN:
            return 1500
        else:
            return 400*(val + 1) + 1100

    def __update_thrust_labels(self, pulsewidths):
        forward_backward_thrust_label_text = None
        vertical_thrust_label_text = None
        left_right_thrust_label_text = None
        pitch_thrust_label_text = None

        fb_pw = pulsewidths.get("forward_backward_pulsewidth")
        v_pw = pulsewidths.get("ascend_descend_pulsewidth")
        l_pw = pulsewidths.get("left_pulsewidth")
        r_pw = pulsewidths.get("right_pulsewidth")
        pl_pw = pulsewidths.get("pitch_left_pulsewidth")
        pr_pw = pulsewidths.get("pitch_right_pulsewidth")

        if fb_pw < 1500:
            fb_pw_percent = (fb_pw/1100.0)*100.0
            forward_backward_thrust_label_text = "Backward" + \
                f" ({fb_pw_percent:.2f}% power)"
        elif fb_pw == 1500:
            forward_backward_thrust_label_text = "0.00% power"
        else:
            fb_pw_percent = (fb_pw/1900.0)*100.0
            forward_backward_thrust_label_text = "Forward" + \
                f" ({fb_pw_percent:.2f}% power)"

        if v_pw < 1500:
            v_pw_percent = (v_pw/1100.0)*100.0
            vertical_thrust_label_text = "Downward" + \
                f" ({v_pw_percent:.2f}% power)"
        elif v_pw == 1500:
            vertical_thrust_label_text = "0.00% power"
        else:
            v_pw_percent = (v_pw/1900.0)*100.0
            vertical_thrust_label_text = "Upward" + \
                f" ({v_pw_percent:.2f}% power)"

        if l_pw < r_pw:
            l_r_percent = (r_pw/1900.0)*100.0
            left_right_thrust_label_text = "Left" + \
                f" ({l_r_percent:.2f}% power)"
        elif l_pw == 1500 and r_pw == 1500 or l_pw == r_pw:
            left_right_thrust_label_text = "0.00% power"
        else:
            l_r_percent = (l_pw/1900.0)*100.0
            left_right_thrust_label_text = "Right" + \
                f" ({l_r_percent:.2f}% power)"

        if pl_pw < pr_pw:
            p_percent = (pr_pw/1900.0)*100.0
            pitch_thrust_label_text = "CCW" + f" ({p_percent:.2f}% power)"
        elif pl_pw == 1500 and pr_pw == 1500 or pl_pw == pr_pw:
            pitch_thrust_label_text = "0.00% power"
        else:
            p_percent = (pl_pw/1900.0)*100.0
            pitch_thrust_label_text = "CW" + f" ({p_percent:.2f}% power)"

        self.__forward_backward_thrust_label.setText(
            forward_backward_thrust_label_text)
        self.__vertical_thrust_label.setText(
            vertical_thrust_label_text)
        self.__left_right_thrust_label.setText(
            left_right_thrust_label_text)
        self.__pitch_thrust_label.setText(pitch_thrust_label_text)
