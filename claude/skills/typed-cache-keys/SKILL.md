---
name: typed-cache-keys
description: Use when building or touching a cache layer in TypeScript — Redis service, cache-key builders, CACHE_KEYS objects, cache invalidation, or wildcard key patterns. Enforces phantom-branded CacheKey<T> / CacheKeyPattern so get/set infer the stored value type from the key.
---

# Typed cache keys

**Shape**

```ts
// shared types (declaration file — type-only, no runtime)
declare const cacheValue: unique symbol;
declare const cachePattern: unique symbol;
export type CacheKey<T> = string & { readonly [cacheValue]: T };
export type CacheKeyPattern = string & { readonly [cachePattern]: true };
```

**Key builders declare the value type**

Each builder returns `CacheKey<TheStoredValue>` (or `CacheKeyPattern` for wildcard invalidators). The string format stays exactly as before — the brand is compile-time only.

```ts
sale: (id: SaleId): CacheKey<Sale> => `sale:id:${id}` as CacheKey<Sale>,
invalidateSales: (id: UserId): CacheKeyPattern =>
  `user:id:${id}:sales*` as CacheKeyPattern,
```

**Cache service infers from the key — never duplicate the type at the call site**

```ts
class RedisService {
  set<T>(key: CacheKey<T>, value: T | null, ttl?: number): Promise<void>;
  get<T>(key: CacheKey<T>): Promise<{ value: T | null } | null>;
  invalidate<T>(key: CacheKey<T>): Promise<void>;
  invalidatePattern(pattern: CacheKeyPattern): Promise<void>;
}

// call sites: no explicit generic
const cached = await redis.get(CACHE_KEYS.sale(id));   // value: Sale | null
await redis.set(CACHE_KEYS.sale(id), saleRow, TTL);    // saleRow must be Sale
```

**Rules of thumb**

- Never type a cache key as plain `string`.
- Never re-pass the value type at the call site (`redis.get<Sale>(...)`); the key already knows.
- A wildcard / pattern key returns `CacheKeyPattern`, not `CacheKey<…>` — they are not interchangeable.
- Invalidating a single key uses `invalidate(key)` (generic infers); deleting many uses `invalidatePattern(pattern)`.
- Brand files live as `.d.ts` to stay out of the build output (no JS emission, keeps `dist/` flat).
