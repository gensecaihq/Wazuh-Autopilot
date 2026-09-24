# Contributing to Wazuh Autopilot

Thank you for your interest in contributing to Wazuh Autopilot! This document provides guidelines and information for contributors.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How to Contribute

### Reporting Issues

- **Bug Reports**: Use the GitHub issue tracker with the "bug" label
- **Feature Requests**: Use the GitHub issue tracker with the "enhancement" label
- **Security Issues**: Please report security vulnerabilities privately to the maintainers

When reporting bugs, please include:
- Operating system and version
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (with secrets redacted)

### Pull Requests

1. **Fork the repository**
   ```bash
   git clone https://github.com/gensecaihq/Wazuh-Autopilot.git
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed

4. **Test your changes**
   ```bash
   cd backend && pytest -q      # backend suite (41 tests)
   cd ../ui && npm run build    # type-checks and builds the UI
   ```

5. **Commit with a clear message**
   ```bash
   git commit -m "feat: Add new feature description"
   ```

6. **Push and create a Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Format

We follow conventional commits:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Example:
```
feat: Add Teams integration support

- Add Teams webhook to notification settings
- Add tests for the notifier
- Document Teams setup
```

## Development Setup

### Prerequisites

- Python 3.12, Node.js 22, Docker (for the demo stack)

### Local Development

```bash
git clone https://github.com/gensecaihq/Wazuh-Autopilot.git
cd Wazuh-Autopilot

# backend
cd backend && python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
AUTOPILOT_DATA_DIR=./data AUTOPILOT_DEMO_MODE=true uvicorn app.main:app --port 8480

# UI (proxies /api to :8480)
cd ../ui && npm ci && npm run dev

# full demo stack (mock Wazuh MCP server, Postgres, seeded history)
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d --build
```

### Testing

- New features need tests; every bug fix needs a regression test
- `cd backend && pytest -q` and `cd ui && npm run build` must pass before a PR
- Skills must cite Wazuh rule IDs as `rule N` / `rules N, M`, only IDs that exist in the official ruleset. After adding one, regenerate `backend/tests/fixtures/wazuh_rule_refs.json` with `backend/scripts/build_wazuh_rule_refs.py <ruleset/rules dir>`; `test_wazuh_skills.py` checks IDs, stated levels and tool grants

## Project Structure

```
Wazuh-Autopilot/
├── backend/            FastAPI + Strands swarm (agents, skills, policy, executor)
│   ├── app/skills/     Agent Skills (SKILL.md), including the IR playbooks
│   └── tests/          pytest suite
├── ui/                 React + TypeScript + Tailwind
├── mock-wazuh/         Simulated Wazuh MCP server for demos
├── docs/               Documentation
└── docker-compose.yml  Platform + Postgres (+ demo overlay)
```

## Adding Agents and Skills

- **Agents:** add an entry to `backend/app/roster.py` (persona, skills, standards, allowed tools, handoffs). `test_roster_skills.py` checks that skills and tools exist and that no agent gets an active-response tool.
- **Skills:** add `backend/app/skills/<id>/SKILL.md` (AgentSkills format; put long reference material in `references/`), then assign it to agents. Custom skills can also be created in the UI.

## Style Guidelines

### YAML

- Use 2-space indentation
- Include comments for complex configurations
- Group related settings together

### Python

- Match the existing style (type hints, small modules, SQLAlchemy 2.0)
- Keep agent-facing tool docstrings accurate: they're what the model sees

### TypeScript

- Strict mode; types in `ui/src/api/types.ts` mirror `docs/API.md`

### Shell Scripts

- Use `#!/usr/bin/env bash`
- Include `set -euo pipefail`
- Add color-coded logging
- Provide user feedback

### Documentation

- Use clear, concise language
- Include code examples
- Keep tables for structured information
- Add links to related documents

## Release Process

1. Update version numbers in relevant files
2. Update CHANGELOG (if maintained)
3. Create a GitHub release with release notes
4. Tag the release

## Questions?

- Open a GitHub Discussion for general questions
- Check existing issues before creating new ones
- Join the community discussions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Wazuh Autopilot!
