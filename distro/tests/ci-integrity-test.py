#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 16: CI integrity gate for OS-1 GitHub Actions workflows.

Verifies that no required workflow job or step conceals failures via:
  - `continue-on-error: true`
  - Test invocations suppressed with `|| true`, `|| :`, or `; true`
  - Unbounded jobs lacking `timeout-minutes`
"""

import glob
import os
import re
import sys


def check_workflow(path: str) -> list[str]:
    errors: list[str] = []
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    name = os.path.basename(path)
    has_timeout = False

    for lineno, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        stripped = line.strip()

        if stripped.startswith("#"):
            continue

        # Disallow continue-on-error: true in required workflows
        if re.match(r"^continue-on-error\s*:\s*true\b", stripped, re.IGNORECASE):
            errors.append(f"{name}:{lineno}: forbidden 'continue-on-error: true'")

        if re.match(r"^timeout-minutes\s*:\s*(\d+)", stripped):
            mins = int(re.match(r"^timeout-minutes\s*:\s*(\d+)", stripped).group(1))
            has_timeout = True
            if mins > 120:
                errors.append(f"{name}:{lineno}: timeout-minutes={mins} exceeds 120m upper bound")

        # Disallow suppressing OS-1 test/build/audit commands with || true / || : / ; true
        if ("./distro/tools/os1.sh" in stripped or "distro/tests/" in stripped):
            if re.search(r"(\|\|\s*(true|:)|;\s*true)\b", stripped):
                errors.append(
                    f"{name}:{lineno}: test/tool invocation suppresses failure: {stripped}"
                )

    if not has_timeout:
        errors.append(f"{name}: missing job-level 'timeout-minutes'")

    return errors


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    wf_dir = os.path.join(repo_root, ".github", "workflows")
    workflows = sorted(glob.glob(os.path.join(wf_dir, "*.yml"))) + sorted(
        glob.glob(os.path.join(wf_dir, "*.yaml"))
    )

    if not workflows:
        print("ERROR: No GitHub Actions workflows found.", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    for wf in workflows:
        errs = check_workflow(wf)
        if errs:
            all_errors.extend(errs)
        else:
            print(f"  [OK] {os.path.relpath(wf, repo_root)}")

    if all_errors:
        print("ERROR: CI integrity check failed:", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"[os1-ci-integrity] PASSED ({len(workflows)} workflows verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
