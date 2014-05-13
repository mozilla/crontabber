Backfillable Jobs
=================


What is backfilling?
--------------------

Backfilling is basically a ``crontabber`` app that receives a date to its
``run()`` function. For example:

.. code-block:: python

    import datetime
    from crontabber.base import BaseCronApp
    from crontabber.mixins import as_backfill_cron_app

    @as_backfill_cron_app
    class MyBackfillApp(BaseCronApp):
        app_name = 'my-backfill-app'

        def run(self, date):
            with open(self.app_name + '.log', 'a') as f:
                f.write('Date supplied: %s\n' % date)

The ``date`` parameter is a Python ``<datetime.datetime>`` instance variable
with timezone information.

What ``crontabber`` guarantees is that that method will never be called
with the same ``date`` value twice.

The point of all this is if the app was to fail, it will be retried
automatically by ``crontabber`` and when it does that needs to know exactly
what dates have been tried before.

An example explains it
----------------------

Suppose that you have a stored procedure in a PostgreSQL database. It needs
to be called exactly once every day. Internally the stored procedure is
programmed to raise an exception if the same day is supplied twice. For
  example it might do something like this:

.. code-block:: sql

    CREATE OR REPLACE FUNCTION cleanup(report_date DATE)
        RETURNS boolean
        LANGUAGE plpgsql
    AS $$
    BEGIN

    SELECT 1 FROM reports_clean
    WHERE report_date = report_date;
    IF FOUND THEN
        RAISE ERROR 'Already run for %.',report_date;
        RETURN FALSE;
    END IF;

    INSERT INTO reports_clean (
        name, sex, dob, report_date
    )
    SELECT
        name, sex, dob, report_date
    FROM ( SELECT
               TRIM(both ' ' from full_name)
               gender,
               date_of_birth::DATE
           FROM data_collection
           WHERE
               collection_date = report_date
               AND
               gender = 'male' OR gender = 'female'
    );

    RETURN TRUE;
    END;
    $$;

The example is not a real-world example but it demonstrates the importance
of really making sure the same date isn't passed into the function twice.
If it was, you'd have duplicates for a particular date and that would be bad.


When does the magic kick in?
----------------------------

When things go wrong. If for example, you have some network outtage or a
bug in your code or something then the triggering will cause an error.
That's OK because ``crontabber`` will catch that and take note of exactly
what date it tried to pass in.

Then, the next time ``crontabber`` runs it will re-attempt to execute the
job app with the same date, even if the wall clock says it's the next day.
It will also know which other days it has not been able to execute and
re-attempt those too.

Suppose you have a daily app that is configured to be backfillable. The app
depends on presence of some external third party service which
unfortunately goes offline for three days. It's not a problem, ``crontabber``
will try and try till it works and will accordinly pass in the correct dates.


A caveat about backfillable jobs
--------------------------------

Because the integrity of which apps have been passed with which dates is
important, it means you can't use ``crontabber`` to run an individual job as
a "one off". That means that if you try::

    crontabber --admin.conf=crontabber.ini --job=my-backfill-app

It will deliberately ignore that since there's a risk it then "disrupts" its
predictable rythem. Otherwise it could potentially be calling the same app
with the same date twice.
