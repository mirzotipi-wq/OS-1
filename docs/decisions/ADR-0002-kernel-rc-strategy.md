# ADR-0002: Handling the `7.4.0-rc3` Kernel Release Candidate

- **Status:** Accepted
- **Date:** 2026-11-18
- **Decision Makers:** OS-1 Architecture Lead

## Context

Audit of `Makefile` at `666539eecdf4db623f5e3c3e55cf9f2dfad24aa4` shows `VERSION=7`, `PATCHLEVEL=4`, `SUBLEVEL=0`, `EXTRAVERSION=-rc3` (with post-rc3 merge commits toward `7.4-rc4`). Linux release candidates (`-rc*`) are development snapshots and are not automatically suitable for an end-user stable desktop release.

## Decision

1. **Explicit OS-1 Kernel Bring-Up:** Build, boot, and test the in-repo `7.4.0-rc3` kernel explicitly with `CONFIG_LOCALVERSION="-os1"` and `CONFIG_LOCALVERSION_AUTO=y` so every booted kernel exposes its exact Git commit SHA in `uname -a`.
2. **No Silent Substitution:** Never silently substitute a stock Debian kernel in place of the OS-1 kernel or mark any OS-1 kernel gate as `PASS` when running another kernel.
3. **Optional Isolated Bring-Up Fallback:** During future userspace/graphics bring-up (Phases 2–5), a separately labeled Debian stable kernel profile may be used strictly for differential debugging (isolating kernel vs. userspace bugs), always logged explicitly as a non-OS-1 diagnostic run.
4. **Path to Stable Release:** Before Phase 15 (Release Qualification), fast-forward or rebase the OS-1 kernel branch onto a tagged stable release (`7.4.x` final or an active LTS series) with a documented patch manifest.

## Consequences

- Preserves 100% honesty and provenance for the OS-1 kernel from Phase 1 onward.
- Prevents `-rc3` regressions from blocking diagnosis of userspace/Wayland issues while keeping the OS-1 kernel gate strictly enforced.
