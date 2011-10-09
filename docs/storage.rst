Telescope's Storage System
==========================

The storage system is completely run by the telescope.storage module.

The abstract version of the storage engine looks like this:
.. autoclass:: telescope.storage.abstract.StorageAbstract
   :members:



Specifics
---------
Classes extend the StorageAbstract class and implement their own features atop it.

At the moment, only the gazellemongo.StorageGazelle class exists to provide a storage engine.

.. autoclass:: telescope.storage.abstract.StorageGazelle
   :members:
   