#!/usr/bin/env bash
# scripts/package-skill.sh
#
# Builds dist/agent-redline/ from this repo's source-of-truth files,
# in the layout the Agent Skills standard expects (https://agentskills.io).
#
# The skill is then drop-in installable into any Agent-Skills-compatible
# tool: Claude Code (~/.claude/skills/), Codex, Cursor, Gemini CLI, etc.
#
# Sources:
#   core/skill/                       → SKILL.md (entry), bootstrap-mode.md, operating-mode.md
#   core/templates/skills/            → references/per-checkpoint/
#   core/templates/*.template / *.sh  → assets/templates/
#   core/schema/                      → assets/schema/
#   core/reporter/reporter.py         → scripts/agent-redline-report.py
#   extensions/                       → extensions/
#
# Path substitutions are applied to skill markdown so internal references
# point at the new locations inside the package.
#
# Usage:
#   scripts/package-skill.sh                # build to dist/agent-redline/
#   scripts/package-skill.sh --dest <path>  # build to a custom path
#
# Exit codes:
#   0 — build succeeded
#   1 — script error

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$REPO_ROOT/dist/agent-redline"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dest) DEST="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

# ----------------------------------------------------------------------
# Sanity checks on sources.
# ----------------------------------------------------------------------

required_paths=(
  "core/skill/agent-redline.md"
  "core/skill/bootstrap-mode.md"
  "core/skill/operating-mode.md"
  "core/templates/skills"
  "core/templates/agent-policy.yaml.template"
  "core/templates/AGENTS.md.template"
  "core/templates/pr-template.md"
  "core/templates/pre-push-check.sh"
  "core/schema/agent-policy.schema.json"
  "core/reporter/reporter.py"
  "extensions/spring-archunit"
)
for p in "${required_paths[@]}"; do
  [[ -e "$REPO_ROOT/$p" ]] || { echo "error: missing source $p" >&2; exit 1; }
done

# ----------------------------------------------------------------------
# Wipe destination and build fresh.
# ----------------------------------------------------------------------

rm -rf "$DEST"
mkdir -p "$DEST/references/per-checkpoint" \
         "$DEST/assets/templates" \
         "$DEST/assets/schema" \
         "$DEST/scripts" \
         "$DEST/extensions"

# ----------------------------------------------------------------------
# Path-substitution helper.
#
# Skill markdown contains references to repo-root paths (core/templates/skills/,
# core/templates/, core/reporter/, etc.) that don't exist inside the package.
# We rewrite them at build time so the agent reads the right paths from the
# skill root.
# ----------------------------------------------------------------------

substitute_paths() {
  local src="$1" dst="$2"
  python3 - "$src" "$dst" <<'PYEOF'
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
text = src.read_text(encoding="utf-8")

# Substitutions for skill files (paths from core/ to package-root-relative).
substitutions = [
    ("core/templates/skills/", "references/per-checkpoint/"),
    ("core/templates/", "assets/templates/"),
    ("core/schema/", "assets/schema/"),
    ("core/reporter/reporter.py", "scripts/agent-redline-report.py"),
    ("core/reporter/", "scripts/"),
]
for old, new in substitutions:
    text = text.replace(old, new)

dst.write_text(text, encoding="utf-8")
PYEOF
}

substitute_extension_paths() {
  # Extension files in the source repo use ../../docs/X.md to reference
  # agent-redline project docs. Inside the package those docs don't
  # exist; replace with absolute GitHub URLs.
  local src="$1" dst="$2"
  python3 - "$src" "$dst" <<'PYEOF'
import re
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
text = src.read_text(encoding="utf-8")

base = "https://github.com/rore/agent-redline/blob/main/"

# [text](../../docs/FILE.md) → [text](<base>docs/FILE.md)
# [text](../../README.md)    → [text](<base>README.md)
text = re.sub(
    r"\]\(\.\./\.\./([^)]+)\)",
    lambda m: f"]({base}{m.group(1)})",
    text,
)

dst.write_text(text, encoding="utf-8")
PYEOF
}

copy_plain() {
  cp "$1" "$2"
}

# ----------------------------------------------------------------------
# 1. Entry: core/skill/agent-redline.md → SKILL.md (with substitutions).
#    The Agent Skills standard requires the entry file be named SKILL.md.
# ----------------------------------------------------------------------

substitute_paths "$REPO_ROOT/core/skill/agent-redline.md" "$DEST/SKILL.md"

# ----------------------------------------------------------------------
# 2. Mode files at the package root.
# ----------------------------------------------------------------------

substitute_paths "$REPO_ROOT/core/skill/bootstrap-mode.md" "$DEST/bootstrap-mode.md"
substitute_paths "$REPO_ROOT/core/skill/operating-mode.md" "$DEST/operating-mode.md"

# ----------------------------------------------------------------------
# 3. Per-checkpoint reference docs.
# ----------------------------------------------------------------------

for f in "$REPO_ROOT"/core/templates/skills/*.md; do
  name=$(basename "$f")
  substitute_paths "$f" "$DEST/references/per-checkpoint/$name"
done

# ----------------------------------------------------------------------
# 4. Stack-neutral templates.
# ----------------------------------------------------------------------

cp "$REPO_ROOT/core/templates/agent-policy.yaml.template" "$DEST/assets/templates/"
cp "$REPO_ROOT/core/templates/AGENTS.md.template"        "$DEST/assets/templates/"
cp "$REPO_ROOT/core/templates/pr-template.md"            "$DEST/assets/templates/"
cp "$REPO_ROOT/core/templates/pre-push-check.sh"         "$DEST/assets/templates/"
chmod +x "$DEST/assets/templates/pre-push-check.sh"

# ----------------------------------------------------------------------
# 5. Schema.
# ----------------------------------------------------------------------

cp "$REPO_ROOT/core/schema/agent-policy.schema.json" "$DEST/assets/schema/"
cp "$REPO_ROOT/core/schema/boundary-violations.schema.json" "$DEST/assets/schema/"

# ----------------------------------------------------------------------
# 6. Reporter.
# ----------------------------------------------------------------------

cp "$REPO_ROOT/core/reporter/reporter.py" "$DEST/scripts/agent-redline-report.py"
chmod +x "$DEST/scripts/agent-redline-report.py"
# The tuner is invoked from inside the skill during bootstrap Phase 3b
# (PR-history calibration). It runs against the consuming repo via `gh`
# and writes nothing into the repo; bootstrap calls it from the skill's
# own scripts/ directory rather than vendoring it.
#
# The tuner imports classification logic from the reporter via
# `from core.reporter.reporter import ...`. In the source repo that
# resolves to core/reporter/reporter.py; in the packaged skill, core/
# doesn't ship. We solve this by ALSO shipping the reporter at
# scripts/_reporter.py — a private importable copy with a name that
# is a valid Python identifier (the user-facing copy is
# scripts/agent-redline-report.py, which has hyphens and can't be
# imported). The tuner has a try/except that imports from _reporter
# in the dist and from core.reporter in the source repo.
cp "$REPO_ROOT/scripts/agent-redline-tune.py" "$DEST/scripts/agent-redline-tune.py"
chmod +x "$DEST/scripts/agent-redline-tune.py"
cp "$REPO_ROOT/core/reporter/reporter.py" "$DEST/scripts/_reporter.py"

# ----------------------------------------------------------------------
# 7. Extensions. Each extension is a self-contained folder of markdown +
#    adapter.yaml + an optional scripts/ subdirectory (for adapters when
#    the boundary backend has no machine-readable output — see
#    docs/EXTENSIONS.md § "Backends without machine-readable output").
#
#    Markdown files get reference rewriting (../../docs/X.md → absolute
#    GitHub URL) so they resolve from inside the package. Non-markdown
#    files (adapter.yaml, scripts) are copied verbatim. Test fixtures
#    (_test_fixture/) are excluded from the package.
# ----------------------------------------------------------------------

for ext_dir in "$REPO_ROOT"/extensions/*/; do
  ext_name=$(basename "$ext_dir")
  mkdir -p "$DEST/extensions/$ext_name"
  for src_file in "$ext_dir"/*; do
    base=$(basename "$src_file")
    # Skip test fixtures — they're for local validation, not packaged.
    if [[ "$base" == _test_fixture ]] || [[ "$base" == _* ]]; then
      continue
    fi
    if [[ -d "$src_file" ]]; then
      # Recursively copy subdirectories (e.g. scripts/), preserving executability.
      cp -r "$src_file" "$DEST/extensions/$ext_name/$base"
      # Drop nested test fixtures under any subdir. Match any directory whose
      # name starts with `_test_fixture` (`_test_fixture`, `_test_fixture_multipkg`, ...).
      find "$DEST/extensions/$ext_name/$base" -type d -name '_test_fixture*' -prune -exec rm -rf {} +
      # Make .py files in scripts/ executable.
      if [[ "$base" == "scripts" ]]; then
        find "$DEST/extensions/$ext_name/$base" -type f -name '*.py' -exec chmod +x {} +
      fi
    elif [[ "$src_file" == *.md ]]; then
      substitute_extension_paths "$src_file" "$DEST/extensions/$ext_name/$base"
    else
      cp "$src_file" "$DEST/extensions/$ext_name/$base"
    fi
  done
done

# ----------------------------------------------------------------------
# 8. Top-level package README pointing at SKILL.md and the install paths.
# ----------------------------------------------------------------------

cat > "$DEST/README.md" <<'EOF'
# agent-redline (packaged skill)

This directory is a self-contained [Agent Skills](https://agentskills.io)
package. Drop it into your harness's skills directory:

| Harness | Install path |
|---|---|
| Claude Code (personal) | `~/.claude/skills/agent-redline/` |
| Claude Code (project) | `<your-repo>/.claude/skills/agent-redline/` |
| Codex / Cursor / Gemini CLI / others | See the harness's own docs |

Then start a session. The skill activates when you ask to set up
agent-redline in a repo, or when you work in a repo that already has
`agent-policy.yaml` at the root.

## Layout

```
agent-redline/
├── SKILL.md                            # entry (Agent Skills standard)
├── bootstrap-mode.md                   # one-time setup instructions
├── operating-mode.md                   # everyday loop
├── references/per-checkpoint/          # detail docs the agent loads on demand
├── assets/templates/                   # files bootstrap copies into consuming repos
├── assets/schema/                      # agent-policy.yaml + boundary-violations.json schemas
├── scripts/agent-redline-report.py     # the reporter (vendored into consuming repos)
└── extensions/
    ├── spring-archunit/                # JVM/Spring + ArchUnit (junit-xml output)
    └── python/                         # Python services + libraries + import-linter
                                        # (json-violations output via scripts/run-import-linter.py)
```

This package is generated from the agent-redline source repo
(<https://github.com/rore/agent-redline>) by `scripts/package-skill.sh`.
EOF

# ----------------------------------------------------------------------
# 9. Stamp the package with a version marker for drift detection.
#    This isn't a manifest — just a plain file the drift check reads.
# ----------------------------------------------------------------------

(cd "$REPO_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo "unknown") \
  > "$DEST/.package-source-rev"

echo "built $DEST"
echo
echo "files: $(find "$DEST" -type f | wc -l | tr -d ' ')"
