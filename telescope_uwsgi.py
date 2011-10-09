"""
This is the file necessary for using Telescope with UWSGI (recommended configuration).

To run, run the command: uwsgi --ini uwsgi.ini
"""

import telescope

application = telescope.go()
