# crontabber

A cron job runner with self-healing and job dependencies.

License: [MPL 2](http://www.mozilla.org/MPL/2.0/)

## How to run tests

First you need to create a dedicated test database. We recommend you call
it `test_crontabber`. Then you need the necessary credentials for it.

Next, in the root directory of the project create a file called
`test-crontabber.ini` and it should look something like this:

```
[crontabber]
database_username=myusername
database_password=mypassword
database_name=test_crontabber
```

To start all the tests run:

```
PYTHONPATH=. nosetests
```

If you want to run a specific test in a specific file in a specific class
you can define it per the `nosetests` standard like this for example:

```
PYTHONPATH=. nosetests tests crontabber/tests/test_crontabber.py:TestCrontabber.test_basic_run_job
```

If you want the tests to stop as soon as the first test fails add `-x` to
that same command above.

Also, if you want `nosetests` to *not* capture `stdout` add `-s` to that
same command as above.
