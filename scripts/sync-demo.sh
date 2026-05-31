#!/usr/bin/env bash
# scripts/sync-demo.sh
#
# Populates the agent-redline-demo repo from this repo's demo-source/
# (agent-redline artifacts) and examples/spring-hexagonal/ (Spring source).
#
# Builds two branches:
#   - greenfield: bare Spring service, no agent-redline artifacts
#   - main:       greenfield + all agent-redline artifacts (bootstrapped state)
#
# Optionally builds the three PR-scenario branches off main.
#
# Usage:
#   scripts/sync-demo.sh --target /path/to/agent-redline-demo
#   scripts/sync-demo.sh --target ../agent-redline-demo --with-pr-branches
#   scripts/sync-demo.sh --target ../agent-redline-demo --push      # also push branches
#
# Safety:
#   - Refuses to operate on a target that has uncommitted changes (unless --force).
#   - Each branch is built fresh from a clean state, then committed.
#   - Reporter is vendored as-of-this-commit; out-of-date copies in the target
#     get replaced.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_SOURCE="$REPO_ROOT/demo-source"
SPRING_FIXTURE="$REPO_ROOT/examples/spring-hexagonal"
REPORTER="$REPO_ROOT/core/reporter/reporter.py"

TARGET=""
WITH_PR_BRANCHES=0
DO_PUSH=0
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --with-pr-branches) WITH_PR_BRANCHES=1; shift ;;
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

# Sanity: make sure we have what we need to copy.
[[ -d "$DEMO_SOURCE" ]] || { echo "error: $DEMO_SOURCE missing" >&2; exit 1; }
[[ -d "$SPRING_FIXTURE/src" ]] || { echo "error: $SPRING_FIXTURE/src missing" >&2; exit 1; }
[[ -f "$REPORTER" ]] || { echo "error: $REPORTER missing" >&2; exit 1; }

# Sanity: target has no uncommitted changes.
cd "$TARGET"
if [[ $FORCE -eq 0 ]]; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "error: $TARGET has uncommitted changes. Stash, commit, or pass --force." >&2
    exit 1
  fi
fi

echo "==> sync-demo target: $TARGET"

# ----------------------------------------------------------------------
# Helper: rsync-like copy that mirrors a tree, replacing destination contents.
# ----------------------------------------------------------------------
copy_spring_source() {
  # Copy only the Spring fixture's source/build, NOT its README, .gitignore, build/, bin/, etc.
  local dest="$1"
  cp -r "$SPRING_FIXTURE/src" "$dest/"
  cp "$SPRING_FIXTURE/build.gradle" "$dest/"
  cp "$SPRING_FIXTURE/settings.gradle" "$dest/"
}

copy_demo_artifacts() {
  # Copy demo-source/ contents into target, except pr-scenarios/ (consumed separately)
  # and the README.md (which is the demo-repo-facing one).
  local dest="$1"
  cp "$DEMO_SOURCE/agent-policy.yaml" "$dest/"
  cp "$DEMO_SOURCE/AGENTS.md" "$dest/"
  cp "$DEMO_SOURCE/README.md" "$dest/"
  cp "$DEMO_SOURCE/CODEOWNERS" "$dest/"
  cp "$DEMO_SOURCE/LICENSE" "$dest/"
  cp "$DEMO_SOURCE/CONTRIBUTING.md" "$dest/"

  mkdir -p "$dest/docs/agent" "$dest/scripts" "$dest/.github/workflows"
  cp "$DEMO_SOURCE/docs/agent/"*.md "$dest/docs/agent/"
  if [[ -f "$DEMO_SOURCE/docs/agent-redline-ci-proposal.md" ]]; then
    cp "$DEMO_SOURCE/docs/agent-redline-ci-proposal.md" "$dest/docs/"
  fi
  cp "$DEMO_SOURCE/scripts/agent-redline-check.sh" "$dest/scripts/"
  chmod +x "$dest/scripts/agent-redline-check.sh"
  cp "$DEMO_SOURCE/.github/pull_request_template.md" "$dest/.github/"
  cp "$DEMO_SOURCE/.github/workflows/agent-redline.yml" "$dest/.github/workflows/"

  # Vendor the reporter.
  cp "$REPORTER" "$dest/scripts/agent-redline-report.py"
  chmod +x "$dest/scripts/agent-redline-report.py"
}

write_gitignore() {
  cat > "$1/.gitignore" <<'EOF'
build/
bin/
.gradle/
*.class
__pycache__/
*.pyc
.DS_Store
EOF
}

clean_worktree() {
  # Remove everything in the worktree except .git/.
  cd "$TARGET"
  find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
}

# ----------------------------------------------------------------------
# Build the greenfield branch.
# ----------------------------------------------------------------------
echo "==> building greenfield branch"
cd "$TARGET"
# Detect default branch / first commit state.
git checkout --orphan greenfield 2>/dev/null || git checkout greenfield
clean_worktree
copy_spring_source "$TARGET"
write_gitignore "$TARGET"

# A README that explains this is a starting point, no agent-redline artifacts.
cat > "$TARGET/README.md" <<'EOF'
# agent-redline-demo — greenfield

Bare Spring Boot service in hexagonal layout. **No** `agent-policy.yaml`,
**no** `AGENTS.md`, **no** per-checkpoint docs, **no** CI workflow.

This branch is the starting point for testing **agent-redline bootstrap mode**.
Drop the agent-redline skill into a Claude Code or Codex session pointed at
a checkout of this branch, ask the agent to set up agent-redline, and observe
what it produces.

The expected output is roughly what the `main` branch already has. See the
`main` branch README for the post-bootstrap state.
EOF

git add -A
if git diff --cached --quiet; then
  echo "    (greenfield branch already up to date)"
else
  git commit -m "greenfield: bare Spring service for bootstrap-mode testing" >/dev/null
  echo "    greenfield commit: $(git rev-parse --short HEAD)"
fi

# ----------------------------------------------------------------------
# Build the main branch.
# ----------------------------------------------------------------------
echo "==> building main branch"
cd "$TARGET"
git checkout --orphan main-rebuild 2>/dev/null || git checkout main-rebuild 2>/dev/null || true
# Use a fresh orphan branch to avoid history entanglement.
git branch -D main-rebuild 2>/dev/null || true
git checkout --orphan main-rebuild
clean_worktree
copy_spring_source "$TARGET"
copy_demo_artifacts "$TARGET"
write_gitignore "$TARGET"

git add -A
git commit -m "main: bootstrapped state with agent-redline artifacts

Spring service from agent-redline:examples/spring-hexagonal/ +
agent-redline-specific artifacts from agent-redline:demo-source/ +
the vendored reporter from agent-redline:core/reporter/reporter.py." >/dev/null
MAIN_SHA=$(git rev-parse HEAD)
echo "    main-rebuild commit: $(git rev-parse --short HEAD)"

# Replace main with main-rebuild.
git branch -D main 2>/dev/null || true
git branch -m main-rebuild main
git checkout main >/dev/null 2>&1 || true
echo "    main is now $(git rev-parse --short HEAD)"

# ----------------------------------------------------------------------
# Optionally build PR scenario branches.
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

    if [[ -x "$scenario/apply.sh" ]]; then
      bash "$scenario/apply.sh"
    else
      bash "$scenario/apply.sh"
    fi

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
# Push if requested.
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

    # ------------------------------------------------------------------
    # PR showcase: ensure each scenario has an OPEN PR against main, with
    # the canonical scenario description as the PR body. Force-pushing the
    # branch closes any prior PR; we recreate it so the demo always shows
    # three live PRs.
    #
    # Requires `gh` on PATH and an authenticated session for the target
    # repo. If `gh` is missing, we skip silently and tell the user.
    # ------------------------------------------------------------------
    if ! command -v gh >/dev/null 2>&1; then
      echo "    (gh not installed; skipping PR creation. Open the three demo PRs manually if you want the showcase.)"
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

          # Title = first line of description.md without the leading '# '
          title=$(head -1 "$scenario/description.md" | sed -E 's/^#+ +//')
          # Body = description.md sans the title line
          body=$(tail -n +2 "$scenario/description.md")

          # Close any open PR pointing at this branch (sync overwrote
          # history; the prior PR is stale).
          existing=$(gh pr list --repo "$target_slug" --head "$branch" --state open --json number --jq '.[].number' 2>/dev/null || true)
          for n in $existing; do
            gh pr close "$n" --repo "$target_slug" --comment "Closing stale PR; demo branch was rebuilt by sync-demo.sh. A fresh PR will be opened immediately." >/dev/null 2>&1 || true
          done

          # Create the fresh PR.
          new_pr=""
          if gh pr create --repo "$target_slug" --base main --head "$branch" --title "$title" --body "$body" 2>/dev/null; then
            new_pr=$(gh pr list --repo "$target_slug" --head "$branch" --state open --json number --jq '.[0].number' 2>/dev/null || true)
            echo "    PR opened: $branch (#$new_pr)"
          else
            echo "    (PR creation failed for $branch; create manually at https://github.com/$target_slug/compare/main...$branch)"
          fi

          # Apply scenario-specific labels if labels.txt exists. One label
          # per line. Labels must already exist in the target repo (the
          # checkpoint labels — architecture-reviewed, api-reviewed,
          # persistence-reviewed — should be created on first setup).
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
fi

echo
echo "done. demo branches in $TARGET:"
cd "$TARGET"
git branch -a 2>&1 | head -20
