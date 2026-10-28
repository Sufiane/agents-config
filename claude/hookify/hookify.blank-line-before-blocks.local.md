---
name: blank-line-before-blocks
enabled: true
event: file
action: warn
conditions:
  - field: new_text
    operator: regex_match
    pattern: "[^\\n\\s][^\\n]*\\n[ \\t]*(for|if|while|return)[\\s(]"
---

⚠️ **Missing blank line before block statement**

The code you're writing has a `for`, `if`, `while`, or `return` statement that is not preceded by a blank line.

**Required style:**
```typescript
// ✅ CORRECT — blank line before block
const x = getValue();

if (x > 0) {
  ...
}

for (const item of items) {
  ...
}

return result;

// ❌ WRONG — no blank line
const x = getValue();
if (x > 0) {
  ...
}
```

Please add a blank line before the block statement.
