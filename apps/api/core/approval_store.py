"""
Approval Store - Persistence layer for the Approval Queue.

Database-backed store using the approval_queue table.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class ApprovalType(str, Enum):
    """Type of approval item."""
    CONTENT = "content"
    OUTREACH = "outreach"
    PR_PITCH = "pr_pitch"
    SMS = "sms"
    TEST_WINNER = "test_winner"
    OTHER = "other"


class ApprovalStatus(str, Enum):
    """Status of an approval item."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT_BACK = "sent_back"
    EXPIRED = "expired"


class Urgency(str, Enum):
    """Urgency level."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ApprovalItem:
    """An item in the approval queue."""
    id: str
    bead_type: str
    bead_id: str
    rig: str
    polecat_type: str
    approval_type: ApprovalType
    urgency: Urgency
    organization_id: str
    campaign_id: str | None = None
    convoy_id: str | None = None
    step_id: str | None = None
    polecat_execution_id: str | None = None

    # Content preview
    preview_title: str | None = None
    preview_content: str | None = None
    full_content: str | None = None

    # Quality gate results
    refinery_scores: dict[str, Any] = field(default_factory=dict)
    refinery_warnings: list[str] = field(default_factory=list)
    refinery_passed: bool = True
    witness_issues: list[str] = field(default_factory=list)
    witness_passed: bool = True

    # Status
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None

    # Decision info
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_notes: str | None = None
    edited_content: str | None = None

    def __post_init__(self):
        if self.expires_at is None:
            # Default expiry: 24 hours for critical, 72 hours otherwise
            hours = 24 if self.urgency == Urgency.CRITICAL else 72
            self.expires_at = self.created_at + timedelta(hours=hours)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "bead_type": self.bead_type,
            "bead_id": self.bead_id,
            "rig": self.rig,
            "polecat_type": self.polecat_type,
            "approval_type": self.approval_type.value,
            "urgency": self.urgency.value,
            "organization_id": self.organization_id,
            "campaign_id": self.campaign_id,
            "convoy_id": self.convoy_id,
            "step_id": self.step_id,
            "polecat_execution_id": self.polecat_execution_id,
            "preview_title": self.preview_title,
            "preview_content": self.preview_content,
            "refinery_scores": self.refinery_scores,
            "refinery_warnings": self.refinery_warnings,
            "refinery_passed": self.refinery_passed,
            "witness_issues": self.witness_issues,
            "witness_passed": self.witness_passed,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decision_notes": self.decision_notes,
        }

    @classmethod
    def from_row(cls, row_dict: dict[str, Any]) -> "ApprovalItem":
        """Create an ApprovalItem from a database row."""
        # Parse JSON fields
        refinery_scores = row_dict.get("refinery_scores")
        if refinery_scores and isinstance(refinery_scores, str):
            refinery_scores = json.loads(refinery_scores)

        refinery_warnings = row_dict.get("refinery_warnings")
        if refinery_warnings and isinstance(refinery_warnings, str):
            refinery_warnings = json.loads(refinery_warnings)

        return cls(
            id=row_dict["id"],
            bead_type=row_dict["bead_type"],
            bead_id=row_dict["bead_id"],
            rig=row_dict["rig"],
            polecat_type=row_dict.get("polecat_type", "unknown"),
            approval_type=ApprovalType(row_dict["approval_type"]),
            urgency=Urgency(row_dict["urgency"]),
            organization_id=row_dict["organization_id"],
            campaign_id=row_dict.get("campaign_id"),
            polecat_execution_id=row_dict.get("polecat_execution_id"),
            preview_title=row_dict.get("preview_title"),
            preview_content=row_dict.get("preview_content"),
            refinery_scores=refinery_scores or {},
            refinery_warnings=refinery_warnings or [],
            status=ApprovalStatus(row_dict["status"]),
            created_at=row_dict["created_at"] if isinstance(row_dict["created_at"], datetime) else datetime.fromisoformat(row_dict["created_at"]),
            expires_at=row_dict.get("expires_at"),
            decided_by=row_dict.get("decided_by"),
            decided_at=row_dict.get("decided_at"),
            decision_notes=row_dict.get("decision_notes"),
            edited_content=row_dict.get("edited_content"),
        )


@dataclass
class AuditLogEntry:
    """An entry in the approval audit log."""
    id: str
    action: str  # created, approved, rejected, sent_back, expired
    item_id: str
    user_id: str | None
    organization_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "item_id": self.item_id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


class ApprovalStore:
    """
    Database-backed store for Approval Queue items.

    Uses the approval_queue and audit_log tables.
    """

    def __init__(self):
        self.logger = logger.bind(service="approval_store")

    async def create(self, session: AsyncSession, item: ApprovalItem) -> ApprovalItem:
        """Add a new item to the approval queue."""
        query = text("""
            INSERT INTO approval_queue
            (id, organization_id, bead_type, bead_id, polecat_execution_id, polecat_type, rig,
             approval_type, urgency, preview_title, preview_content,
             refinery_scores, refinery_warnings, status, expires_at, created_at)
            VALUES (:id, :org_id, :bead_type, :bead_id, :polecat_execution_id, :polecat_type, :rig,
                    :approval_type, :urgency, :preview_title, :preview_content,
                    :refinery_scores, :refinery_warnings, :status, :expires_at, :created_at)
        """)

        await session.execute(query, {
            "id": item.id,
            "org_id": item.organization_id,
            "bead_type": item.bead_type,
            "bead_id": item.bead_id,
            "polecat_execution_id": item.polecat_execution_id,
            "polecat_type": item.polecat_type,
            "rig": item.rig,
            "approval_type": item.approval_type.value,
            "urgency": item.urgency.value,
            "preview_title": item.preview_title,
            "preview_content": item.preview_content,
            "refinery_scores": json.dumps(item.refinery_scores) if item.refinery_scores else None,
            "refinery_warnings": json.dumps(item.refinery_warnings) if item.refinery_warnings else None,
            "status": item.status.value,
            "expires_at": item.expires_at,
            "created_at": item.created_at,
        })

        # Add audit log entry
        await self._add_audit_entry(
            session,
            action="created",
            item_id=item.id,
            user_id=None,
            organization_id=item.organization_id,
            details={"rig": item.rig, "polecat_type": item.polecat_type},
        )

        await session.commit()

        self.logger.info(
            "Approval item created",
            item_id=item.id,
            rig=item.rig,
            polecat_type=item.polecat_type,
            approval_type=item.approval_type.value,
        )
        return item

    async def get(self, session: AsyncSession, item_id: str) -> ApprovalItem | None:
        """Get an approval item by ID."""
        query = text("""
            SELECT * FROM approval_queue WHERE id = :id
        """)
        result = await session.execute(query, {"id": item_id})
        row = result.fetchone()

        if not row:
            return None

        return ApprovalItem.from_row(dict(row._mapping))

    async def get_queue(
        self,
        session: AsyncSession,
        organization_id: str | None,
        status: ApprovalStatus | None = ApprovalStatus.PENDING,
        approval_type: ApprovalType | None = None,
        rig: str | None = None,
        urgency: Urgency | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ApprovalItem], int]:
        """Get items in the approval queue with filters."""
        # Build WHERE clause
        conditions = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if organization_id:
            conditions.append("organization_id = :org_id")
            params["org_id"] = organization_id

        if status:
            conditions.append("status = :status")
            params["status"] = status.value
        if approval_type:
            conditions.append("approval_type = :approval_type")
            params["approval_type"] = approval_type.value
        if rig:
            conditions.append("rig = :rig")
            params["rig"] = rig
        if urgency:
            conditions.append("urgency = :urgency")
            params["urgency"] = urgency.value

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Get total count
        count_query = text(f"SELECT COUNT(*) as total FROM approval_queue WHERE {where_clause}")
        count_result = await session.execute(count_query, params)
        total = count_result.fetchone()._mapping["total"]

        # Get items with sorting by urgency then created_at
        query = text(f"""
            SELECT * FROM approval_queue
            WHERE {where_clause}
            ORDER BY
                CASE urgency
                    WHEN 'critical' THEN 0
                    WHEN 'high' THEN 1
                    WHEN 'normal' THEN 2
                    WHEN 'low' THEN 3
                    ELSE 4
                END,
                created_at ASC
            LIMIT :limit OFFSET :offset
        """)
        result = await session.execute(query, params)

        items = []
        for row in result.fetchall():
            items.append(ApprovalItem.from_row(dict(row._mapping)))

        return items, total

    async def get_counts(self, session: AsyncSession, organization_id: str) -> dict[str, Any]:
        """Get counts of pending items by various dimensions."""
        # Total pending
        total_query = text("""
            SELECT COUNT(*) as total FROM approval_queue
            WHERE organization_id = :org_id AND status = 'pending'
        """)
        total_result = await session.execute(total_query, {"org_id": organization_id})
        total_pending = total_result.fetchone()._mapping["total"]

        # By type
        type_query = text("""
            SELECT approval_type, COUNT(*) as count FROM approval_queue
            WHERE organization_id = :org_id AND status = 'pending'
            GROUP BY approval_type
        """)
        type_result = await session.execute(type_query, {"org_id": organization_id})
        by_type = {row._mapping["approval_type"]: row._mapping["count"] for row in type_result.fetchall()}

        # By urgency
        urgency_query = text("""
            SELECT urgency, COUNT(*) as count FROM approval_queue
            WHERE organization_id = :org_id AND status = 'pending'
            GROUP BY urgency
        """)
        urgency_result = await session.execute(urgency_query, {"org_id": organization_id})
        by_urgency = {row._mapping["urgency"]: row._mapping["count"] for row in urgency_result.fetchall()}

        # By rig
        rig_query = text("""
            SELECT rig, COUNT(*) as count FROM approval_queue
            WHERE organization_id = :org_id AND status = 'pending'
            GROUP BY rig
        """)
        rig_result = await session.execute(rig_query, {"org_id": organization_id})
        by_rig = {row._mapping["rig"]: row._mapping["count"] for row in rig_result.fetchall()}

        return {
            "total_pending": total_pending,
            "by_type": by_type,
            "by_urgency": by_urgency,
            "by_rig": by_rig,
        }

    async def decide(
        self,
        session: AsyncSession,
        item_id: str,
        decision: ApprovalStatus,
        user_id: str,
        notes: str | None = None,
        edited_content: str | None = None,
    ) -> ApprovalItem | None:
        """Make a decision on an approval item."""
        # Get current item
        item = await self.get(session, item_id)
        if not item:
            return None

        if item.status != ApprovalStatus.PENDING:
            self.logger.warning(
                "Cannot decide on non-pending item",
                item_id=item_id,
                current_status=item.status.value,
            )
            return None

        # Update the item
        now = datetime.utcnow()
        query = text("""
            UPDATE approval_queue
            SET status = :status, decided_by = :decided_by, decided_at = :decided_at,
                decision_notes = :notes, edited_content = :edited_content
            WHERE id = :id AND status = 'pending'
        """)
        await session.execute(query, {
            "id": item_id,
            "status": decision.value,
            "decided_by": user_id,
            "decided_at": now,
            "notes": notes,
            "edited_content": edited_content,
        })

        # Add audit log entry
        await self._add_audit_entry(
            session,
            action=decision.value,
            item_id=item_id,
            user_id=user_id,
            organization_id=item.organization_id,
            details={"notes": notes, "had_edits": edited_content is not None},
        )

        await session.commit()

        # Update the item object
        item.status = decision
        item.decided_by = user_id
        item.decided_at = now
        item.decision_notes = notes
        if edited_content:
            item.edited_content = edited_content

        self.logger.info(
            "Approval decision made",
            item_id=item_id,
            decision=decision.value,
            user_id=user_id,
        )
        return item

    async def expire_items(self, session: AsyncSession) -> int:
        """Mark expired items. Called by Deacon."""
        now = datetime.utcnow()

        # Get items to expire (for audit logging)
        select_query = text("""
            SELECT id, organization_id FROM approval_queue
            WHERE status = 'pending' AND expires_at < :now
        """)
        select_result = await session.execute(select_query, {"now": now})
        items_to_expire = select_result.fetchall()

        if not items_to_expire:
            return 0

        # Update status
        update_query = text("""
            UPDATE approval_queue
            SET status = 'expired'
            WHERE status = 'pending' AND expires_at < :now
        """)
        result = await session.execute(update_query, {"now": now})
        expired_count = result.rowcount

        # Add audit entries
        for row in items_to_expire:
            row_dict = dict(row._mapping)
            await self._add_audit_entry(
                session,
                action="expired",
                item_id=row_dict["id"],
                user_id=None,
                organization_id=row_dict["organization_id"],
                details={},
            )

        await session.commit()

        if expired_count > 0:
            self.logger.info("Expired approval items", count=expired_count)

        return expired_count

    async def get_audit_log(
        self,
        session: AsyncSession,
        organization_id: str,
        action: str | None = None,
        user_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLogEntry], int]:
        """Get audit log entries."""
        conditions = ["organization_id = :org_id"]
        params: dict[str, Any] = {"org_id": organization_id, "limit": limit, "offset": offset}

        if action:
            conditions.append("action = :action")
            params["action"] = action
        if user_id:
            conditions.append("user_id = :user_id")
            params["user_id"] = user_id

        where_clause = " AND ".join(conditions)

        # Get count
        count_query = text(f"SELECT COUNT(*) as total FROM audit_log WHERE {where_clause}")
        count_result = await session.execute(count_query, params)
        total = count_result.fetchone()._mapping["total"]

        # Get entries
        query = text(f"""
            SELECT * FROM audit_log
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await session.execute(query, params)

        entries = []
        for row in result.fetchall():
            row_dict = dict(row._mapping)
            details = row_dict.get("details")
            if details and isinstance(details, str):
                details = json.loads(details)

            entries.append(AuditLogEntry(
                id=row_dict["id"],
                action=row_dict["action"],
                item_id=row_dict.get("entity_id", ""),
                user_id=row_dict.get("user_id"),
                organization_id=row_dict["organization_id"],
                timestamp=row_dict["created_at"],
                details=details or {},
            ))

        return entries, total

    async def _add_audit_entry(
        self,
        session: AsyncSession,
        action: str,
        item_id: str,
        user_id: str | None,
        organization_id: str,
        details: dict[str, Any],
    ):
        """Add an entry to the audit log."""
        query = text("""
            INSERT INTO audit_log (id, organization_id, user_id, action, entity_type, entity_id, details, created_at)
            VALUES (:id, :org_id, :user_id, :action, 'approval_item', :entity_id, :details, :created_at)
        """)
        await session.execute(query, {
            "id": str(uuid4()),
            "org_id": organization_id,
            "user_id": user_id,
            "action": action,
            "entity_id": item_id,
            "details": json.dumps(details),
            "created_at": datetime.utcnow(),
        })


# Global singleton instance
_store: ApprovalStore | None = None


def get_approval_store() -> ApprovalStore:
    """Get the global approval store instance."""
    global _store
    if _store is None:
        _store = ApprovalStore()
    return _store
