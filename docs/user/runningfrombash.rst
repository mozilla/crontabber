Running from bash
=================


Locking
-------

.. note:: At the time of writing, ``crontabber`` **does not handle locking**.
This might change in the future.

Generally, locking is a standard bash task that is best described elsewhere.
However, this chapter should hopefully get you going in the right direction.

One example implementation of a lockfile is this:

.. code-block:: bash

    #!/bin/bash
    lockdir=/tmp/crontabber.lock
    if mkdir "$lockdir"
    then
        echo >&2 "successfully acquired lock"
        PYTHONPATH=. crontabber --admin.conf=crontabber.ini

        # Remove lockdir when the script finishes, or when it receives a signal
        trap 'rm -rf "$lockdir"' 0    # remove directory when script finishes

        # Optionally create temporary files in this directory, because
        # they will be removed automatically:
        tmpfile=$lockdir/filelist

    else
        echo >&2 "cannot acquire lock, giving up on $lockdir"
        exit 0
    fi

This means that if you have a job that sometimes takes longer than how
frequently your ``crontab`` runs, you won't run the risk of starting the
same job more than once.


crontab
-------

This is the heart of it all. Installing and setting up ``crontabber`` doesn't
run anything until you actually start running it yourself and the best way
to do that is with ``crontab``.

Before you set up your ``crontab`` it's recommended that you wrap this in a
shell script that takes care of paths and options and stuff. That means you
can keep your ``crontab`` clean and simple. Something like this should good
enough:

.. code-block:: bash

    */5 * * * * myuser /path/to/crontabber_wrapper.sh

And then you can put the actual execution in that one script. For example,
suppose you need a Python ``virtualenv``. Like this for example:

.. code-block:: bash

    #!/bin/bash
    source /home/users/django/venv/bin/active
    HOMEDIR=/home/users/django

    PYTHONPATH="$HOMEDIR/jobs" crontabber --admin.conf="$HOMEDIR/crontabber.ini"

There are many more things you can do and set up. The point is that you
basically do what you were able to do on the command line and freeze that into
one script that can be executed from anywhere.

You will probably also want to combine this with the section on Locking above.


Parallel crontabbers
--------------------

Suppose you have some jobs that take a reeeeeaaallly long time. Equally,
you might have
some jobs that are quick and needs to run often too. Because ``crontabber``
is single threaded running your jobs will block other jobs. This is a good
thing because it asserts that dependent jobs don't start until their
"parents" have finished successfully.

To prevent completely independent jobs from waiting for each other, you can run
multiple parallel instances of ``crontabber``. This means that you will need
to have two lines (or more) in ``crontab``. Here's an example:

.. code-block:: bash

    */5 * * * * myuser /path/to/crontabber_wrapper.sh A
    */5 * * * * myuser /path/to/crontabber_wrapper.sh B

And in your wrapper script you take that first parameter like this for example:

.. code-block:: bash

    PYTHONPATH="$HOMEDIR/jobs" crontabber \
      --admin.conf="$HOMEDIR/crontabber.$1.ini"

That means you need two config files:

* ``crontabber.A.ini``
* ``crontabber.B.ini``

You might think that means you have to duplicate things across two different
files. Thankfully that's not the case. See
:doc:`Advanced Configuration </user/advancedconfiguration>`.
