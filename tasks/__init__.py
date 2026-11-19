"""tasks package
Provides asynchronous task management, queueing, and background workers for heavy operations
such as multi-agent orchestration, PDF report generation, and vector embedding indexing.
"""

from tasks.task_manager import task_manager, BackgroundTaskManager

__all__ = ["task_manager", "BackgroundTaskManager"]
