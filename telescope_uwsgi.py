"""
This is the file necessary for using Telescope with UWSGI (recommended configuration).

To run, run the command: uwsgi --ini uwsgi.ini
"""

import telescope
#import logging
#import logging.handlers

#syslogh = logging.handlers.SysLogHandler()
#logging.getLogger().addHandler(syslogh)
#logging.getLogger().setLevel(logging.DEBUG)

application = telescope.go()

