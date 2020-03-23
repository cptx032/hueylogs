# coding: utf-8
from __future__ import print_function, unicode_literals

from django.db import models
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import periodic_task

from hueylogs.exceptions import HueyMaxTriesException


class HueyExecutionLog(models.Model):
    code = models.CharField(max_length=255, db_index=True)
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(db_index=True)
    is_success = models.BooleanField(default=False)

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
            except Exception:
                HueyExecutionLog.objects.create(
                    code=HueyExecutionLog.task_to_string(func),
                    start_time=start_time,
                    end_time=timezone.now(),
                    is_success=False,
                )
                raise

        # changing the name of returned function because huey uses it
        # as unique names to registry
        _inner_function.__name__ = func.__name__
        _inner_function.__module__ = func.__module__
        _inner_function.register_log_called = True
        return _inner_function
