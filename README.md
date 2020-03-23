# hueylogs

## What
Hueylogs is a django app/plugin for registering the calling of [huey](https://github.com/coleifer/huey/) tasks.
(Truly, it can work with any thing in python/django not just background tasks, Ive called it hueylogs to a better focus).
With it is possible to know how many times a task did last, when it were runned, if it raises many errors, and to interrupt the tasks if so, and in the future, the goal is have some metrics about the memory usage of task and so on.

Example:
```python
# myapp/tasks.py
from hueylogs.models import HueyExecutionLog
from huey.contrib.djhuey import db_task

@db_task()
@HueyExecutionLog.register_log
def print_ok():
    print("OK")

HueyExecutionLog.objects.all().delete()
print_ok.call_local()
assert HueyExecutionLog.objects.count() == 1
```

## Why
I've created hueylogs because I have missed the logs that [django cron](https://github.com/Tivix/django-cron) give to me and some features like [retry delay](https://django-cron.readthedocs.io/en/latest/sample_cron_configurations.html#retry-after-failure-feature).

## When
I start this project when all my personal/professional projects start using huey as the backgroung task manager.
Because of that, I will probably update this project every time a project mine need some feature. But feel encouraged to contribute to my little project as well :D

## Who
Me o_o (twitter.com/cptx032) a newbie pixelart artist

## API
WIP
