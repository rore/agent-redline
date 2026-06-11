#!/usr/bin/env bash
# scripts/sync-python-demo.sh
#
# Populates the agent-redline-python-demo repo from this repo's
# demo-source-python/ (agent-redline artifacts) and examples/python-fastapi/
# (Python source).
#
# Builds two branches:
#   - greenfield: bare FastAPI service, no agent-redline artifacts
#   - main:       greenfield + all agent-redline artifacts (bootstrapped state)
#
# Optionally builds the three PR-scenario branches off main.
#
# Usage:
#   scripts/sync-python-demo.sh --target /path/to/agent-redline-python-demo
#   scripts/sync-python-demo.sh --target ../agent-redline-python-demo --with-pr-branches
#   scripts/sync-python-demo.sh --target ../agent-redline-python-demo --push
#
# Mirrors scripts/sync-demo.sh.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_SOURCE="$REPO_ROOT/demo-source-python"
PYTHON_FIXTURE="$REPO_ROOT/examples/python-fastapi"
REPORTER="$REPO_ROOT/core/reporter/reporter.py"
ADAPTER_SCRIPT="$REPO_ROOT/extensions/python/scripts/run-import-linter.py"

TARGET=""
WITH_PR_BRANCHES=0
WITH_PUSH_DEMO=0
DO_PUSH=0
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --with-pr-branches) WITH_PR_BRANCHES=1; shift ;;
    --with-push-demo) WITH_PUSH_DEMO=1; shift ;;
    --push) DO_PUSH=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "error: --target required" >&2
  exit 1
fi
TARGET="$(cd "$TARGET" 2>/dev/null && pwd || echo "$TARGET")"
[[ -d "$TARGET/.git" ]] || { echo "error: $TARGET is not a git repository" >&2; exit 1; }

[[ -d "$DEMO_SOURCE" ]] || { echo "error: $DEMO_SOURCE missing" >&2; exit 1; }
[[ -d "$PYTHON_FIXTURE/src" ]] || { echo "error: $PYTHON_FIXTURE/src missing" >&2; exit 1; }
[[ -f "$REPORTER" ]] || { echo "error: $REPORTER missing" >&2; exit 1; }
[[ -f "$ADAPTER_SCRIPT" ]] || { echo "error: $ADAPTER_SCRIPT missing" >&2; exit 1; }

cd "$TARGET"
if [[ $FORCE -eq 0 ]]; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "error: $TARGET has uncommitted changes. Stash, commit, or pass --force." >&2
    exit 1
  fi
fi

echo "==> sync-python-demo target: $TARGET"

# ----------------------------------------------------------------------
copy_python_source() {
  local dest="$1"
  cp -r "$PYTHON_FIXTURE/src" "$dest/"
  cp -r "$PYTHON_FIXTURE/tests" "$dest/"
  cp "$PYTHON_FIXTURE/pyproject.toml" "$dest/"
  cp "$PYTHON_FIXTURE/.gitignore" "$dest/"
  # Strip build artifacts that may exist if the fixture was installed editable
  # locally (pip install -e). These are .gitignored normally; we drop them
  # before they ever get tracked in the demo repo.
  find "$dest" \( -name '__pycache__' -o -name '*.egg-info' -o -name '.pytest_cache' -o -name 'build' \) \
    -type d -prune -exec rm -rf {} + 2>/dev/null || true
  find "$dest" -name '*.pyc' -delete 2>/dev/null || true
}

copy_demo_artifacts() {
  local dest="$1"
  cp "$DEMO_SOURCE/agent-policy.yaml" "$dest/"
  cp "$DEMO_SOURCE/AGENTS.md" "$dest/"
  cp "$DEMO_SOURCE/README.md" "$dest/"

  mkdir -p "$dest/scripts" "$dest/.github/workflows" "$dest/.agent-redline"
  cp "$DEMO_SOURCE/scripts/agent-redline-check.sh" "$dest/scripts/"
  chmod +x "$dest/scripts/agent-redline-check.sh"
  cp "$DEMO_SOURCE/.github/workflows/agent-redline.yml" "$dest/.github/workflows/"
  # Vendor the suppression-defaults file the policy points at via
  # useExtensionDefaults: true. Without this the reporter aborts.
  if [[ -f "$DEMO_SOURCE/.agent-redline/suppressions.yaml" ]]; then
    cp "$DEMO_SOURCE/.agent-redline/suppressions.yaml" "$dest/.agent-redline/"
  fi

  # Vendor the reporter and the import-linter adapter.
  cp "$REPORTER" "$dest/scripts/agent-redline-report.py"
  chmod +x "$dest/scripts/agent-redline-report.py"
  cp "$ADAPTER_SCRIPT" "$dest/scripts/run-import-linter.py"
  chmod +x "$dest/scripts/run-import-linter.py"

  # docs/agent/ — copied if/when bootstrap fills demo-source-python/docs/agent/
  if [[ -d "$DEMO_SOURCE/docs/agent" ]]; then
    mkdir -p "$dest/docs/agent"
    cp "$DEMO_SOURCE/docs/agent/"*.md "$dest/docs/agent/" 2>/dev/null || true
  fi
}

clean_worktree() {
  cd "$TARGET"
  find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
}

# ----------------------------------------------------------------------
# greenfield branch
# ----------------------------------------------------------------------
echo "==> building greenfield branch"
cd "$TARGET"
git checkout --orphan greenfield 2>/dev/null || git checkout greenfield
clean_worktree
copy_python_source "$TARGET"

cat > "$TARGET/README.md" <<'EOF'
# agent-redline-python-demo — greenfield

Bare FastAPI service in hexagonal layout. **No** `agent-policy.yaml`,
**no** `AGENTS.md`, **no** import-linter contracts beyond the inherited
`pyproject.toml` block, **no** CI workflow.

This branch is the starting point for testing **agent-redline bootstrap mode**
on a Python repo. Drop the agent-redline skill into a Claude Code or Codex
session pointed at a checkout of this branch, ask the agent to set up
agent-redline, and observe what it produces.

The expected output is roughly what the `main` branch already has.
EOF

git add -A
if git diff --cached --quiet; then
  echo "    (greenfield branch already up to date)"
else
  git commit -m "greenfield: bare FastAPI service for bootstrap-mode testing" >/dev/null
  echo "    greenfield commit: $(git rev-parse --short HEAD)"
fi

# ----------------------------------------------------------------------
# main branch
# ----------------------------------------------------------------------
echo "==> building main branch"
cd "$TARGET"
git branch -D main-rebuild 2>/dev/null || true
git checkout --orphan main-rebuild
clean_worktree
copy_python_source "$TARGET"
copy_demo_artifacts "$TARGET"

git add -A
git commit -m "main: bootstrapped state with agent-redline artifacts

FastAPI service from agent-redline:examples/python-fastapi/ +
agent-redline-specific artifacts from agent-redline:demo-source-python/ +
the vendored reporter (agent-redline:core/reporter/reporter.py) and the
import-linter adapter (agent-redline:extensions/python/scripts/run-import-linter.py)." >/dev/null
echo "    main-rebuild commit: $(git rev-parse --short HEAD)"

git branch -D main 2>/dev/null || true
git branch -m main-rebuild main
git checkout main >/dev/null 2>&1 || true
echo "    main is now $(git rev-parse --short HEAD)"

# ----------------------------------------------------------------------
# PR scenario branches
# ----------------------------------------------------------------------
if [[ $WITH_PR_BRANCHES -eq 1 ]]; then
  for scenario in "$DEMO_SOURCE/pr-scenarios/"*/; do
    name=$(basename "$scenario")
    [[ -f "$scenario/branch.txt" ]] || continue
    branch=$(<"$scenario/branch.txt")
    branch=$(echo "$branch" | tr -d '[:space:]')
    [[ -n "$branch" ]] || continue

    echo "==> building PR branch: $branch ($name)"
    cd "$TARGET"
    git checkout main >/dev/null
    git branch -D "$branch" 2>/dev/null || true
    git checkout -b "$branch" >/dev/null

    bash "$scenario/apply.sh"

    git add -A
    if git diff --cached --quiet; then
      echo "    (no changes — apply.sh produced no diff)"
    else
      git commit -m "$name scenario

$(<"$scenario/description.md")" >/dev/null
      echo "    $branch commit: $(git rev-parse --short HEAD)"
    fi
  done
  cd "$TARGET"
  git checkout main >/dev/null
fi

# ----------------------------------------------------------------------
# Push-mode demo branches
#
# Builds a `push-demo-main` long-lived branch off main with the
# push-mode workflow (instead of the PR-mode one), plus N scenario
# branches under push-demo-* that each show one canonical CI run.
#
# These exercise the push-driven flow end-to-end on real GitHub: each
# push event triggers a workflow run; the verdict surfaces in
# $GITHUB_STEP_SUMMARY at the top of the run page.
# ----------------------------------------------------------------------
PUSH_DEMO_DIR="$DEMO_SOURCE/push-mode"
if [[ $WITH_PUSH_DEMO -eq 1 ]]; then
  if [[ ! -d "$PUSH_DEMO_DIR" ]]; then
    echo "error: --with-push-demo requested but $PUSH_DEMO_DIR is missing" >&2
    exit 1
  fi

  echo "==> building push-demo-main branch (push-mode workflow)"
  cd "$TARGET"
  git checkout main >/dev/null
  git branch -D push-demo-main 2>/dev/null || true
  git checkout -b push-demo-main >/dev/null

  # Replace the PR-mode workflow with the push-mode one.
  cp "$PUSH_DEMO_DIR/.github/workflows/agent-redline.yml" \
     "$TARGET/.github/workflows/agent-redline.yml"

  git add -A
  if git diff --cached --quiet; then
    echo "    (push-demo-main branch already at expected state)"
  else
    git commit -m "push-demo: switch to push-mode workflow

This branch demonstrates agent-redline's push-driven CI flow. The
workflow trigger is `on: push:` instead of pull_request:, the verdict
appears in \$GITHUB_STEP_SUMMARY (run page) instead of a sticky PR
comment, and CI fails on EXIT != 0 (warnings + binding hard fails)
because there's no PR comment surface for non-blocking warnings." >/dev/null
    echo "    push-demo-main commit: $(git rev-parse --short HEAD)"
  fi

  for scenario in "$PUSH_DEMO_DIR/scenarios/"*/; do
    name=$(basename "$scenario")
    [[ -f "$scenario/branch.txt" ]] || continue
    branch=$(<"$scenario/branch.txt")
    branch=$(echo "$branch" | tr -d '[:space:]')
    [[ -n "$branch" ]] || continue

    echo "==> building push-demo branch: $branch ($name)"
    cd "$TARGET"
    git checkout push-demo-main >/dev/null
    git branch -D "$branch" 2>/dev/null || true
    git checkout -b "$branch" >/dev/null

    bash "$scenario/apply.sh"

    git add -A
    if git diff --cached --quiet; then
      echo "    (no changes — apply.sh produced no diff)"
    else
      git commit -m "$name scenario (push-mode demo)

$(<"$scenario/description.md")" >/dev/null
      echo "    $branch commit: $(git rev-parse --short HEAD)"
    fi
  done
  cd "$TARGET"
  git checkout main >/dev/null
fi

# ----------------------------------------------------------------------
# Push (and open PRs) if requested
# ----------------------------------------------------------------------
if [[ $DO_PUSH -eq 1 ]]; then
  echo "==> pushing"
  cd "$TARGET"
  git push -u --force origin main greenfield

  if [[ $WITH_PR_BRANCHES -eq 1 ]]; then
    for scenario in "$DEMO_SOURCE/pr-scenarios/"*/; do
      [[ -f "$scenario/branch.txt" ]] || continue
      branch=$(<"$scenario/branch.txt")
      branch=$(echo "$branch" | tr -d '[:space:]')
      [[ -n "$branch" ]] || continue
      git push -u --force origin "$branch"
    done

    if ! command -v gh >/dev/null 2>&1; then
      echo "    (gh not installed; skipping PR creation)"
    else
      target_remote=$(git config --get remote.origin.url 2>/dev/null || true)
      target_slug=$(echo "$target_remote" | sed -E 's#.*github.com[:/]([^/]+/[^/.]+)(\.git)?$#\1#')
      if [[ -z "$target_slug" || "$target_slug" == "$target_remote" ]]; then
        echo "    (could not determine GitHub slug from $target_remote; skipping PR creation)"
      else
        for scenario in "$DEMO_SOURCE/pr-scenarios/"*/; do
          [[ -f "$scenario/branch.txt" ]] || continue
          [[ -f "$scenario/description.md" ]] || continue
          branch=$(<"$scenario/branch.txt")
          branch=$(echo "$branch" | tr -d '[:space:]')
          [[ -n "$branch" ]] || continue
          title=$(head -1 "$scenario/description.md" | sed -E 's/^#+ +//')
          body=$(tail -n +2 "$scenario/description.md")

          existing=$(gh pr list --repo "$target_slug" --head "$branch" --state open --json number --jq '.[].number' 2>/dev/null || true)
          for n in $existing; do
            gh pr close "$n" --repo "$target_slug" --comment "Closing stale PR; demo branch was rebuilt by sync-python-demo.sh. A fresh PR will be opened immediately." >/dev/null 2>&1 || true
          done

          new_pr=""
          if gh pr create --repo "$target_slug" --base main --head "$branch" --title "$title" --body "$body" 2>/dev/null; then
            new_pr=$(gh pr list --repo "$target_slug" --head "$branch" --state open --json number --jq '.[0].number' 2>/dev/null || true)
            echo "    PR opened: $branch (#$new_pr)"
          else
            echo "    (PR creation failed for $branch; create manually at https://github.com/$target_slug/compare/main...$branch)"
          fi

          if [[ -n "$new_pr" && -f "$scenario/labels.txt" ]]; then
            while IFS= read -r label; do
              label=$(echo "$label" | tr -d '[:space:]')
              [[ -n "$label" ]] || continue
              if gh pr edit "$new_pr" --repo "$target_slug" --add-label "$label" >/dev/null 2>&1; then
                echo "      label applied: $label"
              else
                echo "      (label '$label' not applied — does it exist in the repo?)"
              fi
            done < "$scenario/labels.txt"
          fi
        done
      fi
    fi
  fi

  if [[ $WITH_PUSH_DEMO -eq 1 ]]; then
    echo "==> pushing push-demo branches"
    cd "$TARGET"
    git push -u --force origin push-demo-main
    for scenario in "$PUSH_DEMO_DIR/scenarios/"*/; do
      [[ -f "$scenario/branch.txt" ]] || continue
      branch=$(<"$scenario/branch.txt")
      branch=$(echo "$branch" | tr -d '[:space:]')
      [[ -n "$branch" ]] || continue
      git push -u --force origin "$branch"
    done
    # No PR creation for push-mode — the push event itself triggers CI;
    # the verdict surfaces in the run summary at github.com/<slug>/actions.
    echo "    push-mode demo runs surface at: https://github.com/$(git config --get remote.origin.url \
      | sed -E 's#.*github.com[:/]([^/]+/[^/.]+)(\.git)?$#\1#')/actions"
  fi
fi

echo
echo "done. demo branches in $TARGET:"
cd "$TARGET"
git branch -a 2>&1 | head -20
