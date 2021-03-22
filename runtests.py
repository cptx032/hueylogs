#!/usr/bin/env python3
import glob
import os
import sys

import django
from django.conf import settings
from django.core.management import execute_from_command_line

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.abspath(os.path.join(BASE_DIR, "..")))

# Unfortunately, apps can not be installed via ``modify_settings``
# decorator, because it would miss the database setup.
CUSTOM_INSTALLED_APPS = (
    "hueylogs",
    #    'django.contrib.admin',
)

ALWAYS_INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    #    'django.contrib.sessions',
    #    'django.contrib.messages',
    #    'django.contrib.staticfiles',
)

ALWAYS_MIDDLEWARE_CLASSES = (
    #    'django.contrib.sessions.middleware.SessionMiddleware',
    #    'django.middleware.common.CommonMiddleware',
    #    'django.middleware.csrf.CsrfViewMiddleware',
    #    'django.contrib.auth.middleware.AuthenticationMiddleware',
    #    'django.contrib.messages.middleware.MessageMiddleware',
    #    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

HUEY = {
    "huey_class": "huey.SqliteHuey",  # Huey implementation to use.
    "filename": "",  # Use db name for huey.
    "results": True,  # Store return values of tasks.
    "store_none": False,  # If a task returns None, do not save to results.
    "immediate": False,  # If DEBUG=True, run synchronously.
    "utc": True,  # Use UTC for all times internally.
    "consumer": {
        "workers": 1,
        "worker_type": "thread",
        "initial_delay": 0.1,  # Smallest polling interval, same as -d.
        "backoff": 1.15,  # Exponential backoff using this rate, -b.
        "max_delay": 10.0,  # Max possible polling interval, -m.
        "scheduler_interval": 1,  # Check schedule every second, -s.
        "periodic": True,  # Enable crontab feature.
        "check_worker_health": True,  # Enable worker health checks.
        "health_check_interval": 1,  # Check worker health every second.
    },
}


settings.configure(
    SECRET_KEY="django_tests_secret_key",
    DEBUG=False,
    HUEY=HUEY,
    TEMPLATE_DEBUG=False,
    ALLOWED_HOSTS=[],
    INSTALLED_APPS=ALWAYS_INSTALLED_APPS + CUSTOM_INSTALLED_APPS,
    MIDDLEWARE_CLASSES=ALWAYS_MIDDLEWARE_CLASSES,
    ROOT_URLCONF="hueylogs.urls",
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
        }
    },
    LANGUAGE_CODE="en-us",
    TIME_ZONE="UTC",
    USE_I18N=True,
    USE_L10N=True,
    USE_TZ=True,
    STATIC_URL="/static/",
    # Use a fast hasher to speed up tests.
    PASSWORD_HASHERS=("django.contrib.auth.hashers.MD5PasswordHasher",),
    FIXTURE_DIRS=glob.glob(BASE_DIR + "/" + "*/fixtures/"),
)

django.setup()
args = [sys.argv[0], "test"]
# Current module (``tests``) and its submodules.
test_cases = "."

# Allow accessing test options from the command line.
offset = 1
try:
    sys.argv[1]
except IndexError:
    pass
else:
    option = sys.argv[1].startswith("-")
    if not option:
        test_cases = sys.argv[1]
        offset = 2

args.append(test_cases)
# ``verbosity`` can be overwritten from command line.
args.append("--verbosity=2")
args.extend(sys.argv[offset:])

execute_from_command_line(args)
