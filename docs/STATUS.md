# OS-1 Live Project Status & Acceptance Scorecard

- **Last Updated (UTC):** 2026-11-19
- **Active Branch:** `os1/phase2-debian-userspace` (PR #2)
- **Upstream Kernel Baseline:** `666539eecdf4db623f5e3c3e55cf9f2dfad24aa4` (`Linux 7.4.0-rc3`, "Baby Opossum Posse")
- **Current Phase:** Phase 0 **PASS**, Phase 1 **PASS**, Phase 2 **PASS** → Advancing to Phase 3 (Bootable UEFI Live ISO & Recovery)

## Verified Milestones

- [x] **Phase 0 Forensic Audit & Governance:** Repo audited; durable docs (`docs/*`), ADRs, and `distro/` scaffolding committed and verified (`T0-AUDIT` PASS).
- [x] **Phase 1 Real OS-1 Kernel Build & QEMU Serial Boot Proof:**
  - Verified CI Run: `https://github.com/mirzotipi-wq/OS-1/actions/runs/44461985823` (15m25s, exit 0)
  - Kernel Release: `7.4.0-rc3-os1-g9e716dcb5530` (`bzImage` SHA-256 `f844850f3d2185039af202879f906a7a7cd7fce8fda1ff93c66347e54c744244`)
- [x] **Phase 2 Real Linux Userspace & Persistent Storage:**
  - Verified CI Run: `https://github.com/mirzotipi-wq/OS-1/actions/runs/44466206157` (3m57s, exit 0)
  - Base Userspace: Pinned Debian 12 (`bookworm`, 238 packages, `systemd`, `NetworkManager`, `PipeWire`, `sudo`, persistent `journald`, non-root user `os1`)
  - Kernel Booted: `7.4.0-rc3-os1-ga695703b0fb8`
  - Persistent Disk Image: `os1-rootfs.ext4.img` (2048 MiB, SHA-256 `e8d990582b3ad8786f40e0e926bdbcb567fb2914a8b80e7f3ec9adc294e144c5`)
  - 2-Boot QEMU Proof: Boot 1 reached `os1 login:`, authenticated non-root `os1`, brought up IPv4 via NetworkManager, ran `apt-get update && apt-get install -y tree`, wrote `/home/os1/os1-phase2-persistence.txt`, powered off cleanly. Boot 2 verified both file content (`OS1-PHASE2-PERSISTENCE-VERIFIED-2026`) and `tree v2.1.0` survived reboot, zero panics/Oops.
- [ ] **Phase 3 Bootable UEFI Live ISO & Recovery:** Next active milestone.

## Acceptance Scorecard

| Req ID | System Area | Reference Behavior | Implementation | Test Command | Evidence | Status | Severity | Next Action |
|---|---|---|---|---|---|---|---|---|
| `R0-01` | Repo Audit & Governance | Project resumable from durable docs | `docs/*`, `distro/.gitignore` | `./distro/tools/os1.sh audit` | CI `44466206157` (exit 0) | `PASS` | High | Maintain every phase |
| `R1-01..04` | OS-1 Kernel & Serial Boot | Compile `7.4.0-rc3-os1`, boot in QEMU to PID 1 | `distro/kernel/*`, `distro/tests/qemu-serial-boot.sh` | `./distro/tools/os1.sh kernel && initramfs && boot-test` | CI `44461985823` (3.18s boot) | `PASS` | Critical | — |
| `R2-01` | Debian Userspace & Persistence | Debian 12 + systemd + non-root login + network + APT + reboot persistence | `distro/build/build-rootfs.sh`, `distro/tests/qemu-userspace-test.py` | `sudo ./distro/tools/os1.sh rootfs && ./distro/tools/os1.sh userspace-test` | CI `44466206157` (2-boot PASS) | `PASS` | Critical | — |
| `R3-01` | UEFI Live ISO & Recovery | One-command x86-64 UEFI live ISO booting cleanly in QEMU/OVMF + recovery mode | *In progress (Phase 3)* | *Planned* | — | `NOT TESTED` | Critical | Implement `build-iso.sh` & `qemu-iso-uefi-test.py` |
| `R4-01` | Real Installation | Install from ISO to clean VM disk, detach ISO, reboot, update | *Not yet implemented* | *Planned* | — | `NOT TESTED` | Critical | Phase 4 |
| `R5-01` | Wayland Desktop Session | KDE Plasma/KWin Wayland + XWayland + PipeWire + NetworkManager | *Not yet implemented* | *Planned* | — | `NOT TESTED` | Critical | Phase 5 |
| `R6-12` | macOS Sequoia 15.x Visual & Interaction Fidelity | Original OS-1 identity, Menu Bar, Dock, Finder-class files, Search, Multitasking, Shortcuts | *Not yet implemented* | *Planned* | — | `NOT TESTED` | High | Phases 6–12 |
| `R13-15` | Hardware, Security, Release Qualification | Intel/AMD PCs, signed APT repo, SBOM, upgrade/rollback, release gates | *Not yet implemented* | *Planned* | — | `NOT TESTED` | High | Phases 13–15 |
