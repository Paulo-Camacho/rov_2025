import serial
from PyQt5.QtCore import pyqtSignal, QThread, QObject, QTimer, pyqtSlot
import platform
import serial.tools.list_ports as ports
import coloredlogs
import logging
import json
from queue import Queue
import time

coloredlogs.install(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ArduinoReadWorker(QObject):
    arduino_data_channel_signal = pyqtSignal(dict)

    def __init__(self, serial_port):
        super().__init__()
        self.serial_port = serial_port
        self.running = True

    def read_arduino(self):
        while self.running:
            try:
                payload = self.serial_port.readline().decode("utf-8").strip()
                if payload:
                    data = json.loads(payload)
                    self.arduino_data_channel_signal.emit(data)
            except Exception as e:
                logger.critical(f"Error reading Arduino: {e}")


class ArduinoWriteWorker(QObject):
    def __init__(self, serial_port, queue):
        super().__init__()
        self.serial_port = serial_port
        self.queue = queue
        self.running = True

    def handle_data(self):
        import queue as _queue
        while self.running:
            try:
                data = self.queue.get(timeout=0.02)
                payload = json.dumps(data) + '\0'
                self.serial_port.write(payload.encode('utf-8'))
                self.serial_port.flush()
            except _queue.Empty:
                continue
            except Exception as e:
                logger.critical(f"Error writing to Arduino: {e}")


class ArduinoThread(QThread):
    arduino_data_channel_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.write_queue = Queue()
        self.__serial = None
        self._run_flag = True
        self.__initialize_serial()

        if self.__serial:
            # Reader
            self.read_worker = ArduinoReadWorker(self.__serial)
            self.read_worker.arduino_data_channel_signal.connect(self.forward_arduino_data)
            self.read_thread = QThread()
            self.read_worker.moveToThread(self.read_thread)
            self.read_thread.started.connect(self.read_worker.read_arduino)
            self.read_thread.start()

            # Writer
            self.write_worker = ArduinoWriteWorker(self.__serial, self.write_queue)
            self.write_thread = QThread()
            self.write_worker.moveToThread(self.write_thread)
            self.write_thread.started.connect(self.write_worker.handle_data)
            self.write_thread.start()

        logger.info("Arduino thread ready!")

    def __initialize_serial(self):
        port_filter = None
        available_ports = self.__list_ports()
        logger.debug(f"Available ports: {available_ports}")

        match platform.system():
            case "Darwin":
                port_filter = "/dev/cu.usb"
            case "Linux":
                port_filter = "/dev/ttyACM"
            case "Windows":
                port_filter = "COM"

        filtered_ports = [p for p in available_ports if port_filter in p]
        if not filtered_ports:
            logger.critical("Arduino port not found! Ensure proper connection.")
        else:
            port = filtered_ports[0]
            logger.debug(f"Using port: {port}")
            self.__serial = serial.Serial(port=port, baudrate=9600, write_timeout=0, dsrdtr=True)

    def __list_ports(self):
        return [port.device for port in ports.comports()]

    def stop(self):
        if self.read_worker:
            self.read_worker.running = False
        if self.write_worker:
            self.write_worker.running = False
        if hasattr(self, "read_thread"):
            self.read_thread.quit()
            self.read_thread.wait()
        if hasattr(self, "write_thread"):
            self.write_thread.quit()
            self.write_thread.wait()
        self._run_flag = False
        self.wait()

    def handle_data(self, data):
        self.write_queue.put(data)

    @pyqtSlot(dict)
    def forward_arduino_data(self, data):
        self.arduino_data_channel_signal.emit(data)
