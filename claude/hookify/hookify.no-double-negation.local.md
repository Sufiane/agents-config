---
name: no-double-negation
enabled: true
event: file
action: block
conditions:
  - field: file_path
    operator: regex_match
    pattern: \.tsx?$
  - field: new_text
    operator: regex_match
    pattern: "!![a-zA-Z_$\(]"
---

❌ **Double negation (`!!`) is not allowed for boolean coercion.**

Use `Boolean(...)` instead:

```ts
// ❌
const isActive = !!value;

// ✅
const isActive = Boolean(value);
```
