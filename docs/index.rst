.. crontabber documentation master file, created by
   sphinx-quickstart on Thu May  8 13:28:40 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

crontabber
==========

``crontabber`` is a cron job manager. Written in Python. Uses PostgreSQL for storage.

Killer features include:

* Retries jobs on failure automatically
* Dependency-aware, and won’t execute child jobs that depend on parents that
  have failed
* Nagios integration making it easy to monitor health of jobs

You start crontabber with ``crontab`` and internally it figures out which jobs
to run when and in what ideal order.

``crontabber`` requires Python 2.6 or Python 2.6 and PostgreSQL 9.2 or greater.



User Guide
----------

.. toctree::
   :maxdepth: 2

   user/intro
   user/moreadvancedapps
   user/nagios
   user/backfillablejobs
   user/runningfrombash
   user/advancedconfiguration
   user/advancedsettings


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
