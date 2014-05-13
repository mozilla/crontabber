More Advanced Apps
==================

This documentation carries on the :doc:`Quickstart </user/intro>`.

Apps with dependencies
----------------------

When you wrote your first app (``jobs.myapp.MyFirstApp``) you had to set
an ``app_name`` on the class. That's how you reference other apps when setting
up dependency management. This is important to note. The name of the Python
file or the name of class does not matter.

Diving in, let's now create two more apps. For simplicity we can continue
in the file ``myapp.py`` you created. Add this::

.. code-block:: python

    class MySecondApp(BaseCronApp):
        app_name = 'my-second-app'
        depends_on = ('my-first-app',)  # NOTE!

        def run(self):
            with open(self.app_name + '.log', 'a') as f:
                f.write('Second app run at %s\n' % datetime.datetime.now())

Exactly where you add this app doesn't really matter. Before or after or even
in a different file. All the matters is the ``app_name`` attribute and
the ``depends_on``. It event doesn't matter which order you place it in
your ``crontabber.ini``'s ``jobs`` setting. You can change your
``crontabber.ini`` to be like this::

    jobs='''
    jobs.myapp.MySecondApp|1h
    jobs.myapp.MyFirstApp|5m
    '''

``crontabber`` reads the ``jobs`` setting but when there's dependency linking
apps, even though it reads the ``jobs`` setting from top to bottom, it knows
that ``jobs.myapp.MySecondApp`` needs to be run **after** ``jobs.myapp.MyFirstApp``.

Go ahead and try it::

    crontabber --admin.conf=crontabber.ini

If you now look at the timestamps in ``my-first-app.log`` and ``my-second-app.log``
are in the correct order according to the dependency linkage rather than the
order they are written in the ``jobs`` setting.

Another important thing to appreciate is that if a job fails for some reason,
i.e. a python exception is raised, it will stop any of the **dependening jobs
from running**. Basically, if job ``B`` depends on job ``A``, job ``B`` will not
run until job ``A`` ran without a failure. Basically, ``crontabber`` not only
makes sure the order is correct, it also guards from running dependents if
their "parent" fails.

About the job frequency
-----------------------

In the above example note the notation used for the ``jobs`` setting.
It's ``python.module.and.classname|5m`` or ``python.module.and.classname|1h``.

The frequency is pretty self explanatory. ``5m`` means **every 5 minutes**
and ``1h`` means **every hour**. The other thing you could use is, for example,
``3d`` meaning **every 3 days**.


Running at specific times
-------------------------

Suppose you have a job that is really intensive and causing a lot of stress
in your server. Then you might want to run that "at night" (in quotes because
it means different things in different parts of the world) or whenever you
have the least load in your server.

The way to specify time is to write it in ``HH:MM`` notation on a 24-hour
clock. E.g. ``22:30``.

The way you specify the time is to add it to the ``jobs`` second like this
example shows::

    jobs='''
    jobs.myapp.MyBigFatWeddingApp|2d|21:00
    ```

But here's a very important thing to remember. The timezone is that of your
**PostgreSQL server**. Not the timezone of your server.
However, when you install PostgreSQL it will take the timezone from your
server's timezone. So if you have a server on the US west coast, the default
timezone will be ``US/Pacific``.

However, you can, and it's a good idea to do, change the timezone of your
PostgreSQL server. So if you have set your PostgreSQL server to ``UTC`` and
the ``crontabber`` will adjust these times in ``UTC`` time.


Postgres specific apps
----------------------

``crontabber`` provides several class decorators to make use of postrges
easier within a crontabber app.  These decorators can imbue your app class
with the correct configuration to automatically connect with Postgres and
handle transactions automatically.  The three decorators provide differing
levels of automation so that you can choose how much control you want.

@with_postgres_transactions()
.............................

This decorator tells crontabber that you want to use postgres by adding to
your class two class attributes: ``self.database_connection_factory`` and
``self.database_transaction_executor``.  When execution reaches your run
method, you may use these two attributes to talk to postgres.  If you want
a connection to Postgres you can grab one from the
``database_connection_factory`` and use it as a context manager:

.. code-block:: python

    # ...
    with self.database_connection_factory() as pg_connection:
        cursor = pg_connection.cursor()

The connection that you get from the factory is a psycopg2 connection,
so you have all the resources of that module available for use with your
connection.  You don't have to worry about opening or closing the connection,
the contextmananger will do that for you.  The connection is open and ready
to use when it is handed to you, and is closed when the context ends.  You are
responsible for transactions within the lifetime of the context.

If you want help with transactions, there is also a the
``database_transaction_executor`` at your service.  Give it a function that
accepts a database connection as its first argument, and it will execute the
function within a postgres transaction.   If your function ends normally (with
or without a return value), the transaction will be automatically committed.
If an exception is raised and that exception escapes outside of your function,
then the transaction will be automatically rolled back.

.. code-block:: python

    @with_postgres_transactions()
    class MyPGApp(BaseCronApp):
        def execute_lots_of_sql(connection, sql_in_a_list):
            '''run multiple sql statements in a single transaction'''
            cursor = connection.cursor()
            for an_sql_statement in sql_in_a_list:
               cursor.execute(an_sql_statement)

        def run(self):
            sql = [
                'insert into A (a, b, c) values (2, 3, 4)”,
                'update A set a=26 where b > 11',
                'drop table B'
            ]
            self.database_transaction_executor(
                execute_lots_of_sql,
                sql_in_a_list
            )

@with_postgres_connection_as_argument()
.......................................

This decorator is to be used in conjunction with the previous decorator.  When
using this decorator, your run method must be declared with a database
connection as its first argument:

.. code-block:: python

    @with_postgres_transactions()
    @with_postgres_connection_as_argument()
    class MyCrotabberApp(BaseCronApp):
        app_name = 'postgres-enabled-app'
        def run(self, connection):
            # the connection is live and ready to use
            cursor = connection.cursor()
            # ...

With this decorator, the database connection is handed to you.  You don't
have to get it yourself.  You don't have to worry about closing the connection,
it will be closed for you when your 'run' function ends.  However, you are
still responsible for your own transactions: you must explicitly use 'commit'
or 'rollback'.  If you do not 'commit' your changes, they will be lost when
the connection gets closed at the  end of your function.

You still have the transaction manager available if you want to use it.  Note,
however, that it will acquire its own database connection and not use the one
that was passed into your run function.  Don't deadlock yourself.

@with_single_postgres_transaction()
...................................

This decorator gives you the most automation.  It considers your entire run
function to be a single postgres transaction.  You're handed a connection
through the parameters to your run function.  You use that connection to
accomplish database stuff.  If your run function exits normally, the 'commit'
will happen automatically.  If your run function exits with a Exception
being raised, the connection will be rolled back automatically.

.. code-block:: python

    @with_postgres_transactions()
    @with_single_postgres_transaction()
    class MyCrotabberApp(BaseCronApp):
        app_name = 'postgres-enabled-app'

        def run(self, connection):
            # the connection is live and ready to use
            cursor = connection.cursor()
            cusor.execute('insert into A (a, b, c) values (11, 22, 33)')
            if bad_situation_detected():
                raise GetMeOutOfHereError()

In this example, connections are as automatic as we can make them.
If the exception is raised, the insert will be rolled back.  If the exception
is not raised and the 'run' function exits normally, the insert will be committed.

@with_subprocess
----------------

``crontabber`` is all Python but some of the tasks might be something other
than Python. For example, you might want to run ``rm /var/logs/oldjunk.log``
or something more advanced.

What you do then is use the ``with_subprocess`` helper.
When you use this helper on your application class, you can use
``self.run_process()`` and it will return a tuple of exit code, stdout, stderr.
This example shows how to use it:

.. code-block:: python

    from crontabber.base import BaseCronApp
    from crontabber.mixins import with_subprocess

    @with_subprocess
    class MyFirstCommandlineApp(BaseCronApp):
        app_name = 'my-first-commandline-app'

        def run(self):
            command = 'rm -f /var/logs/oldjunk.log'
            exit_code, stdout, stderr = self.run_process(command)
            if exit_code != 0:
                self.config.logger.error(
                    'Failed to execute %r' % command,
                )
                raise Exception(stderr)
