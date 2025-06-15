from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import pyqtSlot
import numpy as np
from videothread import VideoThread
import coloredlogs, logging

coloredlogs.install(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class VideoWidget(QWidget):
    def __init__(self, width, height):
        super().__init__()
        # Transparent background for a modern look.
        self.setStyleSheet("background-color: transparent;")
        
        # Label for displaying the video feed.
        self.__image_label = QLabel(self)
        self.__image_label.setFixedSize(1280, 720)
        self.__image_label.setScaledContents(True)
        
        # Start the video thread.
        self.__video_thread = VideoThread(width, height)
        self.__video_thread.change_pixmap_signal.connect(self.update_image)
        self.__video_thread.start()
        
        # Label to display detailed joystick axis info.
        self.__axis_label = QLabel("Joystick Axis Info: Not Updated", self)
        self.__axis_label.setStyleSheet(
            "font-size: 32px; font-weight: bold; color: #00E676; background-color: transparent; padding: 10px;"
        )
        
        # Arrange them in a vertical layout.
        layout = QVBoxLayout()
        layout.addWidget(self.__image_label)
        layout.addWidget(self.__axis_label)
        self.setLayout(layout)
    
    @pyqtSlot(np.ndarray)
    def update_image(self, cv_img):
        qt_img = self.__video_thread.convert_cv_qt(cv_img)
        self.__image_label.setPixmap(qt_img)
    
    def update_axis_info(self, axis_info, full_data):
        """
        Expects `axis_info` to be a dictionary with:
          - "Axis 0 (Left Stick X - Yaw)"
          - "Axis 4 (Right Stick X - Vertical)"
        Also, full_data may contain the keys "claw_trigger" and "claw_bumper".
        
        For display:
          • Axis 0 shows yaw (positive means turning right, negative means turning left).
          • Axis 4 is inverted (so positive means ascending, negative means descending).
          • Claw info is displayed with new names.
        """
        threshold = 0.05
        lines = ["Joystick Axis Details:"]
        for axis, value in axis_info.items():
            detail = ""
            if axis == "Axis 0 (Left Stick X - Yaw)":
                if value > threshold:
                    detail = "Turning Right (Increase right thruster offset)"
                elif value < -threshold:
                    detail = "Turning Left (Increase left thruster offset)"
                else:
                    detail = "Neutral (No yaw command)"
            elif axis == "Axis 4 (Right Stick X - Vertical)":
                if value > threshold:
                    detail = "Ascending (Provide vertical lift)"
                elif value < -threshold:
                    detail = "Descending (Reduce vertical lift)"
                else:
                    detail = "Neutral (No vertical change)"
            lines.append(f"{axis}: {round(value, 2)}  → {detail}")
        
        if "claw_trigger" in full_data:
            claw_val = full_data["claw_trigger"]
            if claw_val >= 2100:
                claw_state = "Max Open (Fully released)"
            elif claw_val <= 1100:
                claw_state = "Max Closed (Fully gripped)"
            else:
                claw_state = "Intermediate (Partial grip)"
            lines.append(f"Claw Trigger: {claw_val}  → {claw_state}")
        
        if "claw_bumper" in full_data:
            claw2_val = full_data["claw_bumper"]
            if claw2_val >= 2100:
                claw2_state = "Max Open (Fully released)"
            elif claw2_val <= 1100:
                claw2_state = "Max Closed (Fully gripped)"
            else:
                claw2_state = "Intermediate (Partial grip)"
            lines.append(f"Claw Bumper: {claw2_val}  → {claw2_state}")
        
        self.__axis_label.setText("\n".join(lines))
    
    def get_video_thread(self):
        return self.__video_thread
