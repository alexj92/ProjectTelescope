"""
This file loads the telescope configuration from telescope_config and also provides telescope.go.

telescope.go currently only returns bottle's default_app()
"""

import telescope.plugins.abstract
import os

from telescope_config import CONFIG

# include the correct storage class
storage_package = CONFIG['storage'].split('.', 2)[0]
storage_class = CONFIG['storage'].split('.', 2)[1]
m = __import__('telescope.storage.%s' % (storage_package,))
m = getattr(m.storage, storage_package)

STORAGE = getattr(m, storage_class)(CONFIG['storage config'])
STORAGE.load_data()

# plugin system
from yapsy.PluginManager import PluginManager
# Build the manager
pluginManager = PluginManager()
# Tell it the default place(s) where to find plugins
myPath = os.path.dirname(__file__)
modulePath = os.path.join(myPath, "plugins")
pluginManager.setPluginPlaces([modulePath])
# Tell it about our categories
pluginManager.setCategoriesFilter({
    'WebPlugin': telescope.plugins.abstract.ITelescopeWebPlugin,
    'AnnouncePlugin': telescope.plugins.abstract.ITelescopeAnnouncePlugin
})
# Load all plugins
pluginManager.collectPlugins()

# Activate all loaded plugins
for pluginInfo in pluginManager.getAllPlugins():
   pluginManager.activatePluginByName(pluginInfo.name)

PLUGIN_MANAGER = pluginManager

def go():
    import bottle

    import telescope.handler

    return bottle.default_app()
