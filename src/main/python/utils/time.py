"""
The MIT License (MIT)

Copyright (c) 2015-2020 Rapptz

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""
import datetime
import re

import parsedatetime as pdt
from dateutil.relativedelta import relativedelta
from discord.ext import commands


class plural:
    def __init__(self, value):
        self.value = value
    def __format__(self, format_spec):
        v = self.value
        singular, sep, plural = format_spec.partition('|')
        plural = plural or f'{singular}s'
        if abs(v) != 1:
            return f'{v} {plural}'
        return f'{v} {singular}'

def human_join(seq, delim=', ', final='or'):
    size = len(seq)
    if size == 0:
        return ''

    if size == 1:
        return seq[0]

    if size == 2:
        return f'{seq[0]} {final} {seq[1]}'

    return delim.join(seq[:-1]) + f' {final} {seq[-1]}'

class HumanTime:
    calendar = pdt.Calendar(version=pdt.VERSION_CONTEXT_STYLE)

    def __init__(self, argument, *, now=None):
        now = now or datetime.datetime.utcnow()
        dt, status = self.calendar.parseDT(argument, sourceTime=now)
        if not status.hasDateOrTime:
            raise commands.BadArgument('invalid time provided, try e.g. "tomorrow" or "3 days"')

        if not status.hasTime:
            # replace it with the current time
            dt = dt.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond)

        self.dt = dt
        self._past = dt < now

    @classmethod
    async def convert(cls, ctx, argument):
        return cls(argument, now=ctx.message.created_at)

class ShortTime:
    compiled = re.compile("""(?:(?P<years>[0-9])(?: years?|y))?             # e.g. 2y
                             (?:(?P<months>[0-9]{1,2})(?: months?|mo))?     # e.g. 2months
                             (?:(?P<weeks>[0-9]{1,4})(?: weeks?|w))?        # e.g. 10w
                             (?:(?P<days>[0-9]{1,5})(?: days?|d))?          # e.g. 14d
                             (?:(?P<hours>[0-9]{1,5})(?: hours?|h))?        # e.g. 12h
                             (?:(?P<minutes>[0-9]{1,5})(?: minutes?|m))?    # e.g. 10m
                             (?:(?P<seconds>[0-9]{1,5})(?: seconds?|s))?    # e.g. 15s
                          """, re.VERBOSE)

    def __init__(self, argument, *, now=None):
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            raise commands.BadArgument('invalid time provided')

        data = { k: int(v) for k, v in match.groupdict(default=0).items() }
        now = now or datetime.datetime.utcnow()
        self.dt = now + relativedelta(**data)

    @classmethod
    async def convert(cls, ctx, argument):
        return cls(argument, now=ctx.message.created_at)

class Time(HumanTime):
    def __init__(self, argument, *, now=None):
        try:
            o = ShortTime(argument, now=now)
        except Exception as e:
            super().__init__(argument)
        else:
            self.dt = o.dt
            self._past = False

class FutureTime(Time):
    def __init__(self, argument, *, now=None):
        super().__init__(argument, now=now)

        if self._past:
            raise commands.BadArgument('this time is in the past')

class HumanTime:
    calendar = pdt.Calendar()

    def __init__(self, argument, *, now=None):
        now = now or datetime.datetime.utcnow()
        dt, status = self.calendar.parseDT(argument, sourceTime=now)
        if not status.hasDateOrTime:
            raise commands.BadArgument('invalid time provided, try e.g. "tomorrow" or "3 days"')

        if not status.hasTime:
            # replace it with the current time
            dt = dt.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond)

        self.dt = dt
        self._past = dt < now

    @classmethod
    async def convert(cls, ctx, argument):
        return cls(argument, now=ctx.message.created_at)


class UserFriendlyTime(commands.Converter):
    """That way quotes aren't absolutely necessary."""
    def __init__(self, converter=None, *, default=None, now=None):
        self.now = now
        if isinstance(converter, type) and issubclass(converter, commands.Converter):
            converter = converter()

        if converter is not None and not isinstance(converter, commands.Converter):
            print(converter.__class__)
            raise TypeError('commands.Converter subclass necessary.')

        self.converter = converter
        self.default = default

    async def check_constraints(self, ctx, now, remaining):
        if self.dt < now:
            raise commands.BadArgument(ctx.bot.system.locale('This time is in the past.'))

        if not remaining:
            if self.default is None:
                raise commands.BadArgument(ctx.bot.system.locale('Missing argument after the time.'))
            remaining = self.default

        if self.converter is not None:
            self.arg = await self.converter.convert(ctx, remaining)
        else:
            self.arg = remaining
        return self

    def copy(self):
        cls = self.__class__
        obj = cls.__new__(cls)
        obj.converter = self.converter
        obj.default = self.default
        return obj

    async def convert(self, ctx, argument):
        remaining = None
        try:
            calendar = HumanTime.calendar
            now = ctx.message.created_at if self.now is None else datetime.datetime.utcnow()

            # apparently nlp does not like "from now"
            # it likes "from x" in other cases though so let me handle the 'now' case
            if argument.endswith('from now'):
                argument = argument[:-8].strip()

            if argument[0:2] == 'me':
                # starts with "me to", "me in", or "me at "
                if argument[0:6] in ('me to ', 'me in ', 'me at '):
                    argument = argument[6:]
            if argument.startswith("in "):
                argument = argument[3:]

            elements = calendar.nlp(argument, sourceTime=now)
            if elements is None or len(elements) == 0:
                raise commands.BadArgument(ctx.bot.system.locale('Time Error. try "in an hour" or "5 days".'))

            # handle the following cases:
            # "date time" foo
            # date time foo
            # foo date time

            # first the first two cases:
            dt, status, begin, end, dt_string = elements[0]

            self.dt = dt

            if begin in (0, 1):
                if begin == 1:
                    # check if it's quoted:
                    if argument[0] != '"':
                        raise commands.BadArgument(ctx.bot.system.locale('Expected quote before time input...'))

                    if not (end < len(argument) and argument[end] == '"'):
                        raise commands.BadArgument(ctx.bot.system.locale('If the time is quoted, you must unquote it.'))

                    remaining = argument[end + 1:].lstrip(' ,.!')
                else:
                    remaining = argument[end:].lstrip(' ,.!')
            elif len(argument) == end:
                remaining = argument[:begin].strip()

            return await self.check_constraints(ctx, now, remaining)
        except:
            import traceback
            traceback.print_exc()
            raise

def human_timedelta(locale, dt, *, source=None, accuracy=3, brief=False, suffix=True):
    now = source or datetime.datetime.utcnow()
    # Microsecond free zone
    now = now.replace(microsecond=0)
    dt = dt.replace(microsecond=0)

    # This implementation uses relativedelta instead of the much more obvious
    # divmod approach with seconds because the seconds approach is not entirely
    # accurate once you go over 1 week in terms of accuracy since you have to
    # hardcode a month as 30 or 31 days.
    # A query like "11 months" can be interpreted as "!1 months and 6 days"
    if dt > now:
        delta = relativedelta(dt, now)
        suffix = ''
    else:
        delta = relativedelta(now, dt)
        suffix = locale(' ago') if suffix else ''

    attrs = [
        (locale('year'), 'y'),
        (locale('month'), 'mo'),
        (locale('day'), 'd'),
        (locale('hour'), 'h'),
        (locale('minute'), 'm'),
        (locale('second'), 's'),
    ]

    output = []
    for attr, brief_attr in attrs:
        elem = getattr(delta, attr + 's')
        if not elem:
            continue

        if attr == locale('day'):
            weeks = delta.weeks
            if weeks:
                elem -= weeks * 7
                if not brief:
                    output.append(format(plural(weeks), locale('week')))
                else:
                    output.append(f'{weeks}w')

        if elem <= 0:
            continue

        if brief:
            output.append(f'{elem}{brief_attr}')
        else:
            output.append(format(plural(elem), attr))

    if accuracy is not None:
        output = output[:accuracy]

    if len(output) == 0:
        return locale('now')
    else:
        if not brief:
            return human_join(output, final=locale('and')) + suffix
        else:
            return ' '.join(output) + suffix
