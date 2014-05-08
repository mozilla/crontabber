Introduction
============

Quickstart
----------

To get started, install with `pip`::

    pip install crontabber

It installs all the dependencies you need.

Note if you're trying to install Python dependencies that rely on C bindings
on OSX Maverick not only do you need to have XCode installed, you might also
need to set::

    export CPPFLAGS=-Qunused-arguments
    export CFLAGS=-Qunused-arguments

Once it's installed it creates an executable called ``crontabber`` so you
should now be able to run::

    crontabber --help

The first thing you need to do is to create a config file. You do that with::

    crontabber --admin.dump_conf=crontabber.ini

That creates a file called ``crontabber.ini`` which you can open and get
familiar with. The file is big and possibly confusing as there are many
things you can change. The most important thing is to note that it shows
all default settings left commented out.

Before we can start writing our first app we need to set credentials to
connect to Postgres. Open your newly created ``crontabber.ini`` file and look
for the settings: ``database_name``, ``database_username`` and ``database_password``.
Perhaps you want to create a new database first to test against::

    createdb crontabber

Depending on how you have set up Postgres server you might need to supply a
username and password. Proceed to edit your ``crontabber.ini`` and set::

    database_name=crontabber
    database_username=myusername
    database_password=mypostgrespassword

You can see where the default settings are set and you can change those lines.
Let's try to see if it works::

    crontabber --admin.conf=crontabber.ini --list

You'll possibly see lots of logging on stdout but you shouldn't see any errors.

Great progress so far!

Creating your first app
-----------------------

The most important setting is the ``jobs`` setting. Let's create our first
job. First change the line ``#jobs=''`` to this::

    jobs='''
    jobs.myapp.MyFirstApp|5m
    '''

Now ``crontabber`` is going to need to do the equivalent of:

.. code-block:: python

    from jobs.myapp import MyFirstApp

So, let's create a very simple sample app::

    mkdir jobs
    touch jobs/__init__.py
    emacs jobs/myapp.py

So now we're creating our app (``myapp.py``). Let's start with this:

.. code-block:: python

    import datetime
    from crontabber.base import BaseCronApp

    class MyFirstApp(BaseCronApp):
        app_name = 'my-first-app'

        def run(self):
            with open(self.app_name + '.log', 'a') as f:
                f.write('Now is %s\n' % datetime.datetime.now())

And that's it! Let's try that it can be imported by opening a
python interpreter::

    $ python
    >>> from jobs.myapp import MyFirstApp

Because you created this job in current directory you're in and when you run
``crontabber`` it won't know which Python path that is referring to, so you're
going to need to add ``PYTHONPATH=.`` to the command line or you can, for now,
just run::

    export PYTHONPATH=.

Finally we're ready to run::

    crontabber --admin.conf=crontabber.ini --list

Since you've never run the job before you should see something like this::

    === JOB ========================================================================
    Class:          jobs.myapp.MyFirstApp
    App name:       my-first-app
    Frequency:      5m
    *NO PREVIOUS RUN INFO*

OK. Brace yourself, we're about to run ``crontabber`` for the first time::

    crontabber --admin.conf=crontabber.ini

Remember that our little app does. It creates a file called
``my-first-app.log``. Open that file and you should see something like::

    $ cat my-first-app.log
    Now is 2014-05-08 14:28:14.593252

Try running ``crontabber`` again, noticing that it's not been 5 minutes since
we last run it::

   crontabber --admin.conf=crontabber.ini

Did it write another line to ``my-first-app.log``? Try waiting more than
5 minutes and run again. You can run the above mentioned command as many times
as you like.

If you're curious how this state is remembered, you can open your database
and look at the two tables it created automatically::

    $ psql crontabber

    crontabber=# select * from crontabber;
    ...
    crontabber=# select * from crontabber_log;
    ...

Let's move on to write :doc:`More Advanced Apps </user/moreadvancedapps>`.
