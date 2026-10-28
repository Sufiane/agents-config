---
name: no-folder-name-repeat
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: ([^/]+)/\1[.\-_]
---

**File name repeats its folder name**

The file you're writing has a name that echoes its parent folder, which is redundant. Files inside a folder already inherit the folder's context — the file name should only describe what the file *does*, not where it lives.

**Examples:**
```
❌ grant-xp/grant-xp.db.service.ts   → folder name repeated
❌ claim/claim.usecase.ts             → folder name repeated

✅ grant-xp/db.service.ts            → functional name
✅ claim/usecase.ts                   → functional name
✅ daily-challenges/config.ts         → functional name
```

Rename the file to describe its role only (e.g. `db.service.ts`, `usecase.ts`, `types.ts`).
