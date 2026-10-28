#!/usr/bin/env python3
"""PostToolUse hook: package.json dependency pin-check.

Runs after Edit/Write/MultiEdit. If the touched file is a package.json,
scan every dependencies/devDependencies/peerDependencies/optionalDependencies
entry and flag any version spec that isn't pinned exactly.

Rule (from global CLAUDE.md): every dep must be pinned to an exact version.
No `^`, `~`, `>=`, `<=`, `>`, `<`, `||`, ranges. The only allowed non-exact
forms are `workspace:*` and the bare `"*"` for sibling workspace packages.

Never blocks. Exits 0 always. Emits a JSON `systemMessage` when it finds
violations.
"""

import json
import os
import re
import sys


UNPINNED_RE = re.compile(r"^[\^~><=]|\|\||\s-\s")
DEP_SECTIONS = (
    "dependencies",
    "devDependencies",
    "peerDependencies",
    "optionalDependencies",
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


def scan(data: dict) -> list[tuple[str, str, str]]:
    violations: list[tuple[str, str, str]] = []

    for section in DEP_SECTIONS:
        deps = data.get(section) or {}

        if not isinstance(deps, dict):
            continue

        for name, spec in deps.items():
            if not isinstance(spec, str):
                continue

            if spec.startswith("workspace:"):
                continue

            if spec == "*":
                continue

            if UNPINNED_RE.search(spec):
                violations.append((section, name, spec))

    return violations


def format_violations(path: str, violations: list[tuple[str, str, str]]) -> str:
    rel = os.path.relpath(path) if os.path.isabs(path) else path
    lines = [f"⚠️  Unpinned deps in {rel}:"]

    for section, name, spec in violations:
        lines.append(f"  {section}.{name}: {spec}")

    lines.append("")
    lines.append(
        "Rule: pin exact versions from package-lock.json. Drop `^`/`~`/ranges. "
        "Only `workspace:*` and bare `\"*\"` are allowed."
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

    if os.path.basename(path) != "package.json":
        sys.exit(0)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (IOError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        sys.exit(0)

    violations = scan(data)

    if not violations:
        sys.exit(0)

    print(json.dumps({"systemMessage": format_violations(path, violations)}))
    sys.exit(0)


if __name__ == "__main__":
    main()
