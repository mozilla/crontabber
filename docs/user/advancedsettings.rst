Advanced settings
=================

All configuration in ``crontabber`` is handled by the fact that it's built
on top of `configman`_. ``configman`` is agnostic to configuration file
format (e.g. ``.ini`` or ``.json``) and that means you can reference much more
than just strings and integers. For example, you can reference Python
classes by their name and they get imported automatically when need be.

We strongly recommend that when you write a ``crontabber`` app that you
set a sensibile default and only use a configuration file when you
need to override it. Sometimes you can't put in a sensible default as
the value can't be written in code. Like a password for example.

Setting up settings
-------------------

The trick to adding configuration is to set a class attribute on your
``crontabber`` app called ``required_config``. Let's dive straight
into an example:

.. code-block:: python

    import datetime
    from crontabber.base import BaseCronApp
    from configman import Namespace

    class MyFirstConfigApp(BaseCronApp):
        app_name = 'my-first-config-app'

        required_config = Namespace()
        required_config.add_option(
            'date_format',
            default='%m/%d %Y - %H:%M',
            doc="Format for how the date is reported in the log file."
        )

        def run(self):
            with open(self.app_name + '.log', 'a') as f:
                dt = datetime.datetime.now()
                f.write('Now is %s\n' % dt.strftime(self.config.date_format))


The magic to notice is how you import ``Namespace`` from ``configman``,
create a class attribute called ``required_config`` and then inside the
``run()`` method you can reference to by ``self.config.date_format``.

Overriding settings
-------------------

So, there are now two ways of overriding this other than letting the
default value play. You can either do it in your existing configuration
file (``crontabber.ini`` if you've played along from the
:doc:`Introduction </user/intro>`) or you can do it right on the
command line as local environment variables.

If you intend to use non-trivial notation for environment variables in bash
you have to prefix the command with a program called ``env`` that is
built in on almost all version of bash. So, here's an example of doing
just that::

    env crontabber.class-MyFirstConfigApp.date_format="%A" crontabber --admin.conf=crontabber.ini

Run that and you'll notice it picked up the override setting.

Another way of specifying this is in your ``crontabber.ini`` file. Note!
Setting this requires that you do it under the ``[crontabber]`` section
heading. It looks like this::

    ...

    [crontabber]

        ...

        [[class-MyFirstConfigApp]]

            # Format for how the date is reported in the log file.
            date_format=%W %y %h:%M

If you ever forget this notation, after you have added some setting options
you can run::

    crontabber --admin.conf=crontabber.ini --admin.print_conf=ini

and look at the commented out examples.

Now, run it again and it should pick this up. Now you don't need to specify
anything extra on the command line, so you can use::

    crontabber --admin.conf=crontabber.ini

Let's now make a setting that is something the app needs to
import (as a Python module, class or function) on the fly. Let's say
we want override what function our simple app uses to generate the datetime.
So we add another config called ``date_function`` and tell the config that
this is something it needs to import:

.. code-block:: python

    import datetime
    from crontabber.base import BaseCronApp
    from configman import Namespace

    class MyFirstConfigApp(BaseCronApp):
        app_name = 'my-first-config-app'

        required_config = Namespace()
        required_config.add_option(
            'date_format',
            default='%m/%d %Y - %H:%M',
            doc="Format for how the date is reported in the log file."
        )
        required_config.add_option(
            'date_function',
            default=datetime.datetime.now,
            doc="Function that generates datetime instance"
        )

        def run(self):
            with open(self.app_name + '.log', 'a') as f:
                dt = self.config.date_function()
                f.write('Now is %s\n' % dt.strftime(self.config.date_format))


Configman automatically notices that the default isn't a string but something
pythonic that it can use. But if you want to change that, in a
``crontabber.ini`` file you have to reference it as a string. How do you do
that? This trick isn't for the faint of heart but it's very powerful one.
What you do is you write a ``from_string_converter`` function.

Mind you, this is a rather odd and complicated example but it shows the
power of being able to change anything from a config file:


.. code-block:: python

    import datetime
    from crontabber.base import BaseCronApp
    from configman import Namespace

    def function_converter(function_reference):
        module, callable, function = function_reference.rsplit('.', 2)
        module = __import__(module, globals())
        callable = getattr(module, callable)
        return getattr(callable, function)

    class MyFirstConfigApp(BaseCronApp):
        app_name = 'my-first-config-app'

        required_config = Namespace()
        required_config.add_option(
            'date_format',
            default='%m/%d %Y - %H:%M',
            doc="Format for how the date is reported in the log file."
        )
        required_config.add_option(
            'date_function',
            default=datetime.datetime.now,
            doc="Function that generates datetime instance",
            from_string_converter=function_converter
        )

        def run(self):
            with open(self.app_name + '.log', 'a') as f:
                dt = self.config.date_function()
                f.write('Now is %s\n' % dt.strftime(self.config.date_format))


Now, let's try this out on the command line::

    env crontabber.class-MyFirstConfigApp.date_function="datetime.datetime.utcnow"\
    crontabber --admin.conf=crontabber.ini

The `documentation on configman`_ has more examples of using the
``from_string_converter``.


.. _configman: https://github.com/mozilla/configman
.. _documentation on configman: http://configman.readthedocs.org/en/latest/typeconversion.html
