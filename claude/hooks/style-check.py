#!/usr/bin/env python3
"""Global PostToolUse hook: TypeScript / JavaScript code-style linter.

Runs after Edit / Write / MultiEdit. Reads the file from disk (post-edit) and
flags style violations the user has standardized on:

  1. Inline `if (...) <stmt>;` — body must be braced and on a new line.
  2. Inline `for (...) <stmt>;` — body must be braced and on a new line.
  3. `!!x` boolean cast — use `Boolean(x)` instead.
  4. Nested function declarations (≥4-space indented `function foo`) — lift
     to module scope. Browser-side helpers inside `page.evaluate` callbacks
     are exempt because they have to live where they run.
  5. Missing blank line before `if`, `return`, or `throw` — except as the
     first statement in a block (right after `{`).

Never blocks. Exits 0 always. When violations found, prints a JSON object
with `systemMessage` listing each violation with file:line:col so the user
sees them inline in the transcript.
"""

import json
import os
import re
import sys


TS_JS_EXT_RE = re.compile(r"\.(ts|tsx|js|jsx|mjs|cjs)$", re.IGNORECASE)

# Strings + line/block comments — used to skip lines that are inside them so
# the linter doesn't false-positive on comment text or string literals
# containing keywords. This is a heuristic, not a full parser; it handles the
# common cases well enough for source files.
LINE_COMMENT_RE = re.compile(r"//.*$")
BLOCK_COMMENT_OPEN = "/*"
BLOCK_COMMENT_CLOSE = "*/"


def file_path_from_input(payload: dict) -> str | None:
    """Extract the touched file path from a PostToolUse payload."""
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


def read_file(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (IOError, OSError, UnicodeDecodeError):
        return None


def strip_strings_and_comments(line: str, in_block_comment: bool) -> tuple[str, bool]:
    """Remove string literal contents and comments from a line.

    Returns the cleaned line and the new in_block_comment state. Used so the
    linter regexes don't match keywords inside strings or comments.
    """
    out = []
    i = 0
    in_block = in_block_comment
    in_string = None  # one of None, '"', "'", "`"

    while i < len(line):
        if in_block:
            close_idx = line.find(BLOCK_COMMENT_CLOSE, i)

            if close_idx == -1:
                return ("".join(out), True)

            i = close_idx + len(BLOCK_COMMENT_CLOSE)
            in_block = False

            continue

        if in_string is not None:
            ch = line[i]

            if ch == "\\" and i + 1 < len(line):
                out.append("X")
                out.append("X")
                i += 2

                continue

            if ch == in_string:
                out.append(ch)
                in_string = None
                i += 1

                continue

            out.append("X")
            i += 1

            continue

        # Not in string or block comment.
        # Check for line comment first.
        if line.startswith("//", i):
            return ("".join(out), False)

        if line.startswith(BLOCK_COMMENT_OPEN, i):
            close_idx = line.find(BLOCK_COMMENT_CLOSE, i + len(BLOCK_COMMENT_OPEN))

            if close_idx == -1:
                return ("".join(out), True)

            i = close_idx + len(BLOCK_COMMENT_CLOSE)

            continue

        ch = line[i]

        if ch in ("'", '"', "`"):
            out.append(ch)
            in_string = ch
            i += 1

            continue

        out.append(ch)
        i += 1

    return ("".join(out), False)


# ────────────────────────────────────────────────────────────────────────────
# Individual checks
# ────────────────────────────────────────────────────────────────────────────

DOUBLE_BANG_RE = re.compile(r"(?<![!=<>])!!(?!=)")
NESTED_FUNCTION_RE = re.compile(r"^[ \t]+(?:async\s+)?function\s+[a-zA-Z_]")
UNESCAPED_BACKTICK_RE = re.compile(r"(?<!\\)`")
# Word-boundary keyword positions; balanced-paren matching is done in code.
KEYWORD_RE = {
    "if": re.compile(r"\bif\s*\("),
    "for": re.compile(r"\bfor\s*\("),
}

# Single-letter variable name checks. The classic loop counter `i`/`j`/`k` is
# only acceptable inside an indexed `for` — those are `for (let i = 0; …)`
# and never fire any of these patterns (which target decls-as-statements,
# `.catch(x)`, and `for (… of|in …)` respectively).
SINGLE_LETTER_DECL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([a-zA-Z])\b\s*[=:]"
)
SINGLE_LETTER_CATCH_RE = re.compile(
    r"\.catch\s*\(\s*(?:async\s+)?\(?\s*([a-zA-Z])\s*(?:[),]|\)\s*=>)"
)
SINGLE_LETTER_FOROF_RE = re.compile(
    r"\bfor\s*\(\s*(?:const|let|var)\s+([a-zA-Z])\s+(?:of|in)\b"
)

# Backend files where every function/method must declare an explicit return
# type. Matched by suffix — matches the NestJS-style modules the user works
# with. Non-backend files skip this check.
BACKEND_SUFFIX_RE = re.compile(
    r"\.(service|controller|db|module|guard|interceptor|pipe|filter|middleware|resolver|repository|strategy|gateway)\.ts$",
    re.IGNORECASE,
)

# Top-level `function foo(...) {` with no `):` return-type annotation between
# the closing paren and the opening brace. Only fires on same-line decls —
# multi-line signatures are skipped to keep noise down.
MISSING_RETURN_TYPE_RE = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*\{"
)


def find_inline_keyword(line: str, keyword: str) -> int | None:
    """Return 0-indexed column of an inline `<keyword>(...) <body>` whose body
    is not a `{`. Handles nested parens. Returns None if no inline match.
    """
    pat = KEYWORD_RE[keyword]

    for m in pat.finditer(line):
        kw_start = m.start()
        paren_start = line.find("(", m.end() - 1)

        if paren_start == -1:
            continue

        depth = 0
        j = paren_start

        while j < len(line):
            ch = line[j]

            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1

                if depth == 0:
                    break

            j += 1

        if depth != 0:
            # Unbalanced — multi-line condition; not an inline form on this line.
            continue

        rest = line[j + 1 :].lstrip()

        if rest == "" or rest.startswith("{"):
            continue

        return kw_start

    return None


def check_blank_line_before_flow(prev_line: str | None, raw: str) -> str | None:
    """Require blank line before `if`, `return`, `throw` unless first in block.

    `prev_line` is the previous *raw* line (None for the first line of the
    file). The current line is `raw`.
    """
    stripped = raw.lstrip()
    is_flow = (
        stripped.startswith("if ")
        or stripped.startswith("if(")
        or stripped == "return"
        or stripped.startswith("return ")
        or stripped.startswith("return;")
        or stripped.startswith("throw ")
    )

    if not is_flow:
        return None

    if prev_line is None:
        return None

    prev_stripped = prev_line.strip()

    # First statement in a block is exempt — previous line ends with `{` or is
    # the start of a function/case body / arrow body.
    if prev_stripped.endswith("{") or prev_stripped.endswith("=>") or prev_stripped.endswith(":"):
        return None

    # Comment immediately before the statement — assume the comment annotates
    # this statement (very common pattern). Exempt.
    if prev_stripped.startswith("//") or prev_stripped.startswith("/*") or prev_stripped.startswith("*"):
        return None

    if prev_stripped == "":
        return None

    return f"missing blank line before `{stripped.split()[0]}`"


# ────────────────────────────────────────────────────────────────────────────
# Driver
# ────────────────────────────────────────────────────────────────────────────


def lint(content: str, is_backend: bool = False) -> list[tuple[int, int, str]]:
    """Return list of (line_no, col_no, message) violations (1-indexed).

    `is_backend` gates rules that only apply to backend files (currently the
    explicit-return-type rule).
    """
    violations: list[tuple[int, int, str]] = []
    lines = content.split("\n")
    in_block = False
    in_template = False  # inside a multi-line backtick string
    prev_raw: str | None = None

    for idx, raw in enumerate(lines):
        # Toggle multi-line template string state by counting unescaped
        # backticks on this line.
        backtick_count = len(UNESCAPED_BACKTICK_RE.findall(raw))
        line_starts_in_template = in_template

        if backtick_count % 2 == 1:
            in_template = not in_template

        # Skip linting any line that started inside a template string OR
        # contains a backtick at all on a single-toggle line — too noisy to
        # try to lint half-string lines.
        if line_starts_in_template:
            prev_raw = raw

            continue

        cleaned, in_block = strip_strings_and_comments(raw, in_block)
        triggered: list[tuple[int, str]] = []

        col_if = find_inline_keyword(cleaned, "if")

        if col_if is not None:
            triggered.append((col_if + 1, "inline-if (use braces and put body on a new line)"))

        col_for = find_inline_keyword(cleaned, "for")

        if col_for is not None:
            triggered.append((col_for + 1, "inline-for (use braces and put body on a new line)"))

        m_bang = DOUBLE_BANG_RE.search(cleaned)

        if m_bang:
            triggered.append((m_bang.start() + 1, "double-bang `!!` (use `Boolean(x)` instead)"))

        m_fn = NESTED_FUNCTION_RE.match(raw)

        if m_fn:
            triggered.append((m_fn.start() + 1, "nested function declaration (lift to module scope; browser-side helpers inside page.evaluate are exempt)"))

        m_decl = SINGLE_LETTER_DECL_RE.match(cleaned)

        if m_decl:
            triggered.append((m_decl.start(1) + 1, f"single-letter variable name `{m_decl.group(1)}` (use an explicit short name)"))

        m_catch = SINGLE_LETTER_CATCH_RE.search(cleaned)

        if m_catch:
            triggered.append((m_catch.start(1) + 1, f"single-letter catch parameter `{m_catch.group(1)}` (use `error` or similar)"))

        m_forof = SINGLE_LETTER_FOROF_RE.search(cleaned)

        if m_forof:
            triggered.append((m_forof.start(1) + 1, f"single-letter for-of/in binding `{m_forof.group(1)}` (name the item explicitly)"))

        if is_backend:
            m_rt = MISSING_RETURN_TYPE_RE.match(cleaned)

            if m_rt and m_rt.group(1) != "constructor":
                triggered.append((m_rt.start() + 1, f"function `{m_rt.group(1)}` is missing an explicit return type annotation"))

        for col, msg in triggered:
            violations.append((idx + 1, col, msg))

        flow_msg = check_blank_line_before_flow(prev_raw, raw)

        if flow_msg:
            violations.append((idx + 1, len(raw) - len(raw.lstrip()) + 1, flow_msg))

        prev_raw = raw

    return violations


def format_violations(path: str, violations: list[tuple[int, int, str]]) -> str:
    rel = os.path.relpath(path) if os.path.isabs(path) else path
    lines = [f"⚠️  Style violations in {rel}:"]

    for line_no, col, msg in violations:
        lines.append(f"  {rel}:{line_no}:{col} — {msg}")

    lines.append("")
    lines.append(
        "Style rules: no inline if/for, use Boolean() not !!, lift nested functions to module scope, "
        "blank line before if/return/throw, no single-letter var names (i/j/k only in indexed for loops), "
        "explicit return types on backend functions."
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

    if not TS_JS_EXT_RE.search(path):
        sys.exit(0)

    content = read_file(path)

    if content is None:
        sys.exit(0)

    is_backend = bool(BACKEND_SUFFIX_RE.search(path))
    violations = lint(content, is_backend=is_backend)

    if not violations:
        sys.exit(0)

    output = {"systemMessage": format_violations(path, violations)}
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
