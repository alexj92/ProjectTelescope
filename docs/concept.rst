Concept behind Telescope
========================

The first version of Telescope was written in a few short days by lukegb as a replacement for Ocelot.

Why Python?
-----------
We'd been having issues with the C++ Ocelot randomly overwriting internal variables, and then
starting to burp when presented with connections for longer than about two hours.

We needed a replacement and fast!

What does this have for me over Ocelot?
---------------------------------------
* Cleaner, more documented (like what you're reading now).
* Greater degree of abstraction from backend storage.
* Storage redundancy with uWSGI_.
* IPv6 support (note: this doesn't require the tracker to be accessible over IPv6).
* Supports non-compact announces (:func:`telescope.handler.format_normal`).

.. _uWSGI: http://projects.unbit.it/uwsgi/