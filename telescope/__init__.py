from telescope_config import CONFIG

# include the correct storage class
storage_package = CONFIG['storage'].split('.', 2)[0]
storage_class = CONFIG['storage'].split('.', 2)[1]
m = __import__('telescope.storage.%s' % (storage_package,))
m = getattr(m.storage, storage_package)

STORAGE = getattr( m, storage_class )(CONFIG['storage config'])
STORAGE.load_data()

def go():
    import bottle
    import telescope.handler
    
    return bottle.default_app()
