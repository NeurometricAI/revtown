"""
Approval Store - Persistence layer for the Approval Queue.

Stores approval queue items so they persist across API requests.
In production, this would be backed by Redis or the database.
For now, using in-memory storage with a module-level singleton.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import structlog

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
    In-memory store for Approval Queue items.

    In production, this would be backed by Redis or database.
    """

    def __init__(self):
        self._items: dict[str, ApprovalItem] = {}
        self._audit_log: list[AuditLogEntry] = []
        self._by_org: dict[str, list[str]] = {}  # org_id -> item_ids
        self._by_campaign: dict[str, list[str]] = {}  # campaign_id -> item_ids
        self.logger = logger.bind(service="approval_store")

    def create(self, item: ApprovalItem) -> ApprovalItem:
        """Add a new item to the approval queue."""
        self._items[item.id] = item

        # Index by organization
        if item.organization_id not in self._by_org:
            self._by_org[item.organization_id] = []
        self._by_org[item.organization_id].append(item.id)

        # Index by campaign
        if item.campaign_id:
            if item.campaign_id not in self._by_campaign:
                self._by_campaign[item.campaign_id] = []
            self._by_campaign[item.campaign_id].append(item.id)

        # Add audit log entry
        self._add_audit_entry(
            action="created",
            item_id=item.id,
            user_id=None,
            organization_id=item.organization_id,
            details={"rig": item.rig, "polecat_type": item.polecat_type},
        )

        self.logger.info(
            "Approval item created",
            item_id=item.id,
            rig=item.rig,
            polecat_type=item.polecat_type,
            approval_type=item.approval_type.value,
        )
        return item

    def get(self, item_id: str) -> ApprovalItem | None:
        """Get an approval item by ID."""
        return self._items.get(item_id)

    def get_queue(
        self,
        organization_id: str,
        status: ApprovalStatus | None = ApprovalStatus.PENDING,
        approval_type: ApprovalType | None = None,
        rig: str | None = None,
        urgency: Urgency | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ApprovalItem], int]:
        """Get items in the approval queue with filters."""
        item_ids = self._by_org.get(organization_id, [])
        items = [self._items[iid] for iid in item_ids if iid in self._items]

        # Apply filters
        if status:
            items = [i for i in items if i.status == status]
        if approval_type:
            items = [i for i in items if i.approval_type == approval_type]
        if rig:
            items = [i for i in items if i.rig == rig]
        if urgency:
            items = [i for i in items if i.urgency == urgency]

        # Sort by urgency (critical first) then by creation time
        urgency_order = {Urgency.CRITICAL: 0, Urgency.HIGH: 1, Urgency.NORMAL: 2, Urgency.LOW: 3}
        items.sort(key=lambda x: (urgency_order.get(x.urgency, 99), x.created_at))

        total = len(items)
        items = items[offset:offset + limit]

        return items, total

    def get_counts(self, organization_id: str) -> dict[str, Any]:
        """Get counts of pending items by various dimensions."""
        item_ids = self._by_org.get(organization_id, [])
        items = [self._items[iid] for iid in item_ids if iid in self._items]
        pending = [i for i in items if i.status == ApprovalStatus.PENDING]

        by_type = {}
        by_urgency = {}
        by_rig = {}

        for item in pending:
            # By type
            t = item.approval_type.value
            by_type[t] = by_type.get(t, 0) + 1

            # By urgency
            u = item.urgency.value
            by_urgency[u] = by_urgency.get(u, 0) + 1

            # By rig
            by_rig[item.rig] = by_rig.get(item.rig, 0) + 1

        return {
            "total_pending": len(pending),
            "by_type": by_type,
            "by_urgency": by_urgency,
            "by_rig": by_rig,
        }

    def decide(
        self,
        item_id: str,
        decision: ApprovalStatus,
        user_id: str,
        notes: str | None = None,
        edited_content: str | None = None,
    ) -> ApprovalItem | None:
        """Make a decision on an approval item."""
        item = self._items.get(item_id)
        if not item:
            return None

        if item.status != ApprovalStatus.PENDING:
            self.logger.warning(
                "Cannot decide on non-pending item",
                item_id=item_id,
                current_status=item.status.value,
            )
            return None

        item.status = decision
        item.decided_by = user_id
        item.decided_at = datetime.utcnow()
        item.decision_notes = notes
        if edited_content:
            item.edited_content = edited_content

        # Add audit log entry
        self._add_audit_entry(
            action=decision.value,
            item_id=item_id,
            user_id=user_id,
            organization_id=item.organization_id,
            details={"notes": notes, "had_edits": edited_content is not None},
        )

        self.logger.info(
            "Approval decision made",
            item_id=item_id,
            decision=decision.value,
            user_id=user_id,
        )
        return item

    def expire_items(self) -> int:
        """Mark expired items. Called by Deacon."""
        now = datetime.utcnow()
        expired_count = 0

        for item in self._items.values():
            if item.status == ApprovalStatus.PENDING and item.expires_at and item.expires_at < now:
                item.status = ApprovalStatus.EXPIRED
                self._add_audit_entry(
                    action="expired",
                    item_id=item.id,
                    user_id=None,
                    organization_id=item.organization_id,
                    details={},
                )
                expired_count += 1

        if expired_count > 0:
            self.logger.info("Expired approval items", count=expired_count)

        return expired_count

    def get_audit_log(
        self,
        organization_id: str,
        action: str | None = None,
        user_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLogEntry], int]:
        """Get audit log entries."""
        entries = [e for e in self._audit_log if e.organization_id == organization_id]

        if action:
            entries = [e for e in entries if e.action == action]
        if user_id:
            entries = [e for e in entries if e.user_id == user_id]

        # Sort by timestamp descending (newest first)
        entries.sort(key=lambda x: x.timestamp, reverse=True)

        total = len(entries)
        entries = entries[offset:offset + limit]

        return entries, total

    def _add_audit_entry(
        self,
        action: str,
        item_id: str,
        user_id: str | None,
        organization_id: str,
        details: dict[str, Any],
    ):
        """Add an entry to the audit log."""
        entry = AuditLogEntry(
            id=str(uuid4()),
            action=action,
            item_id=item_id,
            user_id=user_id,
            organization_id=organization_id,
            details=details,
        )
        self._audit_log.append(entry)


# Global singleton instance
_store: ApprovalStore | None = None


def get_approval_store() -> ApprovalStore:
    """Get the global approval store instance."""
    global _store
    if _store is None:
        _store = ApprovalStore()
    return _store
