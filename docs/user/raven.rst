Raven
=====

`raven`_ is a Python program for sending in Python exceptions as a message
to a `Sentry`_ server. Both as free and Open Source but Sentry exists as
a paid service if you don't want to self-host.

What `raven` does is that it makes it possible to package up a Python
exception (type, value, traceback) and send it in to a server. Once
the server receives it, it makes a hash of the error and adds an entry
to its database. If the same error is sent again, instead of logging
another entry to its database it increments the previous one.

Configure your API key
----------------------

To configure your `crontabber` to send all exceptions into a Sentry
server you need an API key. When you have that you add that to your
``crontabber.ini`` file. So it looks
something like this::

    [sentry]

    # DSN for Sentry via raven
    dsn=https://d3683ad...27f9fbd:0ce...4aeb810311dc@errormill.mozilla.org/14

Note, this is not mandatory. You can always reach the full error details
in the logs of the database. Either by interrogating the database table
yourself or by using the command like this::

    crontabber --admin.conf=crontabber.ini --list-jobs


Different protocols
-------------------

It's important to note that the protocol used by Sentry has changed in
recent years. That means that you need to be careful with what version
of ``raven`` you install. If you have an older version of Sentry you
can not install the latest version of ``raven`` because the messages it
transmits won't be understood.

.. _raven: https://github.com/getsentry/raven-python
.. _Sentry: https://getsentry.com/
