# Installing agent-redline

agent-redline is packaged as an [Agent Skills](https://agentskills.io) skill. The standard is supported by Claude Code, Codex, Cursor, Gemini CLI, OpenCode, Goose, and many others.

The packaged skill lives at [`dist/agent-redline/`](dist/agent-redline/) in this repo. Install it by copying that directory into your harness's skills directory.

## Claude Code

### Personal install (recommended for trying it out)

Available across all your projects:

```bash
git clone https://github.com/rore/agent-redline.git
mkdir -p ~/.claude/skills
cp -r agent-redline/dist/agent-redline ~/.claude/skills/
```

Restart Claude Code (or wait for live-reload). The skill activates when:
- you ask the agent to set up agent-redline in a repo (bootstrap mode), or
- you work in a repo that has `agent-policy.yaml` at the root (operating mode).

### Project install

Available only when working on a specific repo. Commit it into the repo:

```bash
git clone https://github.com/rore/agent-redline.git /tmp/agent-redline
mkdir -p .claude/skills
cp -r /tmp/agent-redline/dist/agent-redline .claude/skills/
git add .claude/skills/agent-redline
git commit -m "Add agent-redline skill"
```

### `--add-dir` install (transient)

Drop a clone anywhere and load it for the current session:

```bash
git clone https://github.com/rore/agent-redline.git
claude --add-dir agent-redline/dist
```

## Codex / Cursor / Gemini CLI / others

Each tool has its own skills directory but consumes the same Agent Skills format. Copy `dist/agent-redline/` to the path your tool expects:

| Tool | Path |
|---|---|
| Codex | See <https://developers.openai.com/codex/skills/> |
| Cursor | See <https://cursor.com/docs/context/skills> |
| Gemini CLI | See <https://geminicli.com/docs/cli/skills/> |
| Others | See <https://agentskills.io/clients> for the full list |

The package itself is harness-agnostic; the only thing that varies is where each tool looks for skills.

## Verifying the install

Start a session in any repo. Type `/agent-redline` (or just ask "set up agent-redline for this repo"). If the harness shows the skill or starts the bootstrap conversation, the install worked.

For a structured smoke test, the paired demo repo at <https://github.com/rore/agent-redline-demo> has two long-lived branches:

- `greenfield` — bare Spring service, used to test bootstrap mode
- `main` — already-bootstrapped, used to test operating mode

Clone, point the agent at it, and walk through the scenarios in the demo's README.

## Updating

Pull and re-copy:

```bash
cd /path/to/agent-redline
git pull
cp -r dist/agent-redline ~/.claude/skills/        # or your tool's path
```

The package is regenerated from sources by `scripts/package-skill.sh` — what you copy is always in sync with what's in the repo at that commit.

## Building from source (if you don't trust the committed dist)

Every change to the skill regenerates `dist/agent-redline/` via `scripts/package-skill.sh`. CI verifies the committed package matches the sources. If you'd rather build it yourself:

```bash
git clone https://github.com/rore/agent-redline.git
cd agent-redline
bash scripts/package-skill.sh
# dist/agent-redline/ is now freshly built; copy as above
```

## Uninstall

Delete the directory:

```bash
rm -rf ~/.claude/skills/agent-redline    # personal
rm -rf .claude/skills/agent-redline      # project
```

The skill is self-contained; nothing else needs cleanup.
