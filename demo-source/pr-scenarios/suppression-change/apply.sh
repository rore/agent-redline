#!/usr/bin/env bash
# pr-scenarios/suppression-change/apply.sh
#
# Mutates a clean main checkout to produce the suppression-change-pr diff:
# adds @SuppressWarnings("ArchUnit") on OrderController to demonstrate the
# suppression-detection feature.

set -euo pipefail

CONTROLLER="src/main/java/com/example/orders/controller/OrderController.java"
[[ -f "$CONTROLLER" ]] || { echo "error: $CONTROLLER not found" >&2; exit 1; }

python3 <<'PYEOF'
from pathlib import Path
p = Path("src/main/java/com/example/orders/controller/OrderController.java")
text = p.read_text(encoding="utf-8")
if '@SuppressWarnings("ArchUnit")' not in text:
    text = text.replace(
        "@RestController\n@RequestMapping(\"/orders\")\npublic class OrderController {",
        "@SuppressWarnings(\"ArchUnit\")\n@RestController\n@RequestMapping(\"/orders\")\npublic class OrderController {",
    )
    p.write_text(text, encoding="utf-8")
    print("modified OrderController.java")
else:
    print("already modified")
PYEOF
