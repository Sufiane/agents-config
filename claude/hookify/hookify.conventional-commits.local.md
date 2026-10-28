---
name: conventional-commits
enabled: true
event: bash
pattern: git\s+commit
---

📝 **Conventional Commits — pick the right type**

Before running this `git commit`, double-check the type prefix. The user cares about this; getting it wrong on already-pushed work is unfixable, so do it right the first time.

**Type taxonomy**

| Type | When to use |
|---|---|
| `feat:` | New product capability or new public/observable API. Something a user, a caller, or an API consumer can now do that they couldn't before. |
| `fix:` | Bug fix — code that was producing wrong behavior now produces correct behavior. |
| `refactor:` | Internal restructuring with **no observable behavior change**. Type-only changes, renames, file moves, extracting helpers, branded-type adoption, signature tightening that doesn't add capability. |
| `perf:` | Faster or lighter without changing behavior. |
| `test:` | Adds or fixes tests only. |
| `docs:` | Docs/README/comments only. |
| `chore:` | Tooling, deps, build config, CI — no code change. |
| `build:` | Build system or external dep changes (e.g. tsconfig, webpack). |
| `style:` | Formatting, whitespace, linter cosmetic fixes — no logic change. |

**Common mistakes to avoid**

- **Branded / nominal type adoption → `refactor:`**, not `feat:`. Brands erase at runtime; adding `UserId`, `Profit`, `CacheKey<T>` etc. doesn't add new behavior, it tightens type safety on existing behavior.
- **Renaming, moving, splitting files → `refactor:`**, not `feat:`. No new capability.
- **Tightening a method signature (e.g. `string` → `UserId`) → `refactor:`**, not `feat:`.
- **Adopting a new convention across files → `refactor:`**, not `feat:`.
- **Fixing a typo in a constant that was already correct in the test → `fix:`**, not `chore:`.

**Decision rule**

Ask: "If I describe this change to someone who only sees the running app, what's different for them?"
- Something visibly new → `feat:`
- Something previously wrong now right → `fix:`
- Same observable behavior, cleaner internals → `refactor:`

**Format**

```
type(scope): short imperative summary

Optional longer body explaining the why.
```

- Scope is optional but encouraged: `feat(auth):`, `refactor(redis):`.
- Use `!` after type/scope for breaking changes: `feat(api)!: ...` or include `BREAKING CHANGE:` in body.
- Subject in imperative present ("add", "remove", "rename"), no trailing period.

**If the message has already been written, audit it**

Look at the staged diff. If the diff only contains type signature changes, file renames, or internal restructuring with the same call-site behavior, the prefix should be `refactor:`. Do not let a misleading `feat:` slip through just because new types were added.
