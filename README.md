# FREAKalyze

FREAKalyze is the post-processing counterpart to Project FREAK, where users can analyze their data with more freedom and flexibility. 
FREAKalyze was written in Python using modules Dear PyGui, SciPy, and tkinter to allow it to be more editable, extensible, and maintainable. 

## Installation

Open a terminal in the folder you would like to install FREAKalyze in and enter `git clone https://github.com/Team-Freak-Mizzou/FREAKalyze.git`.
A repository will be instantiated in a folder named FREAKalyze. 

The next step is to create a Python virtual environment so that the project modules may be located by the interpreter. 
Inside the folder that contains FREAKalyze, enter `python -m venv FREAKalyze`. 

To activate your virtual environment, navigate into the folder FREAKalyze and for Windows, enter `./Scripts/activate`. For Mac and Unix, enter `source bin/activate`.

Next, install required Python modules by entering `pip install -r requirements.txt`.

## How to run FREAKalyze

To run FREAKalyze, run `python main.py` inside of the FREAKalyze folder. A window asking you to choose a folder will appear.
Select the folder that contains the output data from Project FREAK.

To load your data, click the button at the top that says "Populate Graphs and Load Camera Feed". 
