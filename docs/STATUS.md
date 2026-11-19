# OS-1 Live Project Status & Acceptance Scorecard

- **Last Updated (UTC):** 2026-11-19
- **Branch:** `master`
- **Last Fully CI-Tested Revision:** `6a8fdcfe2c138eef708ba46f56c1b2136b5d9e8b` (commit `391fe7dc64` used `[skip ci]`)
- **Upstream Kernel Baseline:** Linux `7.4.0-rc3` (`7.4.0-rc3-os1`) — release-candidate kernel; stable/LTS policy pending Phase 22
- **Current Release Status:** **In Progress — OS-1 1.0-rc2 Qualification (Phase 16: CI Truthfulness & Test-Harness Repair)**
- **Baseline Audit:** See [`docs/audits/PHASE16_BASELINE_AUDIT.md`](audits/PHASE16_BASELINE_AUDIT.md)

## Current Workflow Status (Baseline `6a8fdcfe2c` prior to Phase 16 push)

| Workflow | Latest Run ID | Status | Truthful Assessment |
|---|---|---|---|
| `phase1-kernel-boot.yml` | `44493992761` | `GREEN` | Verified QEMU serial boot of `7.4.0-rc3-os1`. |
| `phase2-userspace.yml` | `44493992931` | `GREEN` | Verified Debian 12 userspace, NetworkManager, APT, 2-boot persistence. |
| `phase3-live-iso.yml` | `44493992785` | `GREEN` | Verified UEFI Live ISO + Recovery mode in OVMF. |
| `phase4-installer.yml` | `44493992839` | `GREEN` | Verified serial-only clean-disk install & 2-reboot persistence; lacks special-char password, reserved-username, and installed GUI tests (Phases 18 & 21). |
| `phase5-wayland-desktop.yml` | `44493993181` | **`RED`** | Failed at `CONTROLS_A11Y_RC=` (30s timeout after `kwin_wayland` segfault + unbounded `qdbus` call without exported DBus env). Repaired with diagnostics in Phase 16; awaiting CI run. |
| `phase14-15-release-qualification.yml` | `44493992921` | `GREEN` *(false-positive on UFW)* | Passed despite `[FAILED] Failed to start ufw.service` in `qemu-phase4-installed-boot1.log:691` because test only checked static config text. Also has root-level `os1-branding` paths (Phase 19), unsigned APT repo (Phase 20), and `os1:bzImage_sha256: unknown` in SBOM (Phase 23). |

## Phases 16–24 Mission Tracker

- [ ] **Phase 16 — CI Truthfulness & Test-Harness Repair:** Baseline audit written, `ci-integrity-test.py` added to `audit`, `os1-accessibility` DBus timeout bounded, `qemu-wayland-test.py` split into bounded steps with full failure diagnostics, `STATUS.md`/`TEST_MATRIX.md`/`KNOWN_GAPS.md` reconciled. *(Awaiting CI verification)*
- [ ] **Phase 17 — Firewall & Network-Security Correction:** Pending.
- [ ] **Phase 18 — Installer Safety, Credential Handling & System Identity:** Pending.
- [ ] **Phase 19 — Package Correctness & Package-Owned System Assembly:** Pending.
- [ ] **Phase 20 — Signed Updates, Versioned Kernel Packages & Rollback:** Pending.
- [ ] **Phase 21 — Installed Graphical Session, First-Boot State & Desktop Journeys:** Pending.
- [ ] **Phase 22 — Stable Kernel Baseline, Driver Coverage, Modules & Hardware Policy:** Pending.
- [ ] **Phase 23 — Reproducibility, Supply-Chain Security, SBOM & Release Engineering:** Pending.
- [ ] **Phase 24 — Full OS-1 1.0-rc2 Release Qualification:** Pending.

## Gated Items Outside Automated CI

- **Hardware-Gated:** Physical bare-metal x86-64 UEFI testing (Intel/AMD GPU acceleration, Wi-Fi, Bluetooth, audio, webcam, touchpad, external display, suspend/resume, battery, bare-metal update/rollback).
- **Human / Legal-Gated:** Human accessibility usability review, human legal/trade-dress review, and production release GPG key custody.
