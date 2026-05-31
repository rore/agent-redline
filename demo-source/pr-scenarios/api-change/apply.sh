#!/usr/bin/env bash
# pr-scenarios/api-change/apply.sh
#
# Mutates a clean main checkout to add a /orders/{id}/cancel endpoint
# to OrderController. This produces a real API change that
# springdoc-openapi-gradle-plugin will pick up at build time and that
# the reporter will see as a structural diff between the base spec and
# the head spec.
#
# Also adds a cancel() method to OrderService so the controller has
# something to delegate to. OrderService is on the watch list, so this
# adds a watch-row to the PR comment. Domain Order.java already has a
# CANCELLED status from the red-with-checkpoint scenario's vocabulary,
# but we won't add cancel() to Order.java here — the demo focuses on
# the API surface change, not the domain change.

set -euo pipefail

CONTROLLER="src/main/java/com/example/orders/controller/OrderController.java"
SERVICE="src/main/java/com/example/orders/application/OrderService.java"

[[ -f "$CONTROLLER" ]] || { echo "error: $CONTROLLER not found" >&2; exit 1; }
[[ -f "$SERVICE" ]] || { echo "error: $SERVICE not found" >&2; exit 1; }

python3 <<'PYEOF'
from pathlib import Path

# Add cancelOrder endpoint to OrderController.
controller_path = Path("src/main/java/com/example/orders/controller/OrderController.java")
controller_text = controller_path.read_text(encoding="utf-8")
if "cancelOrder" not in controller_text:
    insert_after = '    @PostMapping("/{id}/ship")\n'
    new_endpoint = '''
    @PostMapping("/{id}/cancel")
    public ResponseEntity<Void> cancelOrder(@PathVariable UUID id) {
        orderService.cancelOrder(id);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/{id}/ship")
'''
    controller_text = controller_text.replace(
        "\n    @PostMapping(\"/{id}/ship\")\n",
        new_endpoint,
    )
    controller_path.write_text(controller_text, encoding="utf-8")
    print("modified OrderController.java (added /orders/{id}/cancel)")
else:
    print("OrderController.java already modified")

# Add cancelOrder method to OrderService — delegates to a domain operation.
service_path = Path("src/main/java/com/example/orders/application/OrderService.java")
service_text = service_path.read_text(encoding="utf-8")
if "cancelOrder" not in service_text:
    new_method = '''
    public void cancelOrder(UUID orderId) {
        Order order = repository.findById(orderId)
            .orElseThrow(() -> new NoSuchElementException("order not found: " + orderId));
        // Domain doesn't yet support cancellation; for the demo we treat
        // any non-shipped order as cancellable and just remove it.
        // A real change here would land via the architecture-review
        // checkpoint as a domain modification.
        if (order.status() == Order.Status.SHIPPED) {
            throw new IllegalStateException("cannot cancel a shipped order");
        }
    }
'''
    # Insert before the final closing brace.
    service_text = service_text.rstrip()
    if service_text.endswith("}"):
        service_text = service_text[:-1].rstrip() + "\n" + new_method + "\n}\n"
    service_path.write_text(service_text, encoding="utf-8")
    print("modified OrderService.java (added cancelOrder)")
else:
    print("OrderService.java already modified")
PYEOF
