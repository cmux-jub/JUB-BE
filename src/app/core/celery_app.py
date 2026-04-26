from collections.abc import Callable
from typing import Any

from app.core.config import get_settings


class DummyCelery:
    def task(self, *args: Any, **kwargs: Any) -> Callable:
        def decorator(func: Callable) -> Callable:
            return func

        return decorator


def create_celery_app() -> Any:
    try:
        from celery import Celery
    except ModuleNotFoundError:
        return DummyCelery()

    settings = get_settings()
    celery_app = Celery("aftertaste", broker=settings.redis_url, backend=settings.redis_url)
    celery_app.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json")
    return celery_app


celery_app = create_celery_app()
