Command line options
====================

This chapter aims to digest some of the command line options
available in ``crontabber``.

One of the important command line options is that on ``--nagios``
which we explored in its :doc:`own chapter </user/nagios>`.


``--configtest``
----------------

If you change the config file it's always a highly recommended and good
idea to first run::

    crontabber --admin.conf=crontabber.ini --configtest

first. It checks that you haven't made any trivial errors in the config
file that will not get caught until it's too late.

It's important to remember that this basically only checks the ``jobs``
setting. But if you have some other typo or corruption anywhere in
your files it might catch it simply because it's unable to load up
the ``jobs`` setting at all.

When it validates the ``jobs`` setting it checks:

1. That the job can be found and imported

2. That the frequency is a valid frequency (e.g. ``2d`` is valid ``2r`` is not)

3. That the time (clock time the job should fire) is a valid time.

4. If a job has a less than daily frequency that a time is not set.

Running this should exit the application with an exit code ``0`` if all
is well. If not the exit code will be a count of how many apps are
misconfigured.

``--reset-job=``
---------------

This keyword parameter option is pretty self explanatory. It resets the
job and basically pretends the job has never run. Just like the state
database didn't know about it before before it was ever run the first time.

It's important to note that this does not clean out the mentioned job
from the logs.

You can either specify the ``app_name`` or the notation that specifies
the location of the app class. For example::

    crontabber --admin.conf=crontabber.ini --reset-job=my-first-app

Or::

    crontabber --admin.conf=crontabber.ini --reset-job=jobs.myapp.MyFirstApp

If you reset a job that has already been reset nothing happens.


``--job=`` and ``--force``
--------------------------

Sometimes you just know a particular job needs to be run here and now.
You can obviously do this outside of ``crontabber`` but suppose the
app you have written has a fair amount of business logic in it and
not just a wrapper around something written elsewhere.

The notation is pretty straight forward as you can guess::

    crontabber --admin.conf=crontabber.ini --job=my-first-app

or::

    crontabber --admin.conf=crontabber.ini --job=my-first-app

However, this will still check if the job is ready to run next. Suppose
a job is not due to run for another hour, then typing in this command
the job **will not be run** straight away. There's also another chance
that the job you're trying to run has a blocking dependency (ie. a job
it depends on failed last time).

If you really want to run it now and can't wait, add ``--force`` like this::

    crontabber --admin.conf=crontabber.ini --job=my-first-app --force

There is an important limitation of this command line option. It **does
not work with backfill apps**. Because backfill apps are very sensitive
about exactly when they run they simply ignore both the ``--job=`` and
even the ``--force`` parameter.


``--version``
-------------

Spits out the version of ``crontabber`` on standard out.
