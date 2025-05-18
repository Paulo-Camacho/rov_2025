# Arduino Mega ROV

- This is code from jdremi that was written in-house for the Deep Sea Dogs ROV "T.O.A.S.T."

# Requirements

- Python 3.12.3.
- Full installation of dependencies, make sure to run this within the root folder of the project
(`pip install -r requirements.txt`).

# Running

- Navigate to the /app directory and run the program by typing `python ./gui/app.py` OR navigate to the `gui` directory and then 
run by typing `python ./app.py`. Make sure you are doing this while inside of a virtual python environment.

# Trouble shooting
- 
# 1. Remove broken .venv folder if it exists
rm -rf .venv

# 2. Create a fresh virtual environment
python3 -m venv .venv

# 3. Activate the environment
source .venv/bin/activate

# 4. Install packages
pip install -r requirements.txt
