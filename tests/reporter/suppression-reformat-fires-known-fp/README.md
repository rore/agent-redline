# suppression-reformat-fires-known-fp

This fixture asserts the spec §6 accepted false positive: a reformat that
removes-and-re-adds a suppression marker fires once on the added line by
design.

The diff removes `foo()  # noqa: E501` and adds `bar()  # noqa: E501` on the
same line. The naive added-line scanner (spec §2.2) walks added lines only,
so it sees one new `# noqa` on the added line and produces one match. The
removed line is invisible to the algorithm by intent.

Cleverer algorithms (set-difference, count-based, per-position pairing) all
leak laundering bypasses where an attacker can swap a tame marker for a
permissive one without firing. See spec §6 for the asymmetry argument.

This fixture is the spec test for that design choice. If you find yourself
"fixing" the false positive, read §6 before changing the algorithm.
