import datetime, pytz
import re
import tzlocal

def date2human(when, slack_secs=180):
    """ Convert timestamp to human-friendly times, like '3 minutes ago' """
    if not when:
        return None
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    diff = now-when
    secs = diff.seconds
    days = diff.days
    if days > 0:
        return str(when)
    if secs >= 3600:
        if (secs<7200):
            return '1 hour ago'
        else:
            return str(secs/3600)+' hours ago'
    else:
        if (secs <slack_secs):
            return 'a moment ago'
        else:
            return str(secs/60)+' minutes ago'

def human2date(when, past=True):
    """UTC timestamps from human 'encoding' like '2 hours ago'.  Human
       timestamps are relative to local time zone."""
    # This is not millisecond precise...
    local_tz = tzlocal.get_localzone()
    now = datetime.datetime.now().replace(tzinfo=local_tz)
    utcnow = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

    if when == 'now':
        return utcnow
    if when == 'today':
        want = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if not past:
            want += datetime.timedelta(days=1)
        newtime = utcnow-(now-want)
        return newtime
    if when == 'yesterday':
        want = now.replace(hour=0, minute=0, second=0, microsecond=0)
        newtime = utcnow-(now-want)
        return newtime-datetime.timedelta(days=1)

    in_past = in_future = False
    if when.endswith(' ago'):
        in_past = True
    if when.startswith('in ') or when.startswith('after '):
        in_future = True

    if in_past and in_future:
        raise TypeError('Time cannot be in the past and in the future')

    r = re.compile('(\d+) days?( ago)?')
    m = r.match(when)
    if m:
        td = datetime.timedelta(days=float(m.group(1)))
        return utcnow-td
    r = re.compile('(\d+) hours?( ago)?')
    m = r.match(when)
    if m:
        td = datetime.timedelta(hours=float(m.group(1)))
        return utcnow-td
    r = re.compile('(\d+) minutes?( ago)?')
    m = r.match(when)
    if m:
        td = datetime.timedelta(minutes=float(m.group(1)))
        return utcnow-td

    formats = ['%H:%M']
    for fmt in formats:
        try:
            td = datetime.datetime.strptime(when, fmt).replace(tzinfo=local_tz)
            new = now
            if '%H' in fmt:
                new = new.replace(hour=td.hour)
            if '%M' in fmt:
                new = new.replace(minute=td.minute)
            if '%S' in fmt:
                new = new.replace(second=td.second)
            else:
                new = new.replace(second=0)
            if '%d' in fmt:
                new = new.replace(day=td.day)
            return new
        except ValueError:
            pass

    return datetime.datetime.strptime(when, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc)
