from __future__ import annotations

import asyncio

from app.services.jobs import run_parse_job
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.parse_job")
def parse_job_task(job_id: str) -> None:
    asyncio.run(run_parse_job(job_id))
