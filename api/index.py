import sys
import os
sys.path.insert(0, '/var/task')
os.chdir('/var/task')

from app import app

application = app
