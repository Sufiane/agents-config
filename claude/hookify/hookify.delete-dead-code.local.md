---
name: delete-dead-code
enabled: true
event: stop
pattern: .*
---

Before stopping, review every file you edited in this session and remove dead code.

**Dead code to delete:**
- Commented-out code blocks (not explanatory comments)
- Unused imports
- Unused variables, parameters, or functions
- Unreachable code paths
- Leftover debug statements (`console.log`, etc.)

**How to apply:**
1. List the files you modified
2. Re-read each one quickly
3. Remove any dead code you find
4. Do not create new files or refactor — only delete dead code
