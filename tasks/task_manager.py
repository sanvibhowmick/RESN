"""tasks/task_manager.py
Asynchronous Task Worker and Job Queue Architecture.

Decouples long-running operations (PDF report compilation, multi-agent triage,
batch risk scoring, and vector embeddings) from the synchronous web request thread.
Provides thread-safe background execution, live status tracking, and Celery fallback.
"""

import os
import uuid
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Any, Callable, Optional
from agents.schemas import TaskStatusSchema


class BackgroundTaskManager:
    """Manages asynchronous background jobs using a thread pool worker queue."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, max_workers: int = 4):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(BackgroundTaskManager, cls).__new__(cls)
                cls._instance._init_manager(max_workers)
            return cls._instance

    def _init_manager(self, max_workers: int):
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="RESN-Worker")
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.futures: Dict[str, Future] = {}
        self._state_lock = threading.Lock()

    def submit_task(
        self,
        task_type: str,
        fn: Callable,
        *args,
        task_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Submits a callable to the background worker pool and returns its tracking task_id."""
        if not task_id:
            task_id = str(uuid.uuid4())

        now_str = datetime.utcnow().isoformat()
        with self._state_lock:
            self.tasks[task_id] = {
                "task_id": task_id,
                "task_type": task_type,
                "status": "PENDING",
                "progress": 0.0,
                "result": None,
                "error": None,
                "created_at": now_str,
                "completed_at": None,
            }

        def _worker_wrapper(tid: str, func: Callable, f_args, f_kwargs):
            self._update_task_state(tid, status="RUNNING", progress=15.0)
            try:
                # Execute the heavy task
                res = func(*f_args, **f_kwargs)
                self._update_task_state(
                    tid,
                    status="COMPLETED",
                    progress=100.0,
                    result=res,
                    completed_at=datetime.utcnow().isoformat(),
                )
            except Exception as e:
                self._update_task_state(
                    tid,
                    status="FAILED",
                    progress=100.0,
                    error=str(e),
                    completed_at=datetime.utcnow().isoformat(),
                )

        future = self.executor.submit(_worker_wrapper, task_id, fn, args, kwargs)
        with self._state_lock:
            self.futures[task_id] = future

        return task_id

    def _update_task_state(self, task_id: str, **updates):
        with self._state_lock:
            if task_id in self.tasks:
                self.tasks[task_id].update(updates)

    def get_task_status(self, task_id: str) -> Optional[TaskStatusSchema]:
        """Returns the structured validated status of a background job."""
        with self._state_lock:
            task_data = self.tasks.get(task_id)
            if not task_data:
                return None
            return TaskStatusSchema.model_validate(task_data)

    def get_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        with self._state_lock:
            return dict(self.tasks)


# Global Singleton Task Manager
task_manager = BackgroundTaskManager(max_workers=4)


# =====================================================================
# BACKGROUND TASK DEFINITIONS
# =====================================================================
def async_generate_pdf_task(student_data: dict, scheme_name: str, risk_analysis: str) -> str:
    """Background worker task for compiling PDF scholarship forms."""
    from tools.report_tools import generate_intervention_pdf

    time.sleep(0.1)  # Context switch
    pdf_path = generate_intervention_pdf(
        student_data=student_data,
        scheme_name=scheme_name,
        risk_analysis=risk_analysis,
    )
    return pdf_path


def async_run_intervention_task(student_id: int, counseling_lang: str = "Hindi") -> dict:
    """Background worker task executing full multi-agent triage."""
    from agents.orchestrator import RESNOrchestrator

    orchestrator = RESNOrchestrator()
    return orchestrator.run_intervention_pipeline(student_id=student_id, counseling_lang=counseling_lang)


def async_index_memory_task(student_id: int, context_summary: str, metadata: dict = None) -> bool:
    """Background worker task offloading embedding calculation and database insertion."""
    from memory.pg_vector import PGVectorMemory

    memory = PGVectorMemory()
    return memory.add_memory(student_id=student_id, context_summary=context_summary, metadata=metadata)
