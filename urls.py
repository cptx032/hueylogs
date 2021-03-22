"""
This urlconf exists because Django expects ROOT_URLCONF to exist. URLs
should be added within the test folders, and use TestCase.urls to set them.
This helps the tests remain isolated.
"""

from rest_framework.routers import DefaultRouter

from .api_views import HueyExecutionLogViewSet

router = DefaultRouter()
router.register("hueylogs", HueyExecutionLogViewSet)
urlpatterns = router.urls
