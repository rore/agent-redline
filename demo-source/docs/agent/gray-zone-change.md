# gray-zone-change

You're touching gray-zone code. The base rules are in `operating-mode.md`. This doc adds nuance specific to gray zones.

## Gray means "we don't know yet"

Gray zone is not a permanent classification. It's the team's signal that this path hasn't been classified explicitly. The right behavior is to:

- Proceed cautiously for *this* PR
- Surface the gray-zone touch in the PR description
- Suggest a policy update to classify the path explicitly

## grayWatch is different from gray

`grayWatch` paths are highlighted in the PR comment even when they overlap with blue or red rules. Use grayWatch for paths that *look* like one zone but might behave like another (e.g., a DTO file that might be an internal type or might be a contract surface). When you touch a grayWatch path, the reporter draws attention to it — that's the point.

If you touch a grayWatch path, the PR description should answer the question grayWatch is asking. For a DTO grayWatch entry, the question is "is this DTO part of an external contract?" — answer it.

## Recurrent gray suggests classification

If you find yourself working in the same gray path repeatedly, the policy is incomplete. Suggest the path be classified — either by promoting it to red (if it's contract surface) or to blue (if it's internal). Don't keep working it as gray.

## Don't escalate gray to red unilaterally

Gray-zone code does not require a checkpoint. If a specific gray task feels risky enough to deserve human attention, that's a signal the *path* should be red — not that *this PR* should be treated as red. Surface the suggestion; don't reclassify mid-task.
