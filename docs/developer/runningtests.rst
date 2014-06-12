Running tests
=============

nosetests
---------

All the dependencies you need to be able to run tests are encapsulated
in the `test-requirements.txt <https://github.com/mozilla/crontabber/blob/master/test-requirements.txt>`_
file. First install that into your virtualenv::

    pip install -r test-requirementst.txt

You also need to create a dedicated PostgreSQL database that you can run
the tests against. And you also you need to be able to connect to this
database. So you need the username and password.

Next, in the root directory of the project create a file called
``test-crontabber.ini`` and it should look something like this::


    [crontabber]
    user=myusername
    password=mypassword
    dbname=test_crontabber

To start all the tests run::

    PYTHONPATH=. nosetests

If you want to run a specific test in a specific file in a specific class
you can define it per the ``nosetests`` standard like this for example::

    PYTHONPATH=. nosetests tests crontabber/tests/test_crontabber.py:TestCrontabber.test_basic_run_job

If you want the tests to stop as soon as the first test fails add ``-x`` to
that same command above.

Also, if you want ``nosetests`` to *not* capture ``stdout`` add ``-s`` to that
same command as above.

Example project
---------------

The ``exampleapp`` project helps you set up a playground to play around with and
test ``crontabber`` to gain a better understanding of how it works.

The best place to start with is to read the
`exampleapp/README.md <https://github.com/mozilla/crontabber/blob/master/exampleapp/README.md>`_
file
and go through its steps. Once you get the basics to work you can start
experimenting with adding your job classes.
