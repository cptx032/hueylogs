# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import time
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.utils import timezone

from hueylogs.exceptions import HueyMaxTriesException
from hueylogs.models import HueyExecutionLog


class DecoratorsTest(TestCase):
    def test_create_model(self):
        log = HueyExecutionLog.objects.create(
            code="test",
            start_time=timezone.now(),
            end_time=timezone.now(),
            is_success=True,
        )
        self.assertIsNotNone(log.pk)

    def test_task_stringify(self):
        def _dummy_task():
            pass

        _dummy_task.__module__ = "dummy"
        _dummy_task.__name__ = "_dummy_task"

        self.assertEqual(
            HueyExecutionLog.task_to_string(_dummy_task), "dummy._dummy_task"
        )

    def test_str(self):
        log = HueyExecutionLog.objects.create(
            code="test",
            start_time=timezone.now(),
            end_time=timezone.now(),
            is_success=True,
        )
        self.assertEqual(str(log), "test")
        self.assertEqual(str(log), "test")

    def test_success_log_creation(self):
        @HueyExecutionLog.register_log
        def _pass():
            pass

        HueyExecutionLog.objects.all().delete()
        _pass()
        self.assertEqual(HueyExecutionLog.objects.count(), 1)
        log = HueyExecutionLog.objects.get()
        self.assertTrue(log.is_success)
        self.assertIsInstance(log.start_time, datetime)
        self.assertIsInstance(log.end_time, datetime)
        self.assertEqual(HueyExecutionLog.task_to_string(_pass), log.code)

    def test_error_log_creation(self):
        @HueyExecutionLog.register_log
        def _zero_division(value):
            return value / 0.0

        HueyExecutionLog.objects.all().delete()
        with self.assertRaises(ZeroDivisionError):
            _zero_division(1)
        self.assertEqual(HueyExecutionLog.objects.count(), 1)
        log = HueyExecutionLog.objects.get()
        self.assertFalse(log.is_success)
        self.assertIsInstance(log.start_time, datetime)
        self.assertIsInstance(log.end_time, datetime)
        self.assertEqual(
            HueyExecutionLog.task_to_string(_zero_division), log.code
        )

    def test_run_at_times(self):
        class VariableToggle:
            runned = False

        @HueyExecutionLog.run_at_times(
            hours=[datetime.now().time()], minutes_tolerance=1
        )
        @HueyExecutionLog.register_log
        def toggle_variable(klass):
            klass.runned = True

        toggle_variable(VariableToggle)
        self.assertTrue(VariableToggle.runned)

        VariableToggle.runned = False

        @HueyExecutionLog.run_at_times(
            hours=[(datetime.now() + relativedelta(hours=1)).time()],
            minutes_tolerance=15,
        )
        @HueyExecutionLog.register_log
        def toggle_variable(klass):
            klass.runned = True

        time.sleep(3)
        toggle_variable(VariableToggle)
        self.assertFalse(VariableToggle.runned)

        HueyExecutionLog.objects.all().delete()
        VariableToggle.runned = False

        @HueyExecutionLog.run_at_times(
            hours=[datetime.now().time()], minutes_tolerance=15
        )
        @HueyExecutionLog.register_log
        def toggle_variable(klass):
            klass.runned = True

        toggle_variable(VariableToggle)
        self.assertTrue(VariableToggle.runned)
        VariableToggle.runned = False
        # trying run it again. it must not run because it already do it
        toggle_variable(VariableToggle)
        self.assertFalse(VariableToggle.runned)

    def test_max_tries_decorator(self):
        # we must decorate the task with register_log before
        # use max_tries decorator
        with self.assertRaises(AttributeError):

            @HueyExecutionLog.max_tries(max_tries=3, try_again_delay=2)
            def _zero_division(value):
                return value / 0.0

        max_tries = 3
        delay_seconds = 3
        five_seconds = delay_seconds / 60.0

        @HueyExecutionLog.max_tries(
            max_tries=max_tries, try_again_delay=five_seconds
        )
        @HueyExecutionLog.register_log
        def _zero_division(value):
            return value / 0.0

        for i in range(max_tries - 1):
            with self.assertRaises(ZeroDivisionError):
                _zero_division(1)

        self.assertFalse(
            HueyExecutionLog._reached_max_tries(
                HueyExecutionLog.task_to_string(_zero_division), max_tries
            )
        )

        # when the task overflows the limit of executions a "MaxTriesException"
        # is raised
        with self.assertRaises(HueyMaxTriesException):
            _zero_division(1)

        self.assertTrue(
            HueyExecutionLog._reached_max_tries(
                HueyExecutionLog.task_to_string(_zero_division), max_tries
            )
        )
        # the zero division must not be called, so no error raises
        # until the "try_again_delay" have been passed
        _zero_division(1)
        # calling it again, just to check that i can call it many times
        # but it will not be executed
        _zero_division(1)

        # waiting for the delay to call it again
        time.sleep(delay_seconds + 1)

        # again it will raise zerodivision, but all the last execution
        # were in error, so it must raises a maxtriesexception again
        with self.assertRaises(HueyMaxTriesException):
            _zero_division(1)
