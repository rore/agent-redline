# Blue-only PR

Adds a `customerNotes` field to `OrderRow` (the persistence-internal DTO).
This is a blue-zone change: tests pass, no contract surface touched, no
checkpoint required.
