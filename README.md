# FlightRadar24 Web Scrapper

## Requirements

- Python (3.9 or later)
- Google Chrome
- Xvfb (For headless Linux or macOS devices only)

## Usage

```
pip install -r requirements.txt
python scrapper.py [number-of-threads]
```

## Step-by-Step Setup Guide (Windows)
1. Download and install Google Chrome from https://www.google.com/chrome/.
1. Download and install Python from https://www.python.org/downloads/.
   - During installation, check the "Add Python .... to PATH" option.
1. Open a terminal or command prompt window.
1. Enter `py --version` to check that python has successfully been installed.
   - If an error message occurs, try substituting `py` for `python` instead.
1. Enter `pip --version` to ensure that the package installer for Python has been installed.
1. Navigate to the folder containing `requirements.txt` by using `cd <path_to_folder>` in the terminal.
   - Use `cd ..` to navigate up a folder in the path.
   - Use `cd ~` to navigate to your home folder.
   - Use `cd <folder_name>` to navigate to a folder in your current directory.
1. To check that you are in the correct folder, use `ls` to list all files in the current folder.
1. Enter `pip install -r requirements.txt` to install all dependencies.
1. Enter `py scrapper.py` to start the scrapper.
   - Optionally, specify the number of browser instances to use by providing it at the end of the command. 
     - For example, use `py scrapper.py 4` to start the scrapper with 4 browser windows. 
     - By default the number of browser windows used is equal to the number of CPU cores of the computer.
     - Do not start the scrapper with more browser windows than the number of CPU cores.
