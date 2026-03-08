# RevTown

> "Kubernetes for GTM Agents" — An autonomous go-to-market execution platform built on the Gastown architecture.

## Overview

RevTown is a distributed agent-orchestration infrastructure for revenue operations. It is not a chatbot or a dashboard with AI features. It is an OS for GTM work: spawn short-lived specialized workers (Polecats), track all state in a versioned ledger (Beads in Dolt), gate every output through quality checks (Refinery + Witness), and route every LLM call through the Neurometric evaluation gateway.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 18+
- Poetry (Python package manager)

### Local Development

1. **Clone and setup:**
   ```bash
   git clone <repository-url>
   cd revtown
   make install
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your Neurometric API key and other credentials
   ```

3. **Start services:**
   ```bash
   make dev
   ```

4. **Initialize database:**
   ```bash
   make db-init
   ```

5. **Access the application:**
   - API: http://localhost:8000
   - Frontend: http://localhost:5173
   - Temporal UI: http://localhost:8088
   - Vault: http://localhost:8200

## Architecture

### Core Concepts

| Term | What It Is |
|------|------------|
| **GTM Mayor** | The orchestration agent that creates Campaign Convoys |
| **Bead** | A versioned unit of state stored in Dolt |
| **Polecat** | An ephemeral single-task agent |
| **Convoy** | A sequenced set of Beads for a campaign |
| **Rig** | A domain-specific subsystem (namespace) |
| **Refinery** | Automated quality gate |
| **Witness** | Consistency and contradiction checker |
| **Deacon** | Background janitor process |

### Rigs

1. **Content Factory** - Inbound content creation
2. **SDR Hive** - Outbound sales development
3. **Social Command** - Social media management
4. **Press Room** - PR and journalist outreach
5. **Intelligence Station** - Competitor monitoring
6. **Landing Pad** - Landing pages and A/B testing
7. **The Wire** - Human-assisted SMS CRM
8. **Repo Watch** - GitHub monitoring

## Development

### Commands

```bash
make dev          # Start all services
make test         # Run tests
make lint         # Run linters
make format       # Format code
make typecheck    # Type checking
```

### Project Structure

```
revtown/
├── apps/
│   ├── web/          # React frontend
│   └── api/          # FastAPI backend
├── rigs/             # Rig implementations
├── polecats/         # Polecat definitions
├── plugins/          # Plugin system
├── infra/            # Infrastructure configs
└── db/               # Database schemas
```

## Deployment

RevTown supports two deployment modes:

- **SaaS** - Hosted platform with auth, billing, and multi-tenancy
- **Self-hosted** - Full-featured open-source deployment

See [deployment documentation](docs/deployment.md) for details.

## Security

- All secrets managed via HashiCorp Vault
- API key + HMAC webhook verification
- Beads encrypted at rest
- No direct LLM calls - all routed through Neurometric

## License

[License details]
