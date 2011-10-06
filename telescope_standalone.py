import telescope
import bottle

application = telescope.go()
bottle.debug(True)
bottle.run(host='0.0.0.0', port=9633, reloader=True)
