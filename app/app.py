import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QFrame, QLabel
from videowidget import VideoWidget
from joystickthread import JoystickThread
from arduinothread import ArduinoThread

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SEA POUNCE")
        self.setGeometry(100, 100, 1400, 900)
        # Use a modern dark background color that pops.
        self.setStyleSheet("background-color: #282c34;")
        
        # Create a central widget with a grid layout.
        central_widget = QWidget(self)
        central_widget.setStyleSheet("background-color: #282c34;")
        self.setCentralWidget(central_widget)
        grid = QGridLayout(central_widget)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(20)
        
        # --- Row 0: Video Widget ---
        self.video_widget = VideoWidget(640, 480)
        self.video_widget.setStyleSheet("background-color: transparent;")
        grid.addWidget(self.video_widget, 0, 0, 1, 2)
        
        # --- Row 1, Column 0: Thruster Outputs Panel (only Left/Right & Vertical) ---
        thruster_frame = QFrame()
        # Updated colors and border for increased vibrancy.
        thruster_frame.setStyleSheet(
            "background-color: #1E1E1E; border: 2px solid #61afef; border-radius: 5px;"
        )
        thruster_layout = QGridLayout(thruster_frame)
        thruster_layout.setSpacing(10)
        thruster_style = (
            "font-size: 32px; font-weight: bold; color: #61afef; "
            "background-color: transparent; padding: 10px;"
        )
        self.left_right_label = QLabel("Left/Right: 1500", self)
        self.left_right_label.setStyleSheet(thruster_style)
        self.vertical_label = QLabel("Vertical: 1500", self)
        self.vertical_label.setStyleSheet(thruster_style)
        thruster_layout.addWidget(self.left_right_label, 0, 0)
        thruster_layout.addWidget(self.vertical_label, 0, 1)
        grid.addWidget(thruster_frame, 1, 0)
        
        # --- Row 1, Column 1: Status / Telemetry Panel ---
        status_frame = QFrame()
        # Use a striking orange border for this panel.
        status_frame.setStyleSheet(
            "background-color: #1E1E1E; border: 2px solid #e06c75; border-radius: 5px;"
        )
        status_layout = QGridLayout(status_frame)
        status_layout.setSpacing(10)
        self.status_label = QLabel("Status: Waiting for controller...", self)
        self.status_label.setStyleSheet(
            "font-size: 32px; font-weight: bold; color: #e5c07b; "
            "background-color: transparent; padding: 10px;"
        )
        status_layout.addWidget(self.status_label, 0, 0)
        grid.addWidget(status_frame, 1, 1)
        
        # --- Create dummy labels for removed panels (Forward/Backward and Pitch) ---
        self.dummy_fb_label = QLabel("Forward/Backward: 1500", self)
        self.dummy_fb_label.setVisible(False)
        self.dummy_pitch_label = QLabel("Pitch: 1500", self)
        self.dummy_pitch_label.setVisible(False)
        
        # --- Instantiate Threads ---
        self.arduino_thread = ArduinoThread()
        self.arduino_thread.start()
        
        self.joystick_thread = JoystickThread(
            forward_backward_thrust_label=self.dummy_fb_label,
            left_right_thrust_label=self.left_right_label,
            vertical_thrust_label=self.vertical_label,
            pitch_thrust_label=self.dummy_pitch_label,
            status_bar=self.status_label,
            arduino_thread=self.arduino_thread,
            video_thread=self.video_widget  # used for screenshot capture
        )
        self.joystick_thread.start()
        
        # --- Connect Signals ---
        self.joystick_thread.joystick_change_signal.connect(
            lambda data: self.video_widget.update_axis_info(data.get("axis_readings", {}), data)
        )
        self.joystick_thread.joystick_change_signal.connect(
            lambda data: self.status_label.setText(f"{data.get('joystickName', 'N/A')}")
        )
        self.arduino_thread.arduino_data_channel_signal.connect(self.handle_arduino_data)
        
    def handle_arduino_data(self, data):
        print("Arduino Telemetry:", data)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
