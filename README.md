# Arduino Mega ROV

This code powers the ROV's thrusters, sensors, and user interface, optimizing hardware-software 
integration.


## Requirements

Ensure you have the following installed before running the project:

* Python 3.12.3

* All dependencies (install using the command below in the project's root folder):

~~~
pip install -r requirements.txt
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


## Credits
This repository contains in-house code developed by jdremi for the Deep Sea Dogs ROV, named T.O.A.S.T., originally based on work
from the rov-2024 project. 

Feel free to submit pull requests or open issues if you find bugs or have suggestions for improvements.
