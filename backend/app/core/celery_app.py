from celery import Celery
from kombu import Queue
from app.core.config import settings

celery_app = Celery(
    "cp_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_queues=[
        Queue("judge_queue", routing_key="judge.#"),
        Queue("run_queue", routing_key="run.#"),
        Queue("proctor_queue", routing_key="proctor.#"),
        Queue("notify_queue", routing_key="notify.#"),
        Queue("reconcile_queue", routing_key="reconcile.#"),
    ],
    task_routes={
        "app.workers.judge.*": {"queue": "judge_queue"},
        "app.workers.run.*": {"queue": "run_queue"},
        "app.workers.proctor.*": {"queue": "proctor_queue"},
        "app.workers.notify.*": {"queue": "notify_queue"},
        "app.workers.reconciler.*": {"queue": "reconcile_queue"},
    },
)
