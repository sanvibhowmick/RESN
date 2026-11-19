"""tasks/celery_app.py
Enterprise Celery Application Configuration with Redis Broker.

Used when running RESN in multi-container / Kubernetes / cloud production
to distribute agentic interventions and document compilation across worker pools.
"""

import os
from celery import Celery

# Redis Broker Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", f"redis://{REDIS_HOST}:{REDIS_PORT}/0")

celery_app = Celery(
    "resn_tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5-minute timeout per intervention
)


@celery_app.task(name="tasks.run_intervention_async")
def run_intervention_async(student_id: int, counseling_lang: str = "Hindi"):
    """Celery worker task for multi-agent intervention."""
    from tasks.task_manager import async_run_intervention_task
    return async_run_intervention_task(student_id, counseling_lang)


@celery_app.task(name="tasks.generate_pdf_async")
def generate_pdf_async(student_data: dict, scheme_name: str, risk_analysis: str):
    """Celery worker task for PDF generation."""
    from tasks.task_manager import async_generate_pdf_task
    return async_generate_pdf_task(student_data, scheme_name, risk_analysis)


@celery_app.task(name="tasks.index_memory_async")
def index_memory_async(student_id: int, context_summary: str, metadata: dict = None):
    """Celery worker task for vector embedding indexing."""
    from tasks.task_manager import async_index_memory_task
    return async_index_memory_task(student_id, context_summary, metadata)
