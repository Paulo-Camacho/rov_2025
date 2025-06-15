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
        """
        Initializes the ArduinoThread instance.

        Args:
            serial_port (str): The serial port used for communication with the Arduino.
        """
        super().__init__()
        self.serial_port = serial_port  # Serial port for communication with Arduino
        self.running = True  # Flag to control the reading loop

    def read_arduino(self):
        while self.running:
            try:
                # Read a line from the serial port and decode it
                payload = self.serial_port.readline().decode("utf-8")
                logger.debug(f"PAYLOAD = {payload}")
                if payload:
                    # Parse the JSON data
                    data = json.loads(payload)
                    # Emit the signal with the received data
                    self.arduino_data_channel_signal.emit(data)
            except Exception as e:
                logger.critical(f"Error reading Arduino: {e}")


class ArduinoWriteWorker(QObject):

    def __init__(self, serial_port, queue):
        super().__init__()
        self.serial_port = serial_port  # Serial port for communication with Arduino
        self.queue = queue  # Queue for handling data to be sent to Arduino
        self.running = True  # Flag to control the writing loop

    def handle_data(self):
        while self.running:
            if not self.queue.empty():
                data = self.queue.get()  # Get data from the queue
                try:
                    # Convert data to JSON format and send to Arduino
                    payload = json.dumps(data) + '\0'
                    # logger.debug(f"Sending payload to Arduino: {payload}")
                    self.serial_port.write(bytes(payload, 'utf-8'))
                    self.serial_port.flush()
                except Exception as e:
                    logger.critical(f"Error writing to Arduino: {e}")
            time.sleep(0.1)  # Small delay to avoid busy waiting
        import queue as _queue
        while self.running:
            try:
                # block up to 20ms for next packet, otherwise loop to check running flag
                data = self.queue.get(timeout=0.02)
            except _queue.Empty:
                continue
            try:
                payload = json.dumps(data) + '\0'
                self.serial_port.write(payload.encode('utf-8'))
                self.serial_port.flush()
            except Exception as e:
                logger.critical(f"Error writing to Arduino: {e}")



class ArduinoThread(QThread):
    arduino_data_channel_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.write_queue = Queue()
        self.__serial = None
        self.__initialize_serial()

        if self.__serial:
            # Initialize reading worker and thread
            self.read_worker = ArduinoReadWorker(self.__serial)
            self.read_thread = QThread()
            self.read_worker.moveToThread(self.read_thread)
            self.read_worker.arduino_data_channel_signal.connect(
                self.forward_arduino_data)
            self.read_thread.started.connect(self.read_worker.read_arduino)
            self.read_thread.start()

            # Initialize writing worker and thread
            self.write_worker = ArduinoWriteWorker(
                self.__serial, self.write_queue)
            self.write_thread = QThread()
            self.write_worker.moveToThread(self.write_thread)
            self.write_thread.started.connect(self.write_worker.handle_data)
            self.write_thread.start()

        logger.info("Arduino thread ready!")

    def __initialize_serial(self):
        port_filter = None
        available_ports = self.__list_ports()

        logger.debug(f"Available ports: {available_ports}")

        # Set port filter based on operating system
        match platform.system():
            case "Darwin":
                port_filter = "/dev/cu.usb"
            case "Linux":
                port_filter = "/dev/ttyACM"
            case "Windows":
                port_filter = "COM"

        # Filter ports based on the port filter
        filtered_ports = list(
            filter(lambda name: port_filter in name, available_ports))

        if len(filtered_ports) == 0:
            logger.critical(
                "Arduino port not found! Ensure proper connection.")
        else:
            port = filtered_ports[0]  # Use the first available port
            logger.debug(f"Using port: {port}")
            # Initialize serial connection
            self.__serial = serial.Serial(
                port=port, baudrate=9600, write_timeout=0, dsrdtr=True)
            logger.debug(f"Serial initialized: {self.__serial}")

    # Function to list available serial ports
    def __list_ports(self):
        """
        Lists all available serial ports.

        This method retrieves a list of all available serial ports on the system
        and returns their device names.

        Returns:
            list: A list of strings, where each string represents the device name
                  of an available serial port.
        """
        return [port.device for port in list(ports.comports())]

    # Function to stop the workers and threads
    def stop(self):
        """
        Stops the execution of the Arduino thread and its associated workers.

        This method ensures that both the reading and writing worker loops are stopped,
        their respective threads are properly quit and waited for, and the main thread
        is also terminated cleanly.

        Steps performed:
        1. Stops the reading worker loop if it exists.
        2. Stops the writing worker loop if it exists.
        3. Quits and waits for the read thread to finish.
        4. Quits and waits for the write thread to finish.
        5. Sets the internal run flag to False.
        6. Waits for the main thread to finish execution.
        """
        if self.read_worker:
            self.read_worker.running = False  # Stop the reading worker loop
        if self.write_worker:
            self.write_worker.running = False  # Stop the writing worker loop
        self.read_thread.quit()  # Quit the read thread
        self.read_thread.wait()  # Wait for the read thread to finish
        self.write_thread.quit()  # Quit the write thread
        self.write_thread.wait()  # Wait for the write thread to finish
        self._run_flag = False
        self.wait()  # Wait for the thread to finish

    # Function to handle data to be sent to Arduino
    def handle_data(self, data):
        """
        Handles incoming data by adding it to the write queue for processing.

        Args:
            data (Any): The data to be queued for sending to the Arduino.

        Notes:
            - The method places the provided data into the `write_queue`.
            - If the queue size grows excessively large (e.g., > 1000 items), 
              additional handling may be required to manage the queue size.
        """
        # logger.debug(f"Queueing data to send to Arduino: {data}")
        self.write_queue.put(data)  # Put data in the queue

        # If queue becomes too big (> 1000), we might need to clear it.
        # logger.debug(f"Queue size: {self.write_queue.qsize()}")

    # Slot to forward data read from Arduino to the main application
    @pyqtSlot(dict)
    def forward_arduino_data(self, data):
        """
        Forwards data received from the Arduino to the main thread via a PyQt signal.

        This method is a PyQt slot that emits the `arduino_data_channel_signal` signal
        with the provided data dictionary. It is typically used to transfer data
        between threads in a PyQt application.

        Args:
            data (dict): The data received from the Arduino to be forwarded.
        """
        # logger.debug(f"Forwarding data to main thread: {data}")
        self.arduino_data_channel_signal.emit(data)
