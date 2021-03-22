# coding: utf-8
from __future__ import unicode_literals

from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter

from .models import HueyExecutionLog
from .serializers import HueyExecutionLogSerializer


class HueyExecutionLogViewSet(viewsets.ReadOnlyModelViewSet):
    class FilterSet(filters.FilterSet):
        start_time__gte = filters.DateFilter(
            name="start_time", lookup_expr="date__gte"
        )
        start_time__lte = filters.DateFilter(
            name="start_time", lookup_expr="date__lte"
        )

        class Meta:
            model = HueyExecutionLog
            fields = ["code", "is_success", "finnished", "id"]

    serializer_class = HueyExecutionLogSerializer
    queryset = HueyExecutionLog.objects.all()
    search_fields = ("code", "error_description")
    ordering_fields = "__all__"
    filter_class = FilterSet
    filter_backends = (
        filters.DjangoFilterBackend,
        OrderingFilter,
        SearchFilter,
    )
