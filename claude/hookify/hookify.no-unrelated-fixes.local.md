---
name: no-unrelated-fixes
enabled: true
event: stop
action: warn
pattern: .*
---

**Scope check before finishing**

You were asked to fix a specific issue. Before stopping, verify:

- [ ] Every file you edited is directly related to the reported issue
- [ ] You did not refactor, clean up, or "improve" code you merely read along the way
- [ ] Any incidental issue you noticed was either **left alone** or **flagged to the user** rather than silently fixed

If you touched unrelated code, revert those changes or ask the user before proceeding.
