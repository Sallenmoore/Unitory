from datetime import datetime

from autonomous.model.autoattr import (
    DateTimeAttr,
    DictAttr,
    IntAttr,
    ListAttr,
    StringAttr,
)
from autonomous.model.automodel import AutoModel

JOB_STATES = ["queued", "running", "finished", "failed"]


class DiscoveryJob(AutoModel):
    meta = {"collection": "discovery_jobs"}

    rq_job_id = StringAttr()
    requested_by = StringAttr()
    hostnames = ListAttr(StringAttr())
    port = IntAttr(default=9100)

    state = StringAttr(choices=JOB_STATES, default="queued")
    started_at = DateTimeAttr()
    finished_at = DateTimeAttr()

    created = IntAttr(default=0)
    updated = IntAttr(default=0)
    failed = IntAttr(default=0)
    errors = ListAttr(DictAttr())

    def mark_running(self):
        self.state = "running"
        self.started_at = datetime.now()
        self.save()

    def mark_finished(self):
        self.state = "finished"
        self.finished_at = datetime.now()
        self.save()

    def mark_failed(self, message: str):
        self.state = "failed"
        self.finished_at = datetime.now()
        self.errors = list(self.errors or []) + [{"hostname": "-", "error": message}]
        self.save()

    def summary(self) -> str:
        return (
            f"{self.created} created · {self.updated} updated · {self.failed} failed"
        )
