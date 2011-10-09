Getting Started with Telescope
==============================

This example will use the :class:`gazellemongo.StorageGazelle`!

Getting the bits together
-------------------------

This is my recommended Telescope setup:
* `Nginx <http://nginx.org/>` (version with built-in `uWSGI <http://projects.unbit.it/uwsgi/>` support)
* `uWSGI <http://projects.unbit.it/uwsgi/>`
* `Supervisor <http://supervisord.org/>`
* `MongoDB <mongodb.org>`

Configuring Telescope
---------------------

Configuring Telescope is really easy.

Create a file called ``private_config.py`` (this is excluded from being committed by git) with the following content::

    CONFIG = {
        'storage': 'gazellemongo.StorageGazelle',
        'storage config': {'connection': ('localhost', 27017), 'database': 'telescope',
                           'backend': {'host': 'localhost', 'user': 'telescope', 'passwd': 'epocselet', 'db': 'telescope'}},

        'announce interval': 900,
        'min interval': 900
    }

Then modify to your liking.

With :class:`gazellemongo.StorageGazelle`, you need to run master.py to sync MySQL with MongoDB. You also (obviously)
need to actually be running MongoDB!

Putting it all together
-----------------------

Supervisord
~~~~~~~~~~~
Firstly, configure supervisord to autorestart the uWSGI workers as well as the master process:

.. code-block:: ini

    [program:telescopemaster]
    autorestart=true
    command=/usr/local/bin/python /home/telescope/telescope/master.py
    directory=/home/telescope/telescope/
    numprocs=1
    environment=PYTHON_EGG_CACHE=/tmp
    user=telescope

    [program:telescopeuwsgi]
    autorestart=true
    command=/usr/local/bin/uwsgi --ini /home/telescope/telescope/uwsgi.ini
    directory=/home/telescope/telescope/
    numprocs=1
    environment=PYTHON_EGG_CACHE=/tmp
    user=telescope


nginx
~~~~~
Set up nginx to talk to Telescope:

.. code-block:: nginx

    server {
            listen 1.2.3.4:34000;
            server_name tracker.xyz.net;

            location / {
                    include uwsgi_params;
                    uwsgi_pass 127.0.0.1:3031;
            }

    }

Starting it up
~~~~~~~~~~~~~~
Now simply start up:
1. MySQL
2. MongoDB
3. Supervisor
...and you're done!