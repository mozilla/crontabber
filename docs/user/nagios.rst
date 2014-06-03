Nagios reporting
================


What is Nagios reporting?
-------------------------

`Nagios`_ is a common system administration tool for doing system health
checks. It works by a central node continually asking questions about
"various parts". These parts can be scripts. The scripts have a simple
protocol that they have to adhere to; it's the exit code these scripts
exit on.

* 0 - everything is fine
* 1 - warning (don't get out of bed)
* 2 - critical (things are on fire!)

The script also has an opportunity to emit a message. It does this by emitting
a single line on ``stdout`` followed by a newline. The convention is to
prefix the message according to the exit code. For example::

    $ ./is-everything-ok.sh
    OK - Everything is fine!
    $ echo $?
    0

    $ ./is-everything-ok.sh
    WARNING - This could get very bad!
    $ echo $?
    1

    $ ./is-everything-ok.sh
    CRITICAL - Call the fire department!
    $ echo $?
    2


How ``crontabber`` can be a Nagios script
-----------------------------------------

This is very simple. You simply use the ``--nagios`` parameter. Like this::

    crontabber --admin.conf=crontabber.ini  --nagios


The rules for which exit code to exit on are fairly simple. However, you
need to understand a bit more about
:doc:`Backfillable Jobs </user/backfillablejobs>`.

If no application in your configuration has errored in the last run
the exit code is simply ``0`` ("OK").

If any of your applications that is **not** a backfillable job has errored
the exit code is ``2`` ("CRITICAL").

Suppose you have a backfillable job and it has only errored **once**, then the
exit code is ``1`` ("WARNING").

Suppose you get a ``1`` or a ``2`` then the message that is printed on
``stdout`` will look like this for example::

    CRITICAL - my-first-app (MyFirstApp) | <type 'exceptions.OSError'> | [Errno 13] Permission denied: '/etc'

If you have multiple apps that have failed, the messages (like the example
above) will be concatenated with a ``;`` character so it's all one long line.

.. _Nagios: http://www.nagios.org/
