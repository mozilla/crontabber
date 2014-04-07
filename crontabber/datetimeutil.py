import datetime

ZERO = datetime.timedelta(0)


class UTC(datetime.tzinfo):
    """
    UTC implementation taken from Python's docs.

    Used only when pytz isn't available.
    """

    def __repr__(self):
        return "<UTC>"

    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO


def utc_now():
    """Return a timezone aware datetime instance in UTC timezone

    This funciton is mainly for convenience. Compare:

        >>> from datetimeutil import utc_now
        >>> utc_now()
        datetime.datetime(2012, 1, 5, 16, 42, 13, 639834,
          tzinfo=<isodate.tzinfo.Utc object at 0x101475210>)

    Versus:

        >>> import datetime
        >>> from datetimeutil import UTC
        >>> datetime.datetime.now(UTC)
        datetime.datetime(2012, 1, 5, 16, 42, 13, 639834,
          tzinfo=<isodate.tzinfo.Utc object at 0x101475210>)

    """
    return datetime.datetime.now(UTC())
