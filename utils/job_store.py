"""Thread-safe in-memory job store."""

import threading
from typing import Any, Dict, Optional


class JobStore:
    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str, input_path: str, output_path: str, cfg) -> None:
        with self._lock:
            self._jobs[job_id] = {
                "job_id":   job_id,
                "status":   "queued",
                "progress": 0,
                "message":  "Queued",
                "input":    input_path,
                "output":   output_path,
                "log":      [],
            }

    def update(self, job_id: str, **kwargs) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(kwargs)
                if "message" in kwargs:
                    self._jobs[job_id]["log"].append(kwargs["message"])

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return dict(self._jobs.get(job_id, {}))

    def append_log(self, job_id: str, msg: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["log"].append(msg)
                self._jobs[job_id]["message"] = msg
