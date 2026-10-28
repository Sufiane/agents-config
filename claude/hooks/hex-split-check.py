#!/usr/bin/env python3
"""PostToolUse hook: hexagonal-split guard for backend services.

Runs after Edit/Write/MultiEdit. If the touched file is `*.service.ts`,
scan for ORM/data-access imports. Services are business logic only; all
data access must live in the sibling `*.db.ts`.

Never blocks. Exits 0 always. Emits a JSON `systemMessage` when it finds
violations.
"""

import json
import os
import re
import sys


BACKEND_SVC_RE = re.compile(r"\.service\.ts$", re.IGNORECASE)

# Any of these imports in a *.service.ts file is a hex-split violation.
ORM_IMPORT_RE = re.compile(
    r"""(?:from|import)\s*['"]("""
    r"prisma"
    r"|@prisma/[\w\-/]+"
    r"|typeorm"
    r"|@nestjs/typeorm"
    r"|mongoose"
    r"|@nestjs/mongoose"
    r"|knex"
    r"|drizzle-orm[\w\-/]*"
    r"|kysely"
    r"|sequelize"
    r"|@mikro-orm/[\w\-/]+"
    r""")['"]"""
)


def file_path_from_input(payload: dict) -> str | None:
    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response") or {}

    candidate = (
        tool_response.get("filePath")
        or tool_input.get("file_path")
        or tool_input.get("filePath")
    )

    if isinstance(candidate, str) and candidate:
        return candidate

    return None


def scan(content: str) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []

    for idx, line in enumerate(content.split("\n"), start=1):
        m = ORM_IMPORT_RE.search(line)

        if m:
            violations.append((idx, m.group(1)))

    return violations


def format_violations(path: str, violations: list[tuple[int, str]]) -> str:
    rel = os.path.relpath(path) if os.path.isabs(path) else path
    db_sibling = os.path.basename(path).replace(".service.ts", ".db.ts")
    lines = [f"⚠️  Hex-split violation in {rel}:"]

    for line_no, pkg in violations:
        lines.append(
            f"  {rel}:{line_no} — imports `{pkg}`. "
            f"Services must NOT import an ORM. Move data access to `{db_sibling}`."
        )

    lines.append("")
    lines.append(
        "Rule: *.service.ts is business logic only. All data access lives in *.db.ts. "
        "The service depends on the db (`constructor(private db: FooDb) {}`)."
    )

    return "\n".join(lines)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    path = file_path_from_input(payload)

    if not path:
        sys.exit(0)

    if not BACKEND_SVC_RE.search(path):
        sys.exit(0)

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError, UnicodeDecodeError):
        sys.exit(0)

    violations = scan(content)

    if not violations:
        sys.exit(0)

    print(json.dumps({"systemMessage": format_violations(path, violations)}))
    sys.exit(0)


if __name__ == "__main__":
    main()
