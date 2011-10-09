"""
This file loads the telescope configuration from telescope_config and also provides telescope.go.

telescope.go currently only returns bottle's default_app()
"""

from telescope_config import CONFIG

# include the correct storage class
storage_package = CONFIG['storage'].split('.', 2)[0]
storage_class = CONFIG['storage'].split('.', 2)[1]
m = __import__('telescope.storage.%s' % (storage_package,))
m = getattr(m.storage, storage_package)

STORAGE = getattr(m, storage_class)(CONFIG['storage config'])
STORAGE.load_data()

def go():
    import bottle

    return bottle.default_app()
