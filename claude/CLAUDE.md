# Global coding preferences

## Communication style

Always respond in caveman mode (terse: drop articles/filler/pleasantries, fragments OK, abbreviate common terms, keep all technical substance exact). Stays on every session unless I say "stop caveman" or "normal mode". Drop it only for security warnings, destructive-action confirmations, and multi-step sequences where terseness risks misread.

## Pairing — push back, don't just comply

When I propose an approach ("can we do X instead of Y?"), answer whether it's actually worth it *before or alongside* building it — not just "yes, technically possible" followed by silent implementation. If X has real costs (complexity, fragility, no real gain over Y) say so plainly and let me decide, the same way you'd answer if I asked "should we" instead of "can we". Don't wait to be asked "be honest" to give the honest answer. Applies globally, not just code choices.

## Backend architecture — hexagonal split (NestJS / Express / Fastify)

Every module that touches a database **must** split into two layers:

| File | Purpose |
|---|---|
| `*.service.ts` | Business logic only. Validation, orchestration, hashing, signing, domain exceptions. **MUST NOT import Prisma, TypeORM, Mongoose, Knex, or any ORM/query builder.** |
| `*.db.ts` | All data access. The only file in the module that imports the ORM. Methods return raw query results. No domain throws here — return `null`/`undefined` and let the service decide. |

The service depends on the db (`constructor(private readonly db: FooDb) {}`). The controller depends on the service. The db depends on the underlying Prisma/ORM client. Never skip a layer.

Both `service` and `db` are registered as providers in the module:

```ts
@Module({
  controllers: [FooController],
  providers: [FooService, FooDb],
})
export class FooModule {}
```

If a module has no DB access (e.g. `health`), it has no `*.db.ts`.

Example shape:

```ts
// foo.db.ts — only file that imports Prisma
@Injectable()
export class FooDb {
  constructor(private readonly prisma: PrismaService) {}

  findOne(id: string) {
    return this.prisma.foo.findUnique({ where: { id } });
  }
}

// foo.service.ts — no Prisma import
@Injectable()
export class FooService {
  constructor(private readonly db: FooDb) {}

  async one(id: string) {
    const row = await this.db.findOne(id);

    if (!row) {
      throw new NotFoundException();
    }

    return row;
  }
}
```

## Backend architecture — usecase layer for complex operations

When a service method's logic outgrows a simple orchestration-over-db-calls shape (multiple intents routed to different writes, non-trivial business rules, several private helpers that only that one operation needs), extract it into a **usecase**: a sub-service scoped to exactly that one operation, following the same two-file split as the module itself.

- Lives in a `usecases/` subfolder of the owning module, one folder per usecase: `<module>/usecases/<operation-name>/`.
- Same split as everywhere else, just renamed: `<operation-name>.usecase.ts` (business logic, no ORM import) + `<operation-name>.usecase.db.ts` (the only file in that usecase's folder that imports the ORM, scoped to exactly the queries that usecase needs — not the module's whole db surface).
- **Call direction is one-way: controller → service → usecase → usecase's own db.** A usecase is never called by a controller directly, and never calls back up into its owning service. The owning service's public method becomes a thin delegate to the usecase's `execute(...)`.
- Extract a usecase's own db access even when an existing general-purpose `*.db.ts` in the module already has the needed methods — don't leave the usecase depending on the module's full db interface if it only needs a handful of its methods. Exactly how clean this split can be depends on how entangled those methods are with private helpers shared by *other*, unrelated methods on the existing db service — when that entanglement makes a full physical move risky on code that's already hardened/well-tested, it's fine to give the usecase a narrow dedicated interface backed by the same underlying db class (registered under both DI tokens) as an interim step, but say so explicitly rather than silently taking the shortcut, and flag it as a candidate for a follow-up cleanup pass.
- Started 2026-09-13, on `psg_inventory`'s `updateSale` — expect this to still be catching on: don't assume every module needs a usecase layer, and don't retrofit it onto simple CRUD methods that are already a clean, short service→db passthrough.

## TypeScript / JavaScript style

- **Explicit return types on every backend function/method.** Enforced by `@typescript-eslint/explicit-function-return-type` set to `error` in the repo's `eslint.config.mjs`. `explicit-module-boundary-types` is its deprecated subset and is NOT separately enabled. Even `Promise<void>`. Inline arrow callbacks whose type comes from context (e.g. `.map(x => x.id)`) are exempt by the rule's default `allowTypedFunctionExpressions: true` — `allowExpressions`/`allowHigherOrderFunctions` are deliberately left off.
- **No single-letter variable names** for local variables, `for…of` loop bindings, or catch/promise-catch parameters. Names must be explicit yet short. `const manhole = …` not `const m = …`; `.catch((error) => …)` not `.catch((e) => …)`; `for (const manhole of rows)` not `for (const m of rows)`. The classic loop counter `i`/`j`/`k` is the **only** acceptable single letter, and only inside indexed `for` loops.
- **No inline `if`.** Always brace and put the body on its own line.
- **Blank line before `if`, `for`, `while`, `return`, `throw`** unless the statement is the first one in its enclosing block.
- **No nested function declarations** (a function inside another function body — extract it).
- **No double negation** (`!!x`) and **no double-bang patterns**. Use explicit `x != null` or `Boolean(x)`.
- **Constructor parameter properties are `readonly` by default.** Any DI/constructor-injected dependency (`private db: FooDb`) becomes `private readonly db: FooDb` unless the field is genuinely reassigned after construction (rare — and if so, prefer restructuring over a mutable injected dependency). Applies to every accessibility modifier (`private`, `public`, `protected`) and to decorated params (`@Inject(TOKEN) private readonly x: X`). A plain constructor parameter with no accessibility modifier at all (used only inside the constructor body, e.g. to build a `super()` call, never stored as `this.x`) is not a parameter property and doesn't take `readonly`.
- Delete dead code rather than commenting it out.
- **Numeric separators on large literals.** Use `_` in any numeric literal of 5+ digits: `2_592_000`, `60_000`, `65_535`. Four digits or fewer stay plain (`3000`).
- **Branded types for domain primitives — on by default in every TS backend, don't wait to be asked.** Brand types live in type-only `.d.ts` files (one per category, `unique symbol` brand, no barrel — full pattern in the `branded-types` skill); validating constructors are small runtime `.ts` files inside `src/` (no ORM import there). Brand: entity ids (`AthleteId`, `AuctionId`, …), `NormalizedEmail` (constructor trims + lowercases), money as `Cents` when a payment provider is involved, otherwise the project's whole unit, one brand per role (non-negative integer; small `money.ts` with `cents()`/`addCents`/`percentOfCents`), third-party ids that share a shape (e.g. `StripePaymentIntentId` vs `StripeCustomerId`), and bounded/validated values (`TrustScore` 0–100, `IanaTimezone` checked via `Intl`). Do NOT brand counts, free-text fields (bib numbers, names), or URLs. Cast to a brand only at an I/O boundary, never in services: `*.db.ts` for ORM reads, and the adapter file that wraps a third-party API/SDK (the only file importing that client) for external calls. Anything an external source returns (Stripe ids, amounts, emails, timezones, …) is branded there through the validating constructors, not a blind `as`, so unvalidated third-party data never enters the service layer as a plain `string`/`number`. No mapping layer over ORM records just to brand fields. Service/db signatures with two or more same-typed params must use the branded types so swapped args fail to compile.

- **Error messages are simple snake_case codes, readable detail goes to a log.** Throw `new NotFoundException('athlete_not_found')`, not a sentence; log the human-readable message (with ids) via the class's `Logger` (`private readonly logger = new Logger(FooService.name)`, `warn` for not-found) at the throw site. Pure helpers (e.g. branded-type constructors in `src/common`) throw only the snake_case code and never log — logging stays in the caller.
- **No barrel files (`index.ts` re-exports).** Import from the specific file, everywhere, including `src/common`. Nest convention prefers direct imports.

## Comments — default to none

**Do not write a comment unless the code genuinely cannot carry the information itself.** Readable code with honest names is the documentation; a comment that restates it is noise that rots the moment the code moves on without it.

Do not comment:
- What the code plainly says. `// Set the status to GIFTED` above `status = 'GIFTED'` earns nothing.
- Every new constant, type field, enum member, or config key by default.
- The absence of something (`// No export here because...`), unless its absence is load-bearing and surprising.
- A narrative of how the code came to look this way. That belongs in the commit message and the spec, not the file.

Do comment, briefly:
- A **why** that is genuinely non-obvious and would otherwise get "fixed" by the next reader — a deliberate-looking-wrong choice, a workaround for an external constraint, an ordering the database or the framework forces.
- A constraint enforced somewhere the reader can't see from here (a hand-written migration, another service, a cross-layer invariant).

When a comment does earn its place, **make it as short as it can be while still carrying the why** — one or two lines, not a paragraph. If it's growing past that, the reason is usually that the code is unclear: fix the code instead.

## Unit test structure (Jest)

- **Nest a `describe` block for every conditional branch under test.** Anything describable as "when X" / "if X" gets its own `describe`, not a long `it()` name that encodes the condition inline. Keeps the condition in one place and lets sibling `it`s read as a plain list of expected behaviors for that condition.
- `describe` titles state the condition (`when ...` preferred, `if ...` also fine). `it` titles are short and state only the expected outcome — don't repeat the condition, it's already the parent's title.
- Shared setup for a condition (mocks, fake timers, fixtures) goes in that `describe`'s own `beforeEach`, not duplicated across sibling `it`s.

Bad:
```ts
describe('updateSale kickoff guard', () => {
  it('rejects marking a sale SOLD after the match kickoff', async () => { ... });
  it('allows marking a sale SOLD when the match is in the future', async () => { ... });
});
```

Good:
```ts
describe('updateSale kickoff guard', () => {
  describe('when the match kickoff has passed', () => {
    it('rejects marking the sale SOLD', async () => { ... });
  });

  describe('when the match is in the future', () => {
    it('allows marking the sale SOLD', async () => { ... });
  });
});
```

## Project conventions

- Default Node runtime: latest LTS (currently Node 24, since Node 20 EoL'd April 2026).
- Prefer npm workspaces for monorepos with shared TS types in a `shared/` package.
- For SvelteKit + Tailwind + Leaflet: import Leaflet CSS via JS (`import 'leaflet/dist/leaflet.css'`) in a `.ts`/`.svelte` file, **not** via `@import` in CSS. The PostCSS `@import` path is unreliable in some build environments (CF Pages, etc.).

## Dependency version pinning

**Every dep in every `package.json` must be pinned to an exact version — no `^`, no `~`, no `>=`, no `*` (except for `workspace:*` or `"*"` references to sibling workspace packages, which are intentional).** Surprise minor/patch updates are how working builds turn into broken builds overnight.

When adding a dep, install it then immediately rewrite the package.json entry to drop the caret/tilde npm adds by default. When pinning an existing project, read the resolved version from `package-lock.json` and write it back into the package.json so it matches what's actually installed.

Bad:
```json
"dependencies": {
  "@nestjs/common": "^10.4.0",
  "vite": "~5.4.0"
}
```

Good:
```json
"dependencies": {
  "@nestjs/common": "10.4.22",
  "vite": "5.4.21",
  "@dexkepo/shared": "*"
}
```

## Git workflow — review before commit

Before committing implementation work (not trivial one-liners), stage the changes and stop — don't commit straight away. Tell the user it's staged and ready, and that they can run `/crit` themselves to review the diff first (I can't trigger `/crit` — it's `disable-model-invocation`, reserved for the user). Wait for their go-ahead or their crit comments before committing. Applies to every project, not just one.

## Git workflow — branch naming

Branch for a Linear ticket is the lowercase key plus the number zero-padded to two digits: `hyr-02` for HYR-2. Not Conductor's auto-name (`handle-hyr-02`), not Linear's suggested `hyr-2`. Check the branch name and rename it **before** pushing or opening a PR (this is the explicit instruction that overrides Conductor's "don't rename the branch" note). Renaming an already-pushed branch via the GitHub rename API closes its open PR, so never rename after the PR exists. Applies to every project.

## Linear — ticket status transitions

When starting work on a Linear ticket, move it to **In Progress** first. Move it to **In Review** only once the work is staged and ready for `/crit`. Never jump Backlog → In Review directly. Check the current state before changing it so a ticket never moves backwards. Applies to every project.

## Git workflow — conventional commits

Every commit message and every PR title follows Conventional Commits: `type(optional-scope): lowercase imperative summary`, with type one of `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `build`, `ci`, `perf`, `style`, `revert`. No capitalised or past-tense subjects ("Add…", "Switch…"). Applies to commits made by subagents too — brief them on it when dispatching. Applies to every project.

## Superpowers plan/spec output path — repo docs, not docs/superpowers

The `superpowers` plugin's `writing-plans` and `brainstorming` skills default to writing specs/plans under `docs/superpowers/specs/` and `docs/superpowers/plans/`. Override this: write specs to `docs/specs/` and plans to `docs/plans/` in the target repo instead (create the dirs if missing). Same filename convention (`YYYY-MM-DD-slug.md`, `-design.md` suffix for specs), just without the `superpowers/` nesting.

**Why:** these are project deliverables, not artifacts of the tool that generated them — nesting them under a folder named after the skill is backwards, and the repo shouldn't carry an implementation detail of which Claude Code plugin wrote a doc in its path. Applies to every project, not just one.

## Code intelligence — prefer codebase-memory-mcp, fall back to graphify

Projects can have two indexers. They do different jobs — pick the right one to avoid burning tokens.

**Default for structural code questions → codebase-memory-mcp (free, no LLM).**
Use its MCP tools for: "who calls X", "where is Y defined", "trace call chain", "find route handler", "what does this import", impact analysis, refactor candidates, dead code, architecture overview.
- `search_graph` to find symbols by name/label/qualified-name
- `trace_path` for call chains / data flow / cross-service
- `get_code_snippet` for exact source by qualified name
- `query_graph` for Cypher-style patterns
- `get_architecture` for project structure
- `search_code` for graph-augmented text search
- If the project is not indexed yet, run `index_repository` first.

**Fall back to serena when cbm can't answer.** Serena is registered globally (`~/.claude.json`, `--project-from-cwd`) — no per-project setup needed, always available. Unlike cbm's static graph snapshot, serena reads live via LSP, so use it when:
- cbm returns empty/no match, or the project isn't indexed and reindexing isn't worth it for a one-off question.
- cbm's graph is stale (recent edits it hasn't seen yet).
- The task needs symbol-precise operations cbm can't do at all: `find_symbol`, `find_referencing_symbols`, `rename_symbol`, `replace_symbol_body`, `insert_after_symbol`/`insert_before_symbol`.

**Use graphify only when codebase-memory-mcp cannot answer.** Graphify uses LLM extraction and costs tokens per run/query — do not invoke for routine code lookups.
Reach for it when:
- The question is conceptual / cross-domain NL ("how does X relate to Y across docs+code", "explain this subsystem in plain language").
- You need community detection, the wiki (`graphify-out/wiki/index.md`), or `GRAPH_REPORT.md` for broad architecture review.
- The corpus includes non-code (PDFs, transcripts, images) that codebase-memory-mcp does not index.

Do **not** run `graphify query` as a default for code questions anymore. Do **not** auto-run `graphify update .` after edits — only refresh when the next task actually needs graphify. The existing `graphify-out/` snapshot is fine to read passively.

# graphify
- **graphify** (`~/.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, invoke the Skill tool with `skill: "graphify"` before doing anything else.
