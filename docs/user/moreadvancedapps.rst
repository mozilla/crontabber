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

``crontabber`` provides helpers for running apps that need a database
connection. You have two choices. Both helpers automatically take care
of closing the connection.

An example demonstrates two apps that uses these helpers:

.. code-block:: python

    from crontabber.base import BaseCronApp
    from crontabber.mixins import with_single_postgres_transactions

    @with_single_postgres_transactions()
    class MyFirstPostgresApp(BaseCronApp):
        app_name = 'my-first-postgres-app'

        def run(self):
            # this self.database_transaction_executor is a wrapper
            # that takes care of the postgres transaction closing
            # and closing the connection
            self.database_transaction_executor(
                self._execute_sql,
                "DELETE FROM some_temp_table"
            )

        def _execute_sql(self, connection, sql):
            cursor = connection.cursor()
            cursor.execute(sql)
            # Look ma! No need to commit the transaction
            # or worry about rolling back if something goes wrong

And here's another example where you have more control over the transaction
management but the helper will take care of closing the connection.:

.. code-block:: python

    from crontabber.base import BaseCronApp
    from crontabber.mixins import with_postgres_transaction

    @with_postgres_transactions()
    class MyFirstPostgresApp(BaseCronApp):
        app_name = 'my-first-postgres-app'

        def run(self, connection):
            cursor = connection.cursor()
            try:
                cursor.callproc('my_stored_procedure_function')
                connection.commit()
            except:
                connection.rollback()
                raise


Running command line jobs
-------------------------

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
