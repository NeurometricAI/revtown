"""
BeadStore - Dolt database client for Bead CRUD operations with versioning.

All Bead mutations are commits in Dolt - never overwrite in place.
To revert a bad AI decision: `dolt checkout <bead_id> <prior_commit>`
"""

import json
from datetime import datetime
from typing import Any, TypeVar
from uuid import UUID, uuid4

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.config import settings
from apps.api.models.beads import (
    BEAD_TYPE_MAP,
    AssetBead,
    AssetBeadCreate,
    AssetBeadUpdate,
    BeadBase,
    CampaignBead,
    CampaignBeadCreate,
    CampaignBeadUpdate,
    CompetitorBead,
    CompetitorBeadCreate,
    CompetitorBeadUpdate,
    ICPBead,
    ICPBeadCreate,
    ICPBeadUpdate,
    JournalistBead,
    JournalistBeadCreate,
    JournalistBeadUpdate,
    LeadBead,
    LeadBeadCreate,
    LeadBeadUpdate,
    ModelRegistryBead,
    ModelRegistryBeadCreate,
    ModelRegistryBeadUpdate,
    PluginBead,
    PluginBeadCreate,
    PluginBeadUpdate,
    TestBead,
    TestBeadCreate,
    TestBeadUpdate,
)

logger = structlog.get_logger()

T = TypeVar("T", bound=BeadBase)


# Table name mapping
BEAD_TABLE_MAP: dict[str, str] = {
    "campaign": "campaign_beads",
    "lead": "lead_beads",
    "asset": "asset_beads",
    "competitor": "competitor_beads",
    "test": "test_beads",
    "icp": "icp_beads",
    "journalist": "journalist_beads",
    "model_registry": "model_registry_beads",
    "plugin": "plugin_beads",
}


class BeadStoreError(Exception):
    """Base exception for BeadStore errors."""

    pass


class BeadNotFoundError(BeadStoreError):
    """Raised when a Bead is not found."""

    pass


class BeadVersionConflictError(BeadStoreError):
    """Raised when there's a version conflict during update."""

    pass


class BeadStore:
    """
    Dolt-backed storage for all Bead types.

    Features:
    - Automatic versioning (version field increments on each update)
    - Organization-scoped data isolation
    - History retrieval via Dolt's git-like versioning
    - Revert capability
    """

    def __init__(self, session: AsyncSession, organization_id: UUID | None = None):
        self.session = session
        self.organization_id = organization_id
        self.logger = logger.bind(organization_id=str(organization_id) if organization_id else None)

    # =========================================================================
    # Generic CRUD Operations
    # =========================================================================

    async def _execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        """Execute a SQL query and return the result."""
        result = await self.session.execute(text(query), params or {})
        return result

    async def _fetch_one(self, query: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Fetch a single row as a dictionary."""
        result = await self._execute(query, params)
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def _fetch_all(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Fetch all rows as a list of dictionaries."""
        result = await self._execute(query, params)
        return [dict(row._mapping) for row in result.fetchall()]

    def _serialize_json_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        """Serialize any dict or list fields to JSON strings."""
        result = {}
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                result[key] = json.dumps(value)
            elif isinstance(value, UUID):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            else:
                result[key] = value
        return result

    def _deserialize_json_fields(self, data: dict[str, Any], json_fields: list[str]) -> dict[str, Any]:
        """Deserialize JSON string fields back to dicts/lists."""
        result = dict(data)
        for field in json_fields:
            if field in result and isinstance(result[field], str):
                try:
                    result[field] = json.loads(result[field])
                except json.JSONDecodeError:
                    pass
        return result

    # =========================================================================
    # Campaign Beads
    # =========================================================================

    async def create_campaign(
        self, data: CampaignBeadCreate, created_by: UUID | None = None
    ) -> CampaignBead:
        """Create a new Campaign Bead."""
        if not self.organization_id:
            raise BeadStoreError("Organization ID is required")

        bead_id = uuid4()
        now = datetime.utcnow()

        params = {
            "id": str(bead_id),
            "type": "campaign",
            "organization_id": str(self.organization_id),
            "name": data.name,
            "description": data.description,
            "goal": data.goal,
            "budget_cents": data.budget_cents,
            "horizon_days": data.horizon_days,
            "settings": json.dumps(data.settings) if data.settings else None,
            "status": "draft",
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "created_by": str(created_by) if created_by else None,
        }

        query = """
            INSERT INTO campaign_beads
            (id, type, organization_id, name, description, goal, budget_cents,
             horizon_days, settings, status, version, created_at, updated_at, created_by)
            VALUES (:id, :type, :organization_id, :name, :description, :goal, :budget_cents,
                    :horizon_days, :settings, :status, :version, :created_at, :updated_at, :created_by)
        """

        await self._execute(query, params)
        await self.session.commit()

        self.logger.info("Campaign bead created", bead_id=str(bead_id), name=data.name)

        return CampaignBead(
            id=bead_id,
            type="campaign",
            organization_id=self.organization_id,
            campaign_id=None,
            name=data.name,
            description=data.description,
            goal=data.goal,
            budget_cents=data.budget_cents,
            horizon_days=data.horizon_days,
            settings=data.settings,
            status="draft",
            version=1,
            created_at=now,
            updated_at=now,
            created_by=created_by,
        )

    async def get_campaign(self, bead_id: UUID) -> CampaignBead:
        """Get a Campaign Bead by ID."""
        query = """
            SELECT * FROM campaign_beads
            WHERE id = :id AND organization_id = :org_id
        """
        row = await self._fetch_one(query, {"id": str(bead_id), "org_id": str(self.organization_id)})

        if not row:
            raise BeadNotFoundError(f"Campaign bead {bead_id} not found")

        row = self._deserialize_json_fields(row, ["settings"])
        return CampaignBead(**row)

    async def update_campaign(
        self, bead_id: UUID, data: CampaignBeadUpdate, expected_version: int | None = None
    ) -> CampaignBead:
        """Update a Campaign Bead with optimistic locking."""
        current = await self.get_campaign(bead_id)

        if expected_version and current.version != expected_version:
            raise BeadVersionConflictError(
                f"Version conflict: expected {expected_version}, found {current.version}"
            )

        update_fields = []
        params = {"id": str(bead_id), "org_id": str(self.organization_id)}

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == "settings" and value is not None:
                params[key] = json.dumps(value)
            else:
                params[key] = value
            update_fields.append(f"{key} = :{key}")

        if not update_fields:
            return current

        params["new_version"] = current.version + 1
        update_fields.append("version = :new_version")
        update_fields.append("updated_at = NOW()")

        query = f"""
            UPDATE campaign_beads
            SET {", ".join(update_fields)}
            WHERE id = :id AND organization_id = :org_id
        """

        await self._execute(query, params)
        await self.session.commit()

        return await self.get_campaign(bead_id)

    async def list_campaigns(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CampaignBead]:
        """List Campaign Beads for the organization."""
        params: dict[str, Any] = {
            "org_id": str(self.organization_id),
            "limit": limit,
            "offset": offset,
        }

        where_clauses = ["organization_id = :org_id"]
        if status:
            where_clauses.append("status = :status")
            params["status"] = status

        query = f"""
            SELECT * FROM campaign_beads
            WHERE {" AND ".join(where_clauses)}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """

        rows = await self._fetch_all(query, params)
        return [
            CampaignBead(**self._deserialize_json_fields(row, ["settings"]))
            for row in rows
        ]

    # =========================================================================
    # Lead Beads
    # =========================================================================

    async def create_lead(self, data: LeadBeadCreate) -> LeadBead:
        """Create a new Lead Bead."""
        if not self.organization_id:
            raise BeadStoreError("Organization ID is required")

        bead_id = uuid4()
        now = datetime.utcnow()

        params = self._serialize_json_fields({
            "id": str(bead_id),
            "type": "lead",
            "organization_id": str(self.organization_id),
            "campaign_id": str(data.campaign_id) if data.campaign_id else None,
            **data.model_dump(exclude={"campaign_id"}),
            "status": "new",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        })

        columns = ", ".join(params.keys())
        placeholders = ", ".join(f":{k}" for k in params.keys())

        query = f"INSERT INTO lead_beads ({columns}) VALUES ({placeholders})"

        await self._execute(query, params)
        await self.session.commit()

        self.logger.info("Lead bead created", bead_id=str(bead_id))

        return await self.get_lead(bead_id)

    async def get_lead(self, bead_id: UUID) -> LeadBead:
        """Get a Lead Bead by ID."""
        query = """
            SELECT * FROM lead_beads
            WHERE id = :id AND organization_id = :org_id
        """
        row = await self._fetch_one(query, {"id": str(bead_id), "org_id": str(self.organization_id)})

        if not row:
            raise BeadNotFoundError(f"Lead bead {bead_id} not found")

        row = self._deserialize_json_fields(row, ["enrichment_data", "tags"])
        return LeadBead(**row)

    async def update_lead(
        self, bead_id: UUID, data: LeadBeadUpdate, expected_version: int | None = None
    ) -> LeadBead:
        """Update a Lead Bead."""
        current = await self.get_lead(bead_id)

        if expected_version and current.version != expected_version:
            raise BeadVersionConflictError(
                f"Version conflict: expected {expected_version}, found {current.version}"
            )

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return current

        params = {"id": str(bead_id), "org_id": str(self.organization_id)}
        update_fields = []

        for key, value in update_data.items():
            serialized = self._serialize_json_fields({key: value})[key]
            params[key] = serialized
            update_fields.append(f"{key} = :{key}")

        params["new_version"] = current.version + 1
        update_fields.append("version = :new_version")
        update_fields.append("updated_at = NOW()")

        query = f"""
            UPDATE lead_beads
            SET {", ".join(update_fields)}
            WHERE id = :id AND organization_id = :org_id
        """

        await self._execute(query, params)
        await self.session.commit()

        return await self.get_lead(bead_id)

    async def list_leads(
        self,
        campaign_id: UUID | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LeadBead]:
        """List Lead Beads for the organization."""
        params: dict[str, Any] = {
            "org_id": str(self.organization_id),
            "limit": limit,
            "offset": offset,
        }

        where_clauses = ["organization_id = :org_id"]
        if campaign_id:
            where_clauses.append("campaign_id = :campaign_id")
            params["campaign_id"] = str(campaign_id)
        if status:
            where_clauses.append("status = :status")
            params["status"] = status

        query = f"""
            SELECT * FROM lead_beads
            WHERE {" AND ".join(where_clauses)}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """

        rows = await self._fetch_all(query, params)
        return [
            LeadBead(**self._deserialize_json_fields(row, ["enrichment_data", "tags"]))
            for row in rows
        ]

    # =========================================================================
    # Asset Beads
    # =========================================================================

    async def create_asset(self, data: AssetBeadCreate) -> AssetBead:
        """Create a new Asset Bead."""
        if not self.organization_id:
            raise BeadStoreError("Organization ID is required")

        bead_id = uuid4()
        now = datetime.utcnow()

        params = self._serialize_json_fields({
            "id": str(bead_id),
            "type": "asset",
            "organization_id": str(self.organization_id),
            "campaign_id": str(data.campaign_id) if data.campaign_id else None,
            **data.model_dump(exclude={"campaign_id"}),
            "status": "draft",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        })

        columns = ", ".join(params.keys())
        placeholders = ", ".join(f":{k}" for k in params.keys())

        query = f"INSERT INTO asset_beads ({columns}) VALUES ({placeholders})"

        await self._execute(query, params)
        await self.session.commit()

        return await self.get_asset(bead_id)

    async def get_asset(self, bead_id: UUID) -> AssetBead:
        """Get an Asset Bead by ID."""
        query = """
            SELECT * FROM asset_beads
            WHERE id = :id AND organization_id = :org_id
        """
        row = await self._fetch_one(query, {"id": str(bead_id), "org_id": str(self.organization_id)})

        if not row:
            raise BeadNotFoundError(f"Asset bead {bead_id} not found")

        row = self._deserialize_json_fields(row, ["keywords"])
        return AssetBead(**row)

    async def update_asset(
        self, bead_id: UUID, data: AssetBeadUpdate, expected_version: int | None = None
    ) -> AssetBead:
        """Update an Asset Bead."""
        current = await self.get_asset(bead_id)

        if expected_version and current.version != expected_version:
            raise BeadVersionConflictError(
                f"Version conflict: expected {expected_version}, found {current.version}"
            )

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return current

        params = {"id": str(bead_id), "org_id": str(self.organization_id)}
        update_fields = []

        for key, value in update_data.items():
            serialized = self._serialize_json_fields({key: value})[key]
            params[key] = serialized
            update_fields.append(f"{key} = :{key}")

        params["new_version"] = current.version + 1
        update_fields.append("version = :new_version")
        update_fields.append("updated_at = NOW()")

        query = f"""
            UPDATE asset_beads
            SET {", ".join(update_fields)}
            WHERE id = :id AND organization_id = :org_id
        """

        await self._execute(query, params)
        await self.session.commit()

        return await self.get_asset(bead_id)

    # =========================================================================
    # History & Revert (Dolt-specific)
    # =========================================================================

    async def get_bead_history(
        self, bead_type: str, bead_id: UUID, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get the version history of a Bead using Dolt's dolt_history table.

        Returns a list of historical versions with commit info.
        """
        table_name = BEAD_TABLE_MAP.get(bead_type)
        if not table_name:
            raise BeadStoreError(f"Unknown bead type: {bead_type}")

        query = f"""
            SELECT h.*, dc.commit_hash, dc.committer, dc.message, dc.date as commit_date
            FROM dolt_history_{table_name} h
            JOIN dolt_commits dc ON h.commit_hash = dc.commit_hash
            WHERE h.id = :bead_id
            ORDER BY dc.date DESC
            LIMIT :limit
        """

        try:
            rows = await self._fetch_all(query, {"bead_id": str(bead_id), "limit": limit})
            return rows
        except Exception as e:
            # Dolt history tables might not exist in non-Dolt MySQL
            self.logger.warning("Failed to get bead history", error=str(e))
            return []

    async def revert_bead(
        self, bead_type: str, bead_id: UUID, to_commit: str
    ) -> dict[str, Any]:
        """
        Revert a Bead to a previous commit using Dolt's checkout.

        This creates a new commit that restores the Bead state.
        """
        table_name = BEAD_TABLE_MAP.get(bead_type)
        if not table_name:
            raise BeadStoreError(f"Unknown bead type: {bead_type}")

        # Use Dolt's checkout to restore the specific row
        query = f"""
            CALL DOLT_CHECKOUT('--', '{table_name}', '--', 'id', :bead_id, '--', 'commit', :commit_hash)
        """

        try:
            await self._execute(query, {"bead_id": str(bead_id), "commit_hash": to_commit})

            # Create a commit for the revert
            commit_query = """
                CALL DOLT_COMMIT('-m', :message)
            """
            message = f"Revert {bead_type} {bead_id} to commit {to_commit[:8]}"
            await self._execute(commit_query, {"message": message})

            await self.session.commit()

            self.logger.info(
                "Bead reverted",
                bead_type=bead_type,
                bead_id=str(bead_id),
                to_commit=to_commit,
            )

            return {"success": True, "message": message}
        except Exception as e:
            self.logger.error("Failed to revert bead", error=str(e))
            raise BeadStoreError(f"Failed to revert bead: {e}")

    async def get_bead_diff(
        self, bead_type: str, bead_id: UUID, from_commit: str, to_commit: str
    ) -> dict[str, Any]:
        """
        Get the diff between two versions of a Bead.
        """
        table_name = BEAD_TABLE_MAP.get(bead_type)
        if not table_name:
            raise BeadStoreError(f"Unknown bead type: {bead_type}")

        query = f"""
            SELECT * FROM dolt_diff_{table_name}
            WHERE id = :bead_id
            AND from_commit = :from_commit
            AND to_commit = :to_commit
        """

        try:
            rows = await self._fetch_all(
                query,
                {
                    "bead_id": str(bead_id),
                    "from_commit": from_commit,
                    "to_commit": to_commit,
                },
            )
            return {"diff": rows}
        except Exception as e:
            self.logger.warning("Failed to get bead diff", error=str(e))
            return {"diff": [], "error": str(e)}

    # =========================================================================
    # Generic Bead Operations
    # =========================================================================

    async def get_bead(self, bead_type: str, bead_id: UUID) -> BeadBase:
        """Get any Bead by type and ID."""
        if bead_type == "campaign":
            return await self.get_campaign(bead_id)
        elif bead_type == "lead":
            return await self.get_lead(bead_id)
        elif bead_type == "asset":
            return await self.get_asset(bead_id)
        else:
            # Generic fetch for other types
            table_name = BEAD_TABLE_MAP.get(bead_type)
            if not table_name:
                raise BeadStoreError(f"Unknown bead type: {bead_type}")

            query = f"""
                SELECT * FROM {table_name}
                WHERE id = :id AND organization_id = :org_id
            """
            row = await self._fetch_one(
                query, {"id": str(bead_id), "org_id": str(self.organization_id)}
            )

            if not row:
                raise BeadNotFoundError(f"{bead_type} bead {bead_id} not found")

            model_class = BEAD_TYPE_MAP.get(bead_type)
            if model_class:
                return model_class(**row)

            return row

    async def archive_bead(self, bead_type: str, bead_id: UUID) -> bool:
        """
        Archive a Bead (never delete - Dolt versioning is the audit trail).
        """
        table_name = BEAD_TABLE_MAP.get(bead_type)
        if not table_name:
            raise BeadStoreError(f"Unknown bead type: {bead_type}")

        query = f"""
            UPDATE {table_name}
            SET status = 'archived', updated_at = NOW(), version = version + 1
            WHERE id = :id AND organization_id = :org_id
        """

        await self._execute(query, {"id": str(bead_id), "org_id": str(self.organization_id)})
        await self.session.commit()

        self.logger.info("Bead archived", bead_type=bead_type, bead_id=str(bead_id))
        return True


# =============================================================================
# Database Engine Setup
# =============================================================================


def create_engine():
    """Create the async SQLAlchemy engine for Dolt."""
    database_url = (
        f"mysql+aiomysql://{settings.dolt_user}:{settings.dolt_password}"
        f"@{settings.dolt_host}:{settings.dolt_port}/{settings.dolt_database}"
    )
    return create_async_engine(database_url, echo=settings.debug)


def create_session_factory():
    """Create the async session factory."""
    engine = create_engine()
    return async_sessionmaker(engine, expire_on_commit=False)


# Singleton session factory
_session_factory: async_sessionmaker | None = None


def get_session_factory() -> async_sessionmaker:
    """Get or create the session factory singleton."""
    global _session_factory
    if _session_factory is None:
        _session_factory = create_session_factory()
    return _session_factory


async def get_bead_store(
    session: AsyncSession, organization_id: UUID | None = None
) -> BeadStore:
    """Dependency injection helper for BeadStore."""
    return BeadStore(session, organization_id)
