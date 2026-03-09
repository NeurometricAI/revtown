"""
Deacon - Background janitor process.

Responsibilities:
- Clean dead leads
- Retire orphaned Polecats
- Monitor thresholds
- Trigger Neurometric evaluation loops
- Ping the Mayor
- Poll plugin health endpoints
- Expire stale approval items
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from apps.api.config import settings

logger = structlog.get_logger()


class Deacon:
    """
    The Deacon background task runner.

    Manages scheduled tasks for system maintenance and monitoring.
    """

    def __init__(self, organization_id: UUID | None = None):
        self.organization_id = organization_id
        self.scheduler = AsyncIOScheduler()
        self.logger = logger.bind(service="deacon")
        self._running = False
        self._last_run_results: dict[str, dict[str, Any]] = {}

    def start(self):
        """Start the Deacon scheduler."""
        if self._running:
            return

        self.logger.info("Starting Deacon scheduler")

        # Schedule tasks
        self._schedule_tasks()

        self.scheduler.start()
        self._running = True

        self.logger.info("Deacon scheduler started")

    def stop(self):
        """Stop the Deacon scheduler."""
        if not self._running:
            return

        self.logger.info("Stopping Deacon scheduler")
        self.scheduler.shutdown(wait=False)
        self._running = False

    def _schedule_tasks(self):
        """Schedule all Deacon tasks."""

        # Every 5 minutes: Check plugin health
        self.scheduler.add_job(
            self._check_plugin_health,
            IntervalTrigger(minutes=5),
            id="plugin_health",
            name="Plugin Health Check",
        )

        # Every 15 minutes: Clean orphaned Polecats
        self.scheduler.add_job(
            self._clean_orphaned_polecats,
            IntervalTrigger(minutes=15),
            id="clean_polecats",
            name="Clean Orphaned Polecats",
        )

        # Every hour: Monitor thresholds
        self.scheduler.add_job(
            self._monitor_thresholds,
            IntervalTrigger(hours=1),
            id="monitor_thresholds",
            name="Monitor Thresholds",
        )

        # Daily at 2 AM: Clean dead leads
        self.scheduler.add_job(
            self._clean_dead_leads,
            CronTrigger(hour=2, minute=0),
            id="clean_dead_leads",
            name="Clean Dead Leads",
        )

        # Weekly on Sunday at 3 AM: Trigger Neurometric evaluation
        self.scheduler.add_job(
            self._trigger_neurometric_eval,
            CronTrigger(day_of_week="sun", hour=3, minute=0),
            id="neurometric_eval",
            name="Neurometric Evaluation Loop",
        )

        # Every 30 minutes: Ping Mayor for status
        self.scheduler.add_job(
            self._ping_mayor,
            IntervalTrigger(minutes=30),
            id="ping_mayor",
            name="Ping Mayor",
        )

        # Every hour: Check approval queue expiration
        self.scheduler.add_job(
            self._check_approval_expiration,
            IntervalTrigger(hours=1),
            id="approval_expiration",
            name="Check Approval Expiration",
        )

    # =========================================================================
    # Task Implementations
    # =========================================================================

    async def _check_plugin_health(self):
        """
        Poll health endpoints for all active plugins.

        Updates plugin health status in PluginBeads.
        Flags unhealthy plugins in the Admin Panel.
        """
        self.logger.debug("Running plugin health check")

        results = {
            "checked": 0,
            "healthy": 0,
            "unhealthy": 0,
            "errors": [],
        }

        try:
            # In production, this would query the plugin registry
            # and call health endpoints
            # For now, log that no plugins are registered
            self.logger.debug("No plugins registered for health check")

        except Exception as e:
            self.logger.error("Plugin health check failed", error=str(e))
            results["errors"].append(str(e))

        self._last_run_results["plugin_health"] = {
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
        }

    async def _clean_orphaned_polecats(self):
        """
        Find and clean up orphaned Polecat executions.

        Polecats are orphaned if:
        - Running status but no Temporal workflow
        - Started > 30 minutes ago with no updates
        """
        from apps.api.core.polecat_store import get_polecat_store, PolecatStatus

        self.logger.debug("Cleaning orphaned Polecats")

        results = {
            "checked": 0,
            "orphaned": 0,
            "cleaned": [],
        }

        try:
            store = get_polecat_store()
            orphans = store.get_orphaned(max_age_minutes=30)

            results["checked"] = len(store._executions)
            results["orphaned"] = len(orphans)

            for execution in orphans:
                store.update_status(
                    execution.id,
                    PolecatStatus.FAILED,
                    error_message="Execution timed out (orphaned)",
                )
                results["cleaned"].append(execution.id)
                self.logger.warning(
                    "Cleaned orphaned Polecat",
                    execution_id=execution.id,
                    polecat_type=execution.polecat_type,
                    started_at=execution.started_at.isoformat() if execution.started_at else None,
                )

            if orphans:
                self.logger.info(
                    "Orphaned Polecat cleanup complete",
                    cleaned_count=len(orphans),
                )

        except Exception as e:
            self.logger.error("Orphaned Polecat cleanup failed", error=str(e))

        self._last_run_results["clean_polecats"] = {
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
        }

    async def _monitor_thresholds(self):
        """
        Monitor system thresholds and alert if exceeded.

        Monitors:
        - Approval queue depth
        - Running Polecat count
        - Active convoy count
        - Error rates
        """
        from apps.api.core.approval_store import get_approval_store, ApprovalStatus
        from apps.api.core.polecat_store import get_polecat_store, PolecatStatus
        from apps.api.core.convoy_store import get_convoy_store, ConvoyStatus

        self.logger.debug("Monitoring thresholds")

        results = {
            "approval_queue": {},
            "polecats": {},
            "convoys": {},
            "alerts": [],
        }

        try:
            # Check approval queue
            approval_store = get_approval_store()
            pending_count = sum(
                1 for item in approval_store._items.values()
                if item.status == ApprovalStatus.PENDING
            )
            results["approval_queue"] = {
                "total_items": len(approval_store._items),
                "pending": pending_count,
            }

            # Alert if approval queue is backed up
            if pending_count > 50:
                alert = f"High approval queue depth: {pending_count} items pending"
                results["alerts"].append(alert)
                self.logger.warning(alert)

            # Check Polecats
            polecat_store = get_polecat_store()
            running = len([e for e in polecat_store._executions.values() if e.status == PolecatStatus.RUNNING])
            failed_recent = len([
                e for e in polecat_store._executions.values()
                if e.status == PolecatStatus.FAILED
                and e.completed_at
                and (datetime.utcnow() - e.completed_at).total_seconds() < 3600
            ])
            results["polecats"] = {
                "total": len(polecat_store._executions),
                "running": running,
                "failed_last_hour": failed_recent,
            }

            # Alert on high failure rate
            if failed_recent > 10:
                alert = f"High Polecat failure rate: {failed_recent} failures in last hour"
                results["alerts"].append(alert)
                self.logger.warning(alert)

            # Check Convoys
            convoy_store = get_convoy_store()
            executing = len([c for c in convoy_store._convoys.values() if c.status == ConvoyStatus.EXECUTING])
            results["convoys"] = {
                "total": len(convoy_store._convoys),
                "executing": executing,
            }

            if results["alerts"]:
                self.logger.warning(
                    "Threshold alerts triggered",
                    alert_count=len(results["alerts"]),
                )

        except Exception as e:
            self.logger.error("Threshold monitoring failed", error=str(e))

        self._last_run_results["monitor_thresholds"] = {
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
        }

    async def _clean_dead_leads(self):
        """
        Archive leads that are no longer viable.

        Criteria for dead leads:
        - No response after X contact attempts
        - Bounced email
        - Explicitly marked as dead
        - No activity in 90+ days

        Note: Requires BeadStore connection to function fully.
        """
        self.logger.info("Running dead lead cleanup")

        results = {
            "checked": 0,
            "archived": 0,
        }

        try:
            # This would query LeadBeads meeting dead criteria
            # For now, log that DB connection is needed
            self.logger.debug("Dead lead cleanup requires BeadStore connection")

        except Exception as e:
            self.logger.error("Dead lead cleanup failed", error=str(e))

        self._last_run_results["clean_dead_leads"] = {
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
        }

    async def _trigger_neurometric_eval(self):
        """
        Trigger the weekly Neurometric model evaluation loop.

        This initiates shadow testing to determine if different
        models would be more efficient for various task classes.
        """
        self.logger.info("Triggering Neurometric evaluation loop")

        results = {
            "task_classes_evaluated": 0,
            "recommendations": [],
        }

        try:
            # This would call Neurometric API to trigger shadow tests
            # For now, log that it would run
            self.logger.debug("Neurometric evaluation would trigger shadow tests")

        except Exception as e:
            self.logger.error("Neurometric evaluation trigger failed", error=str(e))

        self._last_run_results["neurometric_eval"] = {
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
        }

    async def _ping_mayor(self):
        """
        Compile and log system status.

        Reports:
        - System health summary
        - Queue depths
        - Active campaigns status
        - Any alerts or issues
        """
        from apps.api.core.approval_store import get_approval_store, ApprovalStatus
        from apps.api.core.polecat_store import get_polecat_store, PolecatStatus
        from apps.api.core.convoy_store import get_convoy_store, ConvoyStatus

        self.logger.debug("Compiling system status")

        try:
            approval_store = get_approval_store()
            polecat_store = get_polecat_store()
            convoy_store = get_convoy_store()

            status = {
                "timestamp": datetime.utcnow().isoformat(),
                "approval_queue": {
                    "pending": sum(1 for i in approval_store._items.values() if i.status == ApprovalStatus.PENDING),
                    "total": len(approval_store._items),
                },
                "polecats": {
                    "running": len([e for e in polecat_store._executions.values() if e.status == PolecatStatus.RUNNING]),
                    "total": len(polecat_store._executions),
                },
                "convoys": {
                    "executing": len([c for c in convoy_store._convoys.values() if c.status == ConvoyStatus.EXECUTING]),
                    "total": len(convoy_store._convoys),
                },
                "health": "ok",
            }

            # Check for issues
            issues = []
            if status["approval_queue"]["pending"] > 100:
                issues.append("approval_queue_backlog")
            if status["polecats"]["running"] > 50:
                issues.append("high_polecat_concurrency")

            if issues:
                status["health"] = "degraded"
                status["issues"] = issues

            self.logger.info(
                "System status",
                **status,
            )

            self._last_run_results["ping_mayor"] = {
                "timestamp": datetime.utcnow().isoformat(),
                "status": status,
            }

        except Exception as e:
            self.logger.error("Mayor ping failed", error=str(e))

    async def _check_approval_expiration(self):
        """
        Check for and handle expired approval items.

        Items in the approval queue may have expiration times
        (e.g., time-sensitive PR pitches).
        """
        from apps.api.core.approval_store import get_approval_store

        self.logger.debug("Checking approval expiration")

        results = {
            "checked": 0,
            "expired": 0,
        }

        try:
            approval_store = get_approval_store()
            results["checked"] = len(approval_store._items)

            expired_count = approval_store.expire_items()
            results["expired"] = expired_count

            if expired_count > 0:
                self.logger.info(
                    "Expired approval items",
                    count=expired_count,
                )

        except Exception as e:
            self.logger.error("Approval expiration check failed", error=str(e))

        self._last_run_results["approval_expiration"] = {
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
        }

    # =========================================================================
    # Manual Task Triggers
    # =========================================================================

    async def trigger_task(self, task_name: str) -> dict[str, Any]:
        """
        Manually trigger a Deacon task.

        Used for testing or on-demand execution.
        """
        task_map = {
            "plugin_health": self._check_plugin_health,
            "clean_polecats": self._clean_orphaned_polecats,
            "monitor_thresholds": self._monitor_thresholds,
            "clean_dead_leads": self._clean_dead_leads,
            "neurometric_eval": self._trigger_neurometric_eval,
            "ping_mayor": self._ping_mayor,
            "approval_expiration": self._check_approval_expiration,
        }

        task = task_map.get(task_name)
        if not task:
            return {"error": f"Unknown task: {task_name}", "available": list(task_map.keys())}

        self.logger.info(f"Manually triggering task: {task_name}")

        try:
            await task()
            return {
                "success": True,
                "task": task_name,
                "triggered_at": datetime.utcnow().isoformat(),
                "results": self._last_run_results.get(task_name, {}),
            }
        except Exception as e:
            return {"success": False, "task": task_name, "error": str(e)}

    def get_task_status(self) -> list[dict[str, Any]]:
        """Get status of all scheduled tasks."""
        jobs = []
        for job in self.scheduler.get_jobs():
            job_info = {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
            # Include last run results if available
            if job.id in self._last_run_results:
                job_info["last_run"] = self._last_run_results[job.id]
            jobs.append(job_info)
        return jobs


# =============================================================================
# Global Deacon Instance
# =============================================================================

_deacon: Deacon | None = None


def get_deacon() -> Deacon:
    """Get the global Deacon instance."""
    global _deacon
    if _deacon is None:
        _deacon = Deacon()
    return _deacon


def start_deacon():
    """Start the global Deacon."""
    deacon = get_deacon()
    deacon.start()


def stop_deacon():
    """Stop the global Deacon."""
    global _deacon
    if _deacon:
        _deacon.stop()


# =============================================================================
# CLI Entry Point
# =============================================================================


def run():
    """Run the Deacon as a standalone process."""
    import signal

    logger.info("Starting Deacon process")

    deacon = get_deacon()
    deacon.start()

    # Handle shutdown signals
    def shutdown(signum, frame):
        logger.info("Received shutdown signal")
        deacon.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Keep running
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        deacon.stop()


if __name__ == "__main__":
    run()
