import os.path
import sys

DEBUG = False

if DEBUG:
    root_temp = os.path.dirname(os.path.abspath(__file__)).replace("\\core", "")
    root_exe = os.path.dirname(os.path.abspath(__file__)).replace("\\core", "")
else:
    root_temp = os.path.dirname(os.path.abspath(__file__)).replace("\\core", "")
    root_exe = os.path.dirname(sys.executable)
