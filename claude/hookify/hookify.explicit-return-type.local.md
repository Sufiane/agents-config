---
name: explicit-return-type
enabled: true
event: file
conditions:
  - field: file_path
    operator: regex_match
    pattern: (^|/)(api|server|backend)/.*\.(ts)$
  - field: new_text
    operator: regex_match
    pattern: ^[ \t]*(public |private |protected |static |async |export |default |abstract )*[a-zA-Z_$][\w$]*\s*\([^)]*\)\s*\{
---

⚠️ **Backend function is missing an explicit return type.**

Every function/method in the backend must declare its return type. This is enforced by the `@typescript-eslint/explicit-function-return-type` rule and is also a personal convention.

**Bad:**
```ts
async register(dto: RegisterDto) {
  ...
}

one(id: string) {
  return this.db.findOne(id);
}
```

**Good:**
```ts
async register(dto: RegisterDto): Promise<AuthResponse> {
  ...
}

one(id: string): Promise<Foo> {
  return this.db.findOne(id);
}
```

Even `Promise<void>` and `void` must be explicit. Local arrow callbacks passed inline to `.map`/`.filter`/`.forEach` are exempt — only named functions and class methods need declared return types.
