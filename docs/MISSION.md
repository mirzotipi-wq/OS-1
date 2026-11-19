# OS-1 Mission Statement

**Repository:** `https://github.com/mirzotipi-wq/OS-1.git`  
**Baseline Kernel Tree Audit Revision:** `666539eecdf4db623f5e3c3e55cf9f2dfad24aa4` (`7.4.0-rc3`, "Baby Opossum Posse", post-rc3 merge state)

## Core Objective

Transform this repository from an upstream Linux kernel source tree into the foundation of **OS-1**: a real, bootable, installable, maintainable, secure, daily-usable x86-64 GNU/Linux desktop distribution built around the OS-1 kernel, whose appearance, animations, interaction patterns, system applications, and daily workflow reproduce a documented modern macOS reference as closely as technically and legally possible.

## Nonnegotiable Engineering Principles

1. **Real OS First:** The deliverable is a reproducible UEFI bootable Linux ISO and installable system—not a mockup, theme pack, or browser simulation.
2. **Real OS-1 Kernel:** The OS-1 kernel in this repository must be explicitly compiled, packaged, and booted with verifiable `uname -a` and source SHA provenance. Never silently substitute a distro stock kernel and mark the OS-1 kernel requirement complete.
3. **Honest Scope:** OS-1 is a Linux-based macOS-like operating environment, not macOS. It does not natively run arbitrary Apple `.app` bundles, Apple frameworks, iMessage, FaceTime, AirDrop, or Apple ID services. Supported Linux replacements and platform limitations are documented explicitly in [`KNOWN_GAPS.md`](KNOWN_GAPS.md).
4. **Strict IP & Licensing Hygiene:** Zero Apple source code, binaries, icons, fonts, sounds, wallpapers, or trademarks. All OS-1 visual assets and branding must be original or compatibly licensed and tracked in [`LEGAL_AND_LICENSES.md`](LEGAL_AND_LICENSES.md). Linux kernel GPL-2.0-only obligations and `Documentation/process/coding-assistants.rst` (no AI-generated `Signed-off-by` tags) apply at all times.
5. **Evidence-Based Progress:** Every phase requires runnable code, automated verification, and truthful pass/fail/untested reporting in [`STATUS.md`](STATUS.md). Unrun tests are never reported as passed.
6. **Clean Separation:** Upstream kernel source history remains intact; distribution build orchestration, shell, apps, branding, installer, and tests live under `distro/` and `docs/`.

## Durable State & Session Protocol

This project spans multiple working sessions. Persistent state is maintained in:
- [`docs/STATUS.md`](STATUS.md) — Current verified state and acceptance scorecard
- [`docs/SESSION_HANDOFF.md`](docs/SESSION_HANDOFF.md) — Exact restart instructions, environment facts, and next unblocker
- [`docs/ROADMAP.md`](ROADMAP.md) — Phased plan (Phases 0–15) and objective gates
- [`docs/TEST_MATRIX.md`](TEST_MATRIX.md) — Automated CI and local verification gates
- [`docs/KNOWN_GAPS.md`](KNOWN_GAPS.md) — Explicit inventory of missing components and limitations
