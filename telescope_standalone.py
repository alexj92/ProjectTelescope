"""
This allows fast debugging of ProjectTelescope.

It is NOT suitable for running in production. Don't try it, please.
"""

import telescope
import bottle

application = telescope.go()
bottle.debug()
bottle.run(host='0.0.0.0', port=9633, reloader=True)
