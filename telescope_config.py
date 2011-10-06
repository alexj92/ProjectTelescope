CONFIG = {
	'storage': 'gazellemongo.StorageGazelle',
	'storage config': { 'connection': ('localhost', 27017), 'database': 'telescope', 'backend': {'host': 'localhost', 'user': 'telescope', 'passwd': 'epocselet', 'db': 'telescope'} },

	'announce interval': 900,
	'min interval': 900,
}

try:
	import private_config
	CONFIG.update(private_config.CONFIG)
except ImportError:
	pass
