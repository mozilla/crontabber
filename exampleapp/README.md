1. To run this example, you need to first generate a crontabber.ini
   file. You do that with::

   python ../crontabber/app.py --admin.print_conf=ini > crontabber.ini

2. Now you need to edit crontabber.ini. It can be quite scary.
   The first two things to do are:

   1. Find the settings `dbname`, `user`,
   `password` etc. and uncomment them accordingly.

   2. The `jobs` setting is the most important one. For now, change it
   to `foo.FooCronApp|10m`

3. Run it!

    PYTHONPATH=. python ../crontabber/app.py --admin.conf=crontabber.ini

4. This should now have written something to a file called `foo.log` (see
    the source code of `foo.py`).
   Also, this should write something to the table `crontabber` and
   `crontabber_log` in your database.
