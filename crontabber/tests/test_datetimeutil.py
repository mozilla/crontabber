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
