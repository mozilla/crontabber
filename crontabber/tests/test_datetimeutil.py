import datetime
import unittest

from nose.tools import eq_, ok_

from crontabber.datetimeutil import utc_now, timesince


class TestDatetimeUtils(unittest.TestCase):

    def test_utc_now(self):
        now = utc_now()
        ok_(now.tzinfo)

        dt = datetime.datetime.utcnow()
        eq_(now.tzinfo.tzname(dt), 'UTC')
        eq_(now.tzinfo.utcoffset(dt), datetime.timedelta(0))
        eq_(now.tzinfo.dst(dt), datetime.timedelta(0))

    def test_timesince(self):
        now = utc_now()
        then = now - datetime.timedelta(days=365)
        eq_(timesince(then, now), '1 year')
        then = now - datetime.timedelta(days=7)
        eq_(timesince(then, now), '1 week')
        then = now - datetime.timedelta(days=1)
        eq_(timesince(then, now), '1 day')
        then = now - datetime.timedelta(hours=1)
        eq_(timesince(then, now), '1 hour')
        then = now - datetime.timedelta(minutes=1)
        eq_(timesince(then, now), '1 minute')
        then = now - datetime.timedelta(seconds=1)
        eq_(timesince(then, now), '1 second')

        # more than one things
        then = now - datetime.timedelta(days=365 + 7)
        eq_(timesince(then, now), '1 year')
        then = now - datetime.timedelta(days=40)
        eq_(timesince(then, now), '1 month, 1 week')
        then = now - datetime.timedelta(days=2, seconds=60 * 60)
        eq_(timesince(then, now), '2 days, 1 hour')
        then = now - datetime.timedelta(days=2, seconds=60 * 60 * 2)
        eq_(timesince(then, now), '2 days, 2 hours')
        then = now - datetime.timedelta(hours=1, seconds=60)
        eq_(timesince(then, now), '1 hour, 1 minute')
        then = now - datetime.timedelta(hours=2, seconds=60 * 2)
        eq_(timesince(then, now), '2 hours, 2 minutes')
        then = now - datetime.timedelta(minutes=3, seconds=10)
        eq_(timesince(then, now), '3 minutes, 10 seconds')
        then = now - datetime.timedelta(seconds=1)
        eq_(timesince(then, now), '1 second')
        then = now - datetime.timedelta(seconds=0)
        eq_(timesince(then, now), '0 seconds')

    def test_timesince_oddballs(self):
        now = utc_now()
        then = now - datetime.timedelta(days=7)
        # compare two dates
        eq_(timesince(then.date(), now.date()), '1 week')
