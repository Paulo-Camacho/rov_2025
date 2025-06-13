# Arduino Mega ROV

Sea Pounce ROV

This code powers Sea Pounce's thrusters, sensors, and user interface, optimizing hardware-software integration. Developed for
Cuesta College's Aqua Cats Robotics Team for the MATE ROV Competition, it refines control and responsiveness for competitive
underwater robotics.


## Requirements

Ensure you have the following installed before running the project:

* Python 3.12.3

* pip 24.0

* All dependencies (install using the commands below in the project's root folder):

~~~
$ python3 -m venv .venv
$ source .venv/bin/activate
$ pip install -r requirements.txt
~~~


## Running the Application
To launch the program, follow one of these steps:
~~~
python3 ./app.py
~~~


## Troubleshooting
If you encounter issues with the virtual environment, reset it with the following steps:

### Remove broken .venv folder (if it exists):
~~~
rm -rf .venv
~~~

### Create a fresh virtual environment:
~~~
python3 -m venv .venv
~~~

### Activate the environment:
~~~
source .venv/bin/activate
~~~

### Install dependencies again:
~~~
pip install -r requirements.txt
~~~

#### Trouble-shooting Ubuntu
~~~
$ sudo apt-get install '^libxcb.*-dev' libx11-xcb-dev libglu1-mesa-dev libxrender-dev libxi-dev libxkbcommon-dev libxkbcommon-x11-dev
~~~

## Credits
This repository contains in-house code developed by jdremi for the Deep Sea Dogs ROV, named T.O.A.S.T., originally based on work
from the rov-2024 project. 

Feel free to submit pull requests or open issues if you find bugs or have suggestions for improvements.
