# Expected verdict

```
agent-redline: RED
Red-zone files changed.

| Zone | Files |
|---|---|
| Red | src/main/java/com/example/orders/domain/Order.java |

Required checkpoints:
- [x] architecture-review — red-zone change: src/main/java/com/example/orders/domain/Order.java
      (satisfied by label `architecture-reviewed` or CODEOWNER approval)
```

Exit code 0 (checkpoint satisfied). CI green. PR can merge.
