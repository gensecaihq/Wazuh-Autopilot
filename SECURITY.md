# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 3.0.x   | :white_check_mark: |
| < 3.0 (Node runtime line) | :x: |

## Security Model

Wazuh Autopilot is a single platform (FastAPI backend, Strands agent swarm, web UI) that reaches Wazuh only through the [Wazuh MCP Server](https://github.com/gensecaihq/Wazuh-MCP-Server). Controls, from the agents outward:

1. **Agents never hold state-changing Wazuh tools.** Every `wazuh_*` tool except the `wazuh_check_*` verification tools is filtered out of the agents' MCP client, and a pre-tool hook (`ApprovalGate`) cancels any such call as a second layer. Agents call `propose_action`; only the platform executor calls MCP action tools.
2. **Autonomy policy.** `observe`, `recommend` (human approves and executes), `supervised` (human approves, platform executes) or `autonomous` (eligible actions only). Per-action rules set confidence floors, hourly budgets and pinned modes; each agent has an autonomy cap; critical-risk actions always need a human. Uncertain policy state resolves to the more restrictive outcome. See [docs/AUTONOMY_AND_APPROVALS.md](docs/AUTONOMY_AND_APPROVALS.md).
3. **Protected targets.** IPs/CIDRs, hosts, users and agent IDs on the protected list are refused outright, for humans and agents alike.
4. **Separation of duties.** Optional two-person rule: the approver can't also execute. Every executed action is checked with the matching `wazuh_check_*` tool (which infers state from active-response alerts and inventory) and can be rolled back where Wazuh supports it.
5. **RBAC.** Administrator, SOC Manager, Incident Responder, SOC Analyst and Auditor roles, with permissions checked server-side on every endpoint. Scoped API tokens (`apk_…`) are stored hashed.
6. **Audit log.** Logins, failed logins, policy and settings changes, proposals, refusals, approvals, executions, verifications and rollbacks are all recorded with actor and IP.
7. **Secrets.** API keys and webhook tokens are masked in API responses and never written to logs. Passwords use PBKDF2-SHA256.
8. **Deployment defaults.** Non-root container user; the UI/API (8480) binds to `127.0.0.1` by default; `?token=` query credentials are redacted from access logs; alert content is treated as untrusted and wrapped as data in agent prompts (OWASP LLM01).

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: security@gensecai.com

Include the following information:

- Type of vulnerability
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

### Response Timeline

- **24 hours**: Initial acknowledgment
- **72 hours**: Preliminary assessment
- **7 days**: Detailed response with remediation plan
- **90 days**: Public disclosure (coordinated)

## Security Best Practices for Deployment

### Production Checklist

- [ ] Set `POSTGRES_PASSWORD` and `AUTOPILOT_SECRET_KEY` in `.env`
- [ ] Keep the MCP server on a private network (Tailscale, VPN); see [docs/TAILSCALE_MANDATORY.md](docs/TAILSCALE_MANDATORY.md)
- [ ] Put a TLS reverse proxy in front of the UI; keep `AUTOPILOT_BIND` on `127.0.0.1` or a private IP
- [ ] Start at `recommend` or `supervised` autonomy; review per-action rules and protected targets before enabling `autonomous`
- [ ] Enable the two-person rule if your change process requires it
- [ ] Give users the least-privileged role; use Auditor for read-only reviewers
- [ ] Use an MCP key with `wazuh:write` only if you want active response
- [ ] Export traces (OTLP) and back up Postgres

### Secrets Management

Never commit secrets. Put them in `.env` (not committed) or inject them from a secrets manager (AWS Secrets Manager, Vault, …). On AWS compute prefer IAM roles over static keys for Bedrock.

## Security Updates

Security updates are released as patch versions (e.g., 2.0.1, 2.0.2).

Subscribe to releases to receive notifications:
- Watch this repository with "Releases only"
- Check the [Releases](https://github.com/gensecaihq/Wazuh-Autopilot/releases) page

## Acknowledgments

We thank all security researchers who responsibly disclose vulnerabilities.
