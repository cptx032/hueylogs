# coding: utf-8

from __future__ import unicode_literals

from rest_framework import serializers

from .models import HueyExecutionLog


class HueyExecutionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = HueyExecutionLog
        fields = (
            "code",
            "start_time",
            "end_time",
            "is_success",
            "error_description",
            "finnished",
            "pk",
        )
