# coding: utf-8
from __future__ import print_function, unicode_literals

import calendar
import logging
import sys
import traceback
from datetime import datetime
from datetime import time as datetimetime
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.db import models
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import db_periodic_task, lock_task
from six import text_type as unicode

from hueylogs.exceptions import HueyMaxTriesException

logger = logging.getLogger("hueylogs")


class HueyExecutionLog(models.Model):
    code = models.CharField(max_length=255, db_index=True)
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(db_index=True)
    is_success = models.BooleanField(default=False)
    error_description = models.TextField(blank=True)

    def __str__(self):
        return self.code

    @classmethod
    def task_to_string(cls, task_class):
        """Return the string representation of a function."""
        return "{}.{}".format(task_class.__module__, task_class.__name__)

    # @classmethod # fixme
    # @periodic_task(crontab(hour="10", minute="52"))
    # def clean_old_records(cls):
    #     print("CLEANING")

    @classmethod
    def logs(
        cls,
        hours,
        minutes_tolerance=15,
        max_tries=3,
        try_again_delay=5,
        lock=True,
    ):
        """Concentrate all decorators in only one decorator.

        Not that have no need to decorate the function with huey decorators.
        """

        def _decorator(func):
            run_at_times_decorator = HueyExecutionLog.run_at_times(
                hours=hours, minutes_tolerance=minutes_tolerance
            )
            max_tries_decorator = HueyExecutionLog.max_tries(
                max_tries=max_tries, try_again_delay=try_again_delay
            )
            db_periodic_task_decorator = db_periodic_task(lambda dt: True)
            lock_task_decorator = lambda func: func
            if lock:
                lock_task_decorator = lock_task(
                    HueyExecutionLog.task_to_string(func)
                )
            return db_periodic_task_decorator(
                lock_task_decorator(
                    run_at_times_decorator(
                        max_tries_decorator(
                            HueyExecutionLog.register_log(func)
                        )
                    )
                )
            )

        return _decorator

    @classmethod
    def _reached_max_tries(cls, code, max_tries):
        failed_tries = HueyExecutionLog.objects.filter(code=code).order_by(
            "-start_time"
        )[:max_tries]
        if failed_tries.count() < max_tries:
            return False
        fails = [
            not i for i in failed_tries.values_list("is_success", flat=True)
        ]
        return all(fails)

    @classmethod
    def check_incompatible_hours(cls, hours, minutes_tolerance):
        """True if a hour is less than 'minutes_tolerance' of another."""
        _times_copy = list(hours)
        while len(_times_copy):
            hour_to_check = _times_copy.pop()
            for remaining_hour in _times_copy:
                now = datetime.now()
                dt_a = datetime.combine(now, remaining_hour)
                dt_b = datetime.combine(now, hour_to_check)
                delta_minutes = abs((dt_a - dt_b).total_seconds()) / 60.0
                if delta_minutes <= minutes_tolerance:
                    raise ValueError(
                        "Is not possible have hours with less than {} minutes "
                        "of distance. Incompatible hours: {} and {}".format(
                            delta_minutes, dt_a, dt_b
                        )
                    )

    @classmethod
    def utc_to_local(cls, utc_dt):
        """Convert datetime with tzinfo to local hour without tzinfo.

        Source: https://stackoverflow.com/a/13287083
        """
        # get integer timestamp to avoid precision lost
        timestamp = calendar.timegm(utc_dt.timetuple())
        local_dt = datetime.fromtimestamp(timestamp)
        assert utc_dt.resolution >= timedelta(microseconds=1)
        return local_dt.replace(microsecond=utc_dt.microsecond)

    @classmethod
    def its_time(cls, hour, now, minutes_tolerance):
        """Return True if its time.

        Will be the time if the hour of 'now' is equal or in range defined
        by 'minutes_tolerance'. The 'minutes_tolerance' argument only works
        from 'hour' to foward, not backwards.

        Arguments:
            - hour: datetime.time, with time to be sent
            - now: datetime.datetime, now date
            - minutes_tolerance: int, how many minutes will be tolerated AFTER
        """
        # removing time zone data
        if now.tzinfo:
            now = HueyExecutionLog.utc_to_local(now)
        hour = datetimetime(hour.hour, hour.minute)
        assert isinstance(hour, datetimetime), "hour is not datetime.time"
        assert isinstance(now, datetime), "now is not datetime.datetime"

        # removing seconds info
        now = datetime.combine(now.date(), datetimetime(now.hour, now.minute))
        start = datetime(now.year, now.month, now.day, hour.hour, hour.minute)
        end = datetime(
            now.year, now.month, now.day, hour.hour, hour.minute
        ) + relativedelta(minutes=minutes_tolerance)
        return (now >= start) and (now <= end)

    @classmethod
    def run_at_times(self, hours, minutes_tolerance=15):
        """Make sure that the task will be runned only in some hours.

        Note that if 'hours' must have a minimum distance of 'minutes_tolerance'
        minutes.

        Arguments:
            - hours: a list of datetime.time
            - minutes_tolerance: if the task manager delay to run your function
                you can force the execution of it setting minutes_tolerance
                so if the task manager not run the task exactly in 00:00
                but a little bit after, you can execute it still
        """
        HueyExecutionLog.check_incompatible_hours(hours, minutes_tolerance)

        def _decorator(func):
            if not getattr(func, "register_log_called", None):
                raise AttributeError(
                    "The function '{}' must have been decorated "
                    "with 'register_log'".format(
                        HueyExecutionLog.task_to_string(func)
                    )
                )

            def _inner_function(*args, **kwargs):
                now = datetime.now()
                hour = None
                for i in hours:
                    if HueyExecutionLog.its_time(i, now, minutes_tolerance):
                        hour = i
                        break
                if hour is None:
                    return
                # verifying if the function was already called today
                last_execution = (
                    HueyExecutionLog.objects.filter(
                        code=HueyExecutionLog.task_to_string(func),
                        start_time__day=now.day,
                        start_time__month=now.month,
                        start_time__year=now.year,
                    )
                    .order_by("-start_time")
                    .first()
                )
                if last_execution:
                    already_runned = HueyExecutionLog.its_time(
                        hour, last_execution.start_time, minutes_tolerance
                    )
                    if already_runned:
                        return
                return func(*args, **kwargs)

            _inner_function.__module__ = func.__module__
            _inner_function.__name__ = func.__name__
            _inner_function.register_log_called = True
            return _inner_function

        return _decorator

    @classmethod
    def max_tries(cls, max_tries, try_again_delay):
        """If the function was runned many time in error stop the execution.
        Must be used with register_log decorator. The register_Log decorator
        must decorate the function BEFORE the max_tries decorator. Example:

        @periodic_task(lambda dt: True)
        @HueyExecutionLog.max_tries(max_tries=3, try_again_delay=5)
        @HueyExecutionLog.register_log
        def my_task():
            pass

        Arguments:
            - code: string with the unique name of function
            - try_again_delay: how many minutes must be passed since the last
                execution to try again
        """

        def _decorator(func):
            if not getattr(func, "register_log_called", None):
                raise AttributeError(
                    "The function '{}' must have been decorated "
                    "with 'register_log'".format(
                        HueyExecutionLog.task_to_string(func)
                    )
                )

            def _inner_function(*args, **kwargs):
                code = HueyExecutionLog.task_to_string(func)
                if HueyExecutionLog._reached_max_tries(code, max_tries):
                    last_execution = (
                        HueyExecutionLog.objects.filter(code=code)
                        .only("start_time")
                        .order_by("-start_time")
                        .first()
                        .start_time
                    )
                    minutes = (timezone.now() - last_execution).seconds / 60.0
                    if minutes < try_again_delay:
                        print(
                            "Skipping execution to detriment of "
                            "'try_again_delay' of {}".format(try_again_delay)
                        )
                        return
                try:
                    return func(*args, **kwargs)
                except:
                    reached = HueyExecutionLog._reached_max_tries(
                        code, max_tries
                    )
                    if reached:
                        raise HueyMaxTriesException(
                            "The function '{}' have reached the maximum "
                            "of {} tries".format(code, max_tries)
                        )
                    raise

            # changing the name of returned function because huey uses it
            # as unique names to registry
            _inner_function.__name__ = func.__name__
            _inner_function.__module__ = func.__module__
            _inner_function.register_log_called = True
            return _inner_function

        return _decorator

    @classmethod
    def register_log(cls, func):
        """Register the execution of a function."""

        def _inner_function(*args, **kwargs):
            start_time = timezone.now()
            try:
                result = func(*args, **kwargs)
                HueyExecutionLog.objects.create(
                    code=HueyExecutionLog.task_to_string(func),
                    start_time=start_time,
                    end_time=timezone.now(),
                    is_success=True,
                )
                return result
            except Exception as e:

                class DummyFile:
                    def __init__(self):
                        self.value = ""

                    def write(self, value):
                        if type(value) is not unicode:
                            value = value.decode("utf-8")
                        self.value += value + "\n"

                t, v, trace = sys.exc_info()
                dummy_file = DummyFile()
                traceback.print_exception(t, v, trace, file=dummy_file)
                HueyExecutionLog.objects.create(
                    code=HueyExecutionLog.task_to_string(func),
                    start_time=start_time,
                    end_time=timezone.now(),
                    is_success=False,
                    error_description=dummy_file.value,
                )
                logger.error(e)
                raise

        # changing the name of returned function because huey uses it
        # as unique names to registry
        _inner_function.__name__ = func.__name__
        _inner_function.__module__ = func.__module__
        _inner_function.register_log_called = True
        return _inner_function
