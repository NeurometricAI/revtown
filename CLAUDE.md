# CLAUDE.md — RevTown

> "Kubernetes for GTM Agents" — An autonomous go-to-market execution platform built on the Gastown architecture.

---

## Project Overview

RevTown is a distributed agent-orchestration infrastructure for revenue operations. It is **not** a chatbot or a dashboard with AI features. It is an OS for GTM work: spawn short-lived specialized workers (Polecats), track all state in a versioned ledger (Beads in Dolt), gate every output through quality checks (Refinery + Witness), and route every LLM call through the Neurometric evaluation gateway.

The two foundational principles:
1. **Context is the enemy of scale.** Decompose every revenue motion into atomic, ledger-tracked units of work.
2. **Models are infrastructure, not oracles.** Every AI call is evaluated by Neurometric to determine whether the right model and compute budget was used.

---

## Architecture Concepts (Use These Terms Consistently)

| Term | What It Is |
|---|---|
| **GTM Mayor** | The single orchestration agent. Takes a goal + budget + horizon, produces a Campaign Convoy, monitors feedback, re-slates Beads dynamically. |
| **Bead** | A versioned unit of state stored in Dolt. Types: `LeadBead`, `AssetBead`, `CampaignBead`, `CompetitorBead`, `TestBead`, `PluginBead`, `ModelRegistryBead`, `ICPBead`, `JournalistBead`. |
| **Polecat** | An ephemeral single-task agent. Spawned, executed, terminated. Never holds state — state lives in Beads. |
| **Convoy** | A sequenced set of Beads distributed across Rigs, created by the Mayor for a campaign. |
| **Rig** | A domain-specific subsystem (Content Factory, SDR Hive, Social Command, Press Room, etc.). Each Rig runs as a Kubernetes namespace; Polecats run as ephemeral Jobs within it. |
| **Refinery** | Automated quality gate: brand voice, spam score, SEO grade, legal flags, hallucination likelihood. Runs before any output touches the real world. |
| **Witness** | Second-pass AI agent that checks Bead history for contradictions, duplicate outreach, and consistency violations. |
| **Deacon** | Background janitor process: cleans dead leads, retires orphaned Polecats, monitors thresholds, triggers Neurometric eval loops, pings the Mayor. |
| **Approval Dashboard** | Human-in-the-loop checkpoint (`/approve`). All high-stakes outputs queue here before send. |

---

## Repository Structure

```
revtown/
├── apps/
│   ├── web/                    # React + Tailwind frontend (3-panel SPA)
│   │   ├── admin/              # /admin — Rig management, config, plugins
│   │   ├── approve/            # /approve — Approval Dashboard
│   │   └── optimize/           # /optimize — Analytics & Neurometric dashboard
│   └── api/                    # FastAPI backend
│       ├── routers/
│       │   ├── beads.py
│       │   ├── polecats.py
│       │   ├── approval.py
│       │   ├── plugins.py
│       │   └── neurometric.py
│       ├── core/
│       │   ├── mayor.py        # GTM Mayor orchestration logic
│       │   ├── deacon.py       # Background task runner
│       │   ├── refinery.py     # Quality gate checks
│       │   └── witness.py      # Contradiction/dupe checker
│       └── models/             # Bead type schemas (Pydantic)
├── rigs/
│   ├── content_factory/        # Rig 1 — Inbound content
│   ├── sdr_hive/               # Rig 2 — Outbound SDR
│   ├── social_command/         # Rig 3 — Social media
│   ├── press_room/             # Rig 4 — PR & journalist outreach
│   ├── intelligence_station/   # Rig 5 — Competitor monitoring
│   ├── landing_pad/            # Rig 6 — Landing pages & A/B testing
│   ├── wire/                   # Rig 7 — Human SMS CRM front end
│   └── repo_watch/             # Rig 8 — GitHub monitoring
├── polecats/
│   ├── base.py                 # BasePolecat class — all Polecats inherit this
│   └── [rig_name]/             # Polecat implementations per Rig
├── plugins/
│   ├── registry/               # Plugin manifest parsing and validation
│   └── examples/               # Example plugin implementations
├── infra/
│   ├── k8s/                    # Kubernetes manifests (one namespace per Rig)
│   ├── temporal/               # Temporal.io workflow definitions
│   └── vault/                  # Secrets management config (no secrets committed)
├── db/
│   └── schema/                 # Dolt schema definitions for all Bead types
└── CLAUDE.md
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | Temporal.io (durable Polecat execution with retries) |
| State / Ledger | Dolt (git-backed relational DB — all Beads live here) |
| Message queue | Kafka or AWS SQS (Bead event bus) |
| API | FastAPI (Python) |
| Frontend | React + Tailwind CSS, three-panel SPA |
| SMS | Twilio Messaging API |
| Deployment | Kubernetes — Rigs as namespaces, Polecats as Jobs |
| LLM Gateway | Neurometric API (`neurometric.ai`) — **all LLM calls must route here** |
| Landing pages | Vercel (programmatic deploy via Vercel API) |
| Secrets | HashiCorp Vault or AWS Secrets Manager |

---

## LLM Usage Rules — Neurometric Gateway

**Every AI API call must be routed through the Neurometric gateway. No direct calls to Claude, OpenAI, or any model provider.**

### Current Model Registry (source of truth: `ModelRegistryBead`)

| Task Class / Polecat Type | Default Model | Status |
|---|---|---|
| Blog draft (long-form) | Claude Sonnet | ✅ Confirmed optimal |
| Email personalization | Claude Haiku | ✅ Confirmed sufficient |
| Competitor analysis | Claude Opus | ⚠️ Under evaluation |
| Subject line A/B | Claude Haiku | ✅ Confirmed sufficient |
| PR pitch drafting | Claude Sonnet | ✅ Confirmed optimal |
| Statistical significance | Claude Sonnet | ✅ Confirmed optimal |

When writing a Polecat that makes an LLM call:
1. Fetch the current recommended model from `ModelRegistryBead` for that task class.
2. Route the call via `neurometric_client.complete(task_class=..., prompt=..., context=...)`.
3. Never hardcode a model name inside a Polecat. Always defer to the registry.

The Deacon triggers Neurometric's shadow-testing loop weekly. Results update `ModelRegistryBead` automatically.

---

## Polecat Implementation Pattern

All Polecats inherit from `BasePolecat`. They must:
- Accept a `bead_id` at instantiation (their sole state input)
- Read context from the Bead ledger via `BeadStore`
- Call LLMs through the Neurometric client only
- Write output back as a new or updated Bead
- Pass output through `Refinery` then `Witness` before writing a `status: ready_for_approval` Bead
- Self-terminate cleanly on success or failure (log failure to Bead, do not throw silently)

```python
class MyPolecat(BasePolecat):
    task_class = "my_task_class"

    async def execute(self):
        bead = await self.bead_store.get(self.bead_id)
        result = await self.neurometric.complete(
            task_class=self.task_class,
            prompt=self.build_prompt(bead),
        )
        refined = await self.refinery.check(result, rules=self.refinery_rules)
        witnessed = await self.witness.verify(refined, bead_history=bead.history)
        await self.bead_store.write_output(self.bead_id, witnessed)
```

---

## Bead Conventions

- Beads are Pydantic models persisted in Dolt.
- Every Bead must have: `id`, `type`, `campaign_id`, `created_at`, `updated_at`, `status`, `version`.
- Bead mutations are commits in Dolt — never overwrite in place.
- To revert a bad AI decision: `dolt checkout <bead_id> <prior_commit>`.
- Bead event types for webhooks: `bead.created`, `bead.updated`, `bead.reverted`.

---

## Security Requirements

Security is a primary concern. Apply these rules everywhere:

- **No secrets in code or Beads.** All credentials live in Vault/Secrets Manager. Polecats receive credentials via injected environment at runtime — never stored in Bead fields.
- **API authentication:** API key per organization + HMAC signature verification on all webhook events.
- **Approval Dashboard actions** must be signed with authenticated user identity and logged to the Bead ledger.
- **Beads encrypted at rest** in Dolt.
- **Input validation** on all API endpoints — treat all external input as untrusted.
- **Neurometric gateway** inherits Neurometric's security model. Raw provider API keys never appear inside Polecats.
- **SMS (The Wire):** Never send automated unsolicited SMS. The Wire is human-assisted only — AI drafts, human sends. This is both a compliance requirement (CAN-SPAM, GDPR, TCPA) and a design invariant. Enforce this at the routing layer, not just the UI.
- When in doubt on any security decision: fail closed, require explicit approval, log the event.

---

## Human-in-the-Loop Rules

These are non-negotiable design invariants:

| Output Type | Gate |
|---|---|
| Journalist pitches | Always require human approval — no exceptions |
| SMS messages | Always require human approval (The Wire) |
| Cold outbound email sequences | Configurable: default requires approval |
| Blog posts / landing pages | Configurable: low-risk can auto-publish |
| A/B test winner declarations | Require human approval before promotion |
| Any output with Refinery score below threshold | Force to approval queue |

The Approval Dashboard (`/approve`) is the mechanism for all of the above. Build it to be fast: one-click Approve / Edit & Approve / Reject / Send Back.

---

## Refinery Check Standards

Refinery checks vary by Rig but the following are universal minimums:

- **Outbound email:** Spam score < 3, personalization depth > 70%, CAN-SPAM + GDPR jurisdiction check
- **Blog / content:** Brand voice score, Flesch reading ease, keyword density, duplicate content fingerprint
- **PR pitches:** AP Style compliance, claim verification flag, no hallucinated quotes or statistics
- **Social posts:** Character count validation, platform policy compliance, no hallucinated statistics
- **Landing pages:** Lighthouse score check, conversion element validation before Vercel deploy

---

## Plugin Architecture

Plugins are self-contained modules registered via `revtown-plugin.json` manifest. Each plugin may:
- Register Polecat templates
- Register Refinery check functions
- Register new Bead types
- Declare required credentials (surfaced in Admin Panel)
- Expose a `/health` endpoint monitored by the Deacon

When building or modifying plugin support:
- Validate manifests strictly on registration
- Plugin credentials are injected at runtime via the same Vault mechanism as core Polecats
- The Deacon polls plugin health endpoints; unhealthy plugins are flagged in the Admin Panel, not silently disabled

---

## API Conventions

- Base path: `/api/v1/`
- Auth: `Authorization: Bearer <org_api_key>` on all endpoints
- Webhook payloads: JSON + `X-RevTown-Signature` HMAC header
- All responses follow: `{ data: ..., meta: { version, timestamp } }`
- Errors follow: `{ error: { code, message, bead_id? } }`
- Polecat spawn is async — return a `polecat_id` immediately; poll `/polecats/{id}/status` or subscribe via webhook

---

## Deployment Notes

- Each Rig deploys as its own Kubernetes namespace.
- Polecats deploy as Kubernetes `Job` objects — ephemeral by design.
- Temporal.io handles durable execution, retries, and timeout management for Polecats.
- The Mayor and Deacon run as long-lived `Deployment` objects.
- Local development: use `docker-compose` to run Dolt, Kafka, and the API locally. Temporal can run in dev mode.
- The system is dual-delivery: hosted SaaS (with account creation, billing via Stripe, and auth) and open-source self-hosted. The core engine must work in both modes. Feature flags control SaaS-only capabilities.

---

## What Not To Do

- Do not make direct LLM calls. All calls go through Neurometric.
- Do not store secrets in Beads, environment files committed to git, or any Polecat source.
- Do not let a Polecat hold state between tasks. If it needs context, it reads a Bead.
- Do not send SMS automatically. The Wire is human-assisted only — enforce at the router level.
- Do not delete Beads. Archive them. Dolt versioning is the audit trail.
- Do not hardcode model names in Polecats. Read from `ModelRegistryBead`.
- Do not skip the Refinery + Witness gate for any output that reaches the real world.
- Do not build the Approval Dashboard as an afterthought. It is a primary interface and a compliance requirement.
