# Team Setup Guide

Get okf-tools working with your Kiro IDE in under 5 minutes. No installation required — the shared deployment handles everything.

## Prerequisites

- Kiro installed on your Windows machine
- SSH access to 10.81.2.23 (ask your team lead if you don't have this)
- Kiro connected to the server via Remote-SSH

## Setup (One-Time)

### Step 1: Create the MCP config

On the Linux server, create the file `~/.kiro/settings/mcp.json`:

```bash
mkdir -p ~/.kiro/settings
cat > ~/.kiro/settings/mcp.json << 'EOF'
{
  "mcpServers": {
    "okf-tools": {
      "command": "/home/electra/trunk/m3/castle_sdx/etc/okf-tools/.venv/bin/okf-mcp",
      "args": [
        "--bundle-path",
        "/home/electra/trunk/m3/castle_sdx/etc/team-okf"
      ],
      "autoApprove": [
        "commit_concept",
        "delete_concept",
        "fetch_concepts",
        "get_stats",
        "init_bundle",
        "list_concepts",
        "reindex",
        "show_concept",
        "update_concept"
      ]
    }
  }
}
EOF
```

Or using `$BRODIR`:

```bash
mkdir -p ~/.kiro/settings
cat > ~/.kiro/settings/mcp.json << EOF
{
  "mcpServers": {
    "okf-tools": {
      "command": "$BRODIR/etc/okf-tools/.venv/bin/okf-mcp",
      "args": [
        "--bundle-path",
        "$BRODIR/etc/team-okf"
      ],
      "autoApprove": [
        "commit_concept",
        "delete_concept",
        "fetch_concepts",
        "get_stats",
        "init_bundle",
        "list_concepts",
        "reindex",
        "show_concept",
        "update_concept"
      ]
    }
  }
}
EOF
```

### Step 2: Connect Kiro

1. Open Kiro on Windows
2. Connect to the server via Remote-SSH (host: 10.81.2.23)
3. Open any workspace

Kiro will automatically detect the MCP config and connect to the okf-tools server.

### Step 3: Verify

In the Kiro chat, type:

> list all concepts in the knowledge bundle

Or:

> get the bundle stats

You should see results from the team knowledge base.

## How It Works

```
┌──────────────────────────────────┐
│  Windows Desktop                 │
│  ┌────────────────────────────┐  │
│  │  Kiro (Remote-SSH)         │  │
│  └────────────┬───────────────┘  │
└───────────────┼──────────────────┘
                │ SSH
                ▼
┌──────────────────────────────────────────────────┐
│  Linux Server (10.81.2.23)                       │
│                                                  │
│  ~/.kiro/settings/mcp.json                       │
│    → tells Kiro to spawn okf-mcp                 │
│                                                  │
│  $BRODIR/etc/okf-tools/.venv/bin/okf-mcp         │
│    → MCP server process (started by Kiro)        │
│                                                  │
│  $BRODIR/etc/team-okf/                           │
│    → shared knowledge bundle (markdown + index)  │
└──────────────────────────────────────────────────┘
```

- Kiro runs on the server via Remote-SSH
- It reads your `~/.kiro/settings/mcp.json` and spawns `okf-mcp` directly
- No SSH wrapper in the MCP config — Kiro is already on the server
- No `pip install` needed — the shared venv at `$BRODIR/etc/okf-tools/` is pre-built

## Important Notes

- **Shared bundle** — commits are visible to all team members immediately
- **No install needed** — the MCP server and venv are deployed centrally
- **Auto-approve** — all tools are pre-approved so Kiro won't prompt for confirmation
- **First search may be slow** — the embedding model (~30MB) downloads on first use, then is cached

## Available Tools

Your agent now has these tools available via the MCP connection:

| Tool | What it does |
|------|-------------|
| `fetch_concepts` | Search with natural language (hybrid keyword + semantic) |
| `show_concept` | Read full concept content |
| `list_concepts` | Browse concepts with optional filters |
| `commit_concept` | Add new knowledge to the bundle |
| `update_concept` | Modify an existing concept |
| `delete_concept` | Remove a concept |
| `get_stats` | Bundle health and statistics |
| `reindex` | Rebuild the search index |
| `init_bundle` | Create a new bundle (rarely needed) |

## Troubleshooting

### MCP not connecting

1. Check the config file exists: `cat ~/.kiro/settings/mcp.json`
2. Test the server manually: `/home/electra/trunk/m3/castle_sdx/etc/okf-tools/.venv/bin/okf-mcp --bundle-path /home/electra/trunk/m3/castle_sdx/etc/team-okf` (should hang silently — Ctrl+C to exit)
3. Reconnect MCP from Kiro's command palette

### "No bundle configured" error

The bundle path in your config doesn't exist. Verify: `ls /home/electra/trunk/m3/castle_sdx/etc/team-okf/.okf/config.json`

### Tools not appearing

Restart Kiro or reconnect Remote-SSH. The MCP config is only read on connection.
