# orders — minimal hexagonal FastAPI service

Used as the source fixture for [`agent-redline-python-demo`](https://github.com/rore/agent-redline-python-demo). Smallest possible FastAPI service that has all the layers agent-redline's Python extension expects to find:

```
src/orders/
├── api/                 # FastAPI routers (HIGH layer)
│   └── orders_router.py
├── application/         # use cases / orchestrators
│   └── place_order.py
├── domain/              # entities + port interfaces (LOW layer)
│   ├── order.py
│   └── repositories/
│       └── orders_repository.py
└── infrastructure/      # adapters (live OUTSIDE the layered stack;
    │                      they may import domain to implement its ports)
    ├── db/
    │   └── in_memory_orders.py
    └── email/
        └── stub_sender.py
```

This fixture is paired with `demo-source-python/` (the agent-redline artifacts the demo repo carries) by `scripts/sync-python-demo.sh`.

## Run locally

```bash
pip install -e '.[dev]'
pytest
python scripts/run-import-linter.py --out build/import-linter-report.json   # if running outside CI
```

## Why this minimal

The demo's job is to make the three canonical agent-redline verdicts visible (BLUE / RED-checkpoint / BOUNDARY_VIOLATION). Every line beyond what's needed for that goal is a maintenance cost; the service is therefore deliberately tiny.
