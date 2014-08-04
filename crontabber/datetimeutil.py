import datetime

ZERO = datetime.timedelta(0)


class UTC(datetime.tzinfo):
    """
    UTC implementation taken from Python's docs.

    Used only when pytz isn't available.
    """

    def __repr__(self):  # pragma: no cover
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


def timesince(d, now):
    """
    Taken from django.utils.timesince and modified to simpler requirements.

    Takes two datetime objects and returns the time between d and now
    as a nicely formatted string, e.g. "10 minutes". If d occurs after now,
    then "0 minutes" is returned.

    Units used are years, months, weeks, days, hours, and minutes.
    Seconds and microseconds are ignored. Up to two adjacent units will be
    displayed. For example, "2 weeks, 3 days" and "1 year, 3 months" are
    possible outputs, but "2 weeks, 3 hours" and "1 year, 5 days" are not.

    Adapted from
    http://web.archive.org/web/20060617175230/\
    http://blog.natbat.co.uk/archive/2003/Jun/14/time_since
    """
    def pluralize(a, b):
        def inner(n):
            if n == 1:
                return a % n
            return b % n
        return inner

    def ugettext(s):
        return s

    chunks = (
        (60 * 60 * 24 * 365, pluralize('%d year', '%d years')),
        (60 * 60 * 24 * 30, pluralize('%d month', '%d months')),
        (60 * 60 * 24 * 7, pluralize('%d week', '%d weeks')),
        (60 * 60 * 24, pluralize('%d day', '%d days')),
        (60 * 60, pluralize('%d hour', '%d hours')),
        (60, pluralize('%d minute', '%d minutes')),
        (0, pluralize('%d second', '%d seconds'))
    )
    # Convert datetime.date to datetime.datetime for comparison.
    if not isinstance(d, datetime.datetime):
        d = datetime.datetime(d.year, d.month, d.day)
    if now and not isinstance(now, datetime.datetime):
        now = datetime.datetime(now.year, now.month, now.day)

    delta = now - d
    # ignore microseconds
    since = delta.days * 24 * 60 * 60 + delta.seconds
    if since <= 0:
        # d is in the future compared to now, stop processing.
        # We'll use the last chunk (highest granularity)
        _, name = chunks[-1]
        return name(0)
    for i, (seconds, name) in enumerate(chunks):
        if seconds > 0:
            count = since // seconds
            if count != 0:
                break
        else:
            count = since

    result = name(count)
    if i + 1 < len(chunks):
        # Now get the second item
        seconds2, name2 = chunks[i + 1]
        if seconds2 > 0:
            count2 = (since - (seconds * count)) // seconds2
        else:
            count2 = since - (seconds * count)
        if count2 != 0:
            result += ugettext(', ') + name2(count2)

    return result
