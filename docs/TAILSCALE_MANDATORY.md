# Tailscale for Production Networking

Wazuh Autopilot talks to two things over the network: the Wazuh MCP Server and your model provider. For production we recommend putting Autopilot and the MCP server on a Tailscale tailnet so neither is exposed publicly.

The platform doesn't enforce Tailscale. It connects to whatever `mcp_url` you configure, so it's up to you to keep that path private: Tailscale, a corporate VPN or mTLS.

## Why Tailscale

- **No public exposure.** The MCP server holds a key that can run active response. It should never be reachable from the internet.
- **Identity-based access.** Connections are tied to machine identities and restricted by ACLs.
- **Encrypted and logged.** WireGuard transport, connection audit logs.
- **Simple addressing.** MagicDNS names like `wazuh-mcp.your-tailnet.ts.net`, and it works through NAT without firewall changes.

## What to keep private

| Endpoint | Default bind | Guidance |
|---|---|---|
| Autopilot UI/API | `127.0.0.1:8480` | Put a TLS reverse proxy in front, or expose only on the tailnet (`AUTOPILOT_BIND=<tailscale-ip>`) |
| Wazuh MCP Server | `127.0.0.1:3000` | Tailnet only |

## Setup

### 1. Install Tailscale on the Autopilot host and the MCP host

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

### 2. Tag the machines

```bash
sudo tailscale up --advertise-tags=tag:autopilot   # Autopilot host
sudo tailscale up --advertise-tags=tag:mcp         # MCP host
```

### 3. Restrict with ACLs

```json
{
  "acls": [
    {"action": "accept", "src": ["tag:autopilot"], "dst": ["tag:mcp:3000"]}
  ],
  "tagOwners": {
    "tag:autopilot": ["autogroup:admin"],
    "tag:mcp": ["autogroup:admin"]
  }
}
```

### 4. Point Autopilot at the tailnet address

Set **Settings → Wazuh MCP → MCP server base URL** (or `WAZUH_MCP_URL` in `.env` before first boot) to the MagicDNS name, e.g. `https://wazuh-mcp.your-tailnet.ts.net:3000`, then click **Test connection**.

## Verifying

```bash
tailscale status                                            # both machines online
curl https://wazuh-mcp.your-tailnet.ts.net:3000/health      # from the Autopilot host
```

In Autopilot, **Agent Health** shows the Wazuh MCP component as healthy with the number of read tools available to agents.

## Troubleshooting

| Symptom | Check |
|---|---|
| MCP "down" in Agent Health | `tailscale status` on both hosts; MCP listening (`ss -tlnp \| grep 3000`); ACL allows `tag:autopilot → tag:mcp:3000` |
| Container can't resolve MagicDNS names | Use the tailnet IP, or run Tailscale on the Docker host with MagicDNS enabled for containers |

## Alternatives

A corporate VPN, mTLS between Autopilot and the MCP server, or an SSH tunnel all work too. Whatever you pick, the MCP server stays off the public internet.

## Reference

- [Tailscale documentation](https://tailscale.com/kb/)
- [Tailscale ACLs](https://tailscale.com/kb/1018/acls/)
- [DEPLOYMENT.md](DEPLOYMENT.md)
