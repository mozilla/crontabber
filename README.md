# crontabber

A cron job runner with self-healing and job dependencies.

License: [MPL 2](http://www.mozilla.org/MPL/2.0/)

[![Coverage Status](https://coveralls.io/repos/mozilla/crontabber/badge.png)](https://coveralls.io/r/mozilla/crontabber)

[![Build Status](https://travis-ci.org/mozilla/crontabber.svg?branch=master)](https://travis-ci.org/mozilla/crontabber)

## How to run tests

First you need to create a dedicated test database. We recommend you call
it `test_crontabber`. Then you need the necessary credentials for it.

Before running the tests you need to install some extras to be able to
run tests at all:

```
pip install -r test-requirements.txt
```

Next, in the root directory of the project create a file called
`test-crontabber.ini` and it should look something like this:

```
[crontabber]
user=myusername
password=mypassword
dbname=test_crontabber
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

## How to do code coverage analysis

First you need to install the
[coverage](http://nedbatchelder.com/code/coverage/) module. Then, with
`nosetests`, you can run this:

```
PYTHONPATH=. nosetests --with-coverage --cover-erase --cover-html --cover-package=crontabber
```
After it has run, you can open the file `cover/index.html` in browser.

## How to run the exampleapp

The example app helps you set up a playground to play around with and
test crontabber to gain a better understanding of how it works.

The best place to start with is to read the `exampleapp/README.md` file
and go through its steps. Once you get the basics to work you can start
experimenting with adding your job classes.

## How locking works

crontabber supports locking. It basically means if you start a second
instance of crontabber whilst it's already ongoing in another terminal/server
the second one will exist early. This is only applicable if there is
an actual job ongoing.

There are two kinds of locking.

1. **General locking.** The first thing crontabber does before it starts
an app is to ask the state (stored in PostgreSQL) if it's ongoing and if
it is, it exists with an error code of `3`.

1. **Sub-second locking.** If the general locking (see point above) says
"No, the job is not ongoing", it's going to proceed to update the state
with a [row-level locking transaction in PostgreSQL](https://www.postgresql.org/docs/9.5/static/explicit-locking.html#LOCKING-ROWS).
That basically means PostgreSQL only allows one single `UPDATE` from
the process that gets there first. The second crontabber process will
will exit early with an error code of `2` if the first crontabber process
managed to run the `UPDATE` first.

Imagine two separate terminals starting crontabber at the almost same time:

```
# Terminal 1
$ python crontabber.py --admin.conf=crontabber.ini
$ echo $?
0
```
```
# Terminal 2 (started almost simultaneously)
$ python crontabber.py --admin.conf=crontabber.ini
$ echo $?
3
```

**Note!** If a job has been ongoing to a maximum period of time, the
locking is ignored. This is controlled by the config option
`crontabber.max_ongoing_age_hours` which defaults to **12 hours**.
This is applicable if crontabber, updates the state that it's starting
a job, then when it tries to update the state that it finished (successfully
or not) and that write fails, if for example it's unable to make a
connection to PostgreSQL. If this happens crontabber will just ignore
the lock and run it anyway.
