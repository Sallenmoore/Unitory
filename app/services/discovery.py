"""Autodiscovery — background job plus the handler-side enqueue helper."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from autonomous import log
from autonomous.taskrunner import AutoTasks

from app.models.discovery_job import DiscoveryJob
from app.models.server import DISCOVERY_FIELDS, Server
from app.services.node_exporter import fetch_metrics, parse_metrics


def enqueue_scan(hostnames: list[str], port: int, requested_by: str) -> DiscoveryJob:
    hostnames = _normalize_hostnames(hostnames)
    if not hostnames:
        raise ValueError("No hostnames provided")

    job_record = DiscoveryJob(
        hostnames=hostnames,
        port=port,
        requested_by=requested_by,
        state="queued",
    )
    job_record.save()

    timeout = min(max(30, len(hostnames) * 10), 3600)
    task = AutoTasks().task(
        scan_hosts,
        hostnames=hostnames,
        port=port,
        job_id=str(job_record.pk),
        _task_job_timeout=timeout,
    )
    job_record.rq_job_id = task.id
    job_record.save()
    return job_record


def scan_hosts(hostnames: list[str], port: int, job_id: str) -> dict:
    """Entry point executed by the RQ worker.

    Imports models inside the function so the MongoDB connection is
    established in the worker process, not at module import time.
    """
    job = DiscoveryJob.get(job_id)
    if not job:
        log(f"scan_hosts: DiscoveryJob {job_id} not found")
        return {"error": "job_not_found"}

    job.mark_running()
    created = updated = failed = 0
    errors: list[dict] = []

    for host in hostnames:
        try:
            text = fetch_metrics(host, port=port, timeout=5.0)
        except Exception as exc:
            failed += 1
            errors.append({"hostname": host, "error": f"fetch: {exc}"})
            continue

        try:
            discovered = parse_metrics(text)
        except Exception as exc:
            failed += 1
            errors.append({"hostname": host, "error": f"parse: {exc}"})
            continue

        try:
            result = _upsert_server(host, discovered)
        except Exception as exc:
            failed += 1
            errors.append({"hostname": host, "error": f"save: {exc}"})
            continue

        if result == "created":
            created += 1
        else:
            updated += 1

    job.created = created
    job.updated = updated
    job.failed = failed
    job.errors = errors
    job.mark_finished()

    return {
        "job_id": job_id,
        "created": created,
        "updated": updated,
        "failed": failed,
    }


def _upsert_server(hostname: str, discovered: dict) -> str:
    server = Server.find(hostname=hostname)
    is_new = server is None
    if is_new:
        server = Server(hostname=hostname, status="discovered")

    for key, value in discovered.items():
        if key not in DISCOVERY_FIELDS:
            continue
        if value in (None, "", []):
            continue
        setattr(server, key, value)

    server.last_discovered = datetime.now()
    server.discovery_data = discovered
    server.save()
    return "created" if is_new else "updated"


def _normalize_hostnames(hostnames: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in hostnames:
        host = (raw or "").strip().lower()
        if not host or host.startswith("#"):
            continue
        if host in seen:
            continue
        seen.add(host)
        out.append(host)
    return out
