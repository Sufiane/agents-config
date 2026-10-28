---
name: branded-types
description: Use when creating, extending or reasoning about TypeScript branded/nominal types — entity ids, money, emails, validated values, Brand<> helpers, shared type folders, or where to cast at a trust boundary. Also use when adding a new entity id or money field to a TS backend or frontend.
---

# Branded types

**Primitive**

```ts
// shared/src/brand.d.ts — declaration file, no JS emission
declare const brand: unique symbol;
export type Brand<T, B extends string> = T & { readonly [brand]: B };
export type Override<T, U> = Omit<T, keyof U> & U;
```

Use `unique symbol` — never a string-literal `__brand` property. Symbol brands cannot be forged structurally.

**Per-category files, no barrel**

Group brands by category, one `.d.ts` per category, no `index.d.ts`:

```
shared/src/
  brand.d.ts
  ids.d.ts        # UserId, SaleId, …
  money.d.ts      # Invest, Profit, ListedPrice, …
  counts.d.ts
  strings.d.ts    # Email, JwtToken, OpponentName, …
  time.d.ts       # SeasonYear, LeadDays
  percentage.d.ts
  cache.d.ts      # CacheKey<T>, CacheKeyPattern
```

Consumers import per category: `import type { UserId } from '@psg/shared/ids'`. Each import line states which slice it depends on.

**Why `.d.ts` not `.ts`**

A `.ts` file gets compiled and emitted; if it lives outside `src/`, tsc widens the inferred `rootDir` to the common parent and `dist/main.js` ends up at `dist/src/main.js`, breaking `node dist/main`. `.d.ts` files are declaration-only — never emitted, never widen rootDir.

**Path mapping (not npm workspace)**

```jsonc
// tsconfig.json
"baseUrl": "./",
"paths": { "@psg/shared/*": ["shared/src/*"] }
```

For SvelteKit/Vite:
```js
// svelte.config.js
kit: { alias: { '@psg/shared/*': '../shared/src/*' } }
```

No npm workspace needed — the brands are type-only, no runtime resolution.

**Trust boundaries: cast once at the edge**

Brands are erased at runtime, so the `as Brand` cast belongs at exactly one place per ingress:

| Boundary | Where |
|---|---|
| DTO field | Type the property directly (`userId: UserId`). `class-validator` runs at runtime; TS sees post-validation field as branded. **No `as` at call sites.** |
| Db service return | Cast the Prisma row once at the return statement (`return row as Sale | null`). Downstream callers receive branded values automatically. |
| JWT payload | Type the `validate(payload)` shape with brands; cast once when constructing the safe user. |
| Frontend API client | Cast the `fetch().json()` result to the branded response type once. |

Values that can be invalid (emails, timezones, scores, amounts, third-party ids) get a validating constructor instead of a bare `as`: a small runtime `.ts` inside the app's `src/` (e.g. `src/common/email.ts` exporting `normalizedEmail(raw): NormalizedEmail`) that throws a snake_case code. Types stay in the `.d.ts`; only the constructor is runtime code. Ids read from the database keep the single `as` cast at the db return.

Inside services, brands flow through with no extra ceremony. Never sprinkle `as UserId` through business logic.

**Wrap Prisma payloads with `Override`**

When a domain entity reuses Prisma's row shape, wrap the id/foreign-key fields:

```ts
export type Sale = Override<
  Prisma.SalesGetPayload<typeof query>,
  {
    id: SaleId;
    userId: UserId;
    matchId: MatchId;
    Match: Override<Row['Match'], {
      Opponent: Override<Row['Match']['Opponent'], { id: OpponentId; name: OpponentName }>;
    }>;
  }
>;
```

One wrapper per entity. Service code reads `sale.userId` as `UserId` end-to-end.

**Distinct money brands**

Unit follows the project's source of truth: whole units where the domain is whole units, integer `Cents` wherever a payment provider (Stripe) is involved. Different roles get different brands: `Invest`, `Profit`, `ListedPrice`, `SeasonPassPrice`, `AvgTicketPrice`, `AvgProfit`. Don't unify behind a single `Money` brand — the whole point is preventing `profit` swapped with `invest` in a calc.

**Anti-patterns to refuse**

- `type Foo = string & { __brand: 'Foo' }` — string-literal brand is forgeable. Use `unique symbol`.
- Re-exporting brands from a barrel — adds a load-bearing file with no value and obscures dependencies.
- `import { UserId } from '@psg/shared/ids'` for a type-only use — must be `import type` so tsc elides at emit and `verbatimModuleSyntax` is satisfied if turned on.
- Casting in business logic (`service.foo(sale.id as SaleId)`) — means a boundary upstream was missed.
