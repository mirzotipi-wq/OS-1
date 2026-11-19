# OS-1 Live Project Status & Acceptance Scorecard

- **Last Updated (UTC):** 2026-11-19
- **Active Branch:** `os1/phase0-1-foundation-kernel-boot` (PR #1)
- **Upstream Kernel Baseline:** `666539eecdf4db623f5e3c3e55cf9f2dfad24aa4` (`Linux 7.4.0-rc3`, "Baby Opossum Posse")
- **Current Phase:** Phase 0 **PASSED**, Phase 1 **PASSED** → Advancing to Phase 2 (Real Debian Userspace & Persistent Storage)

## Verified Milestones

- [x] **Phase 0 Forensic Audit & Governance:** Repo audited; durable docs (`docs/*`), ADRs, and `distro/` scaffolding committed and verified (`T0-AUDIT` PASS).
- [x] **Phase 1 Real OS-1 Kernel Build & QEMU Serial Boot Proof:**
  - Verified CI Run: `https://github.com/mirzotipi-wq/OS-1/actions/runs/44461985823` (15m25s, exit 0)
  - Kernel Release: `7.4.0-rc3-os1-g9e716dcb5530` (`git_dirty_entries: 0`)
  - Compiler: `gcc (Ubuntu 15.2.0-16ubuntu1) 15.2.0`
  - `bzImage` SHA-256: `f844850f3d2185039af202879f906a7a7cd7fce8fda1ff93c66347e54c744244`
  - `os1_x86_64.config` SHA-256: `440d1c110c2c2520faa30c9d304221e7d10f5b793c9a5351fc33e587d716bfe0`
  - QEMU Boot Proof: Booted to PID 1 BusyBox init in 3.18s (`OS-1_INIT_START`, `OS-1_UNAME`, `OS-1_TMP_WRITE_OK`, `OS-1_BOOT_PROOF_PASS`, clean `reboot: Power down`, zero panics/Oops).
- [ ] **Phase 2 Real Linux Userspace & Persistent Storage:** Next active milestone.

## Acceptance Scorecard

| Req ID | System Area | Reference Behavior | Implementation | Test Command | Evidence | Status | Severity | Next Action |
|---|---|---|---|---|---|---|---|---|
| `R0-01` | Repo Audit & Governance | Project resumable from durable docs without chat memory | `docs/*`, `distro/.gitignore` | `./distro/tools/os1.sh audit` | Local & CI run `44461985823` (exit 0) | `PASS` | High | Maintain every phase |
| `R1-01` | Kernel Config | Deterministic x86-64 QEMU/UEFI/systemd config with `-os1` identity | `distro/kernel/os1_x86_64.fragment`, `build-kernel.sh` | `./distro/tools/os1.sh kernel --config-only` | `os1_x86_64.config` (`440d1c11...`) | `PASS` | Critical | — |
| `R1-02` | Kernel Build | Compile real OS-1 `bzImage` with SHA-256 provenance | `distro/kernel/build-kernel.sh` | `./distro/tools/os1.sh kernel` | CI run `44461985823`, `bzImage` (`f844850f...`) | `PASS` | Critical | Add `--with-modules` + CI cache for Phase 2+ |
| `R1-03` | Minimal Userspace | Smallest bootable initramfs (PID 1) | `distro/build/build-initramfs.sh`, `pack-initramfs.py` | `./distro/tools/os1.sh initramfs` | Local (static C) & CI (BusyBox) pass | `PASS` | High | — |
| `R1-04` | QEMU Serial Boot | Boot OS-1 `bzImage` + initramfs to serial console, verify `uname -a` & clean poweroff | `distro/tests/qemu-serial-boot.sh` | `./distro/tools/os1.sh boot-test` | CI run `44461985823`, `qemu-serial-clean.log` (3.18s) | `PASS` | Critical | — |
| `R2-01` | Debian Userspace & Persistence | Debian stable rootfs + systemd + non-root login + network + APT + reboot persistence | *In progress (Phase 2)* | *Planned* | — | `NOT TESTED` | Critical | Implement `build-rootfs.sh` & `qemu-userspace-test.py` |
| `R3-01` | UEFI Live ISO | One-command UEFI ISO booting in clean QEMU/OVMF | *Not yet implemented* | *Planned* | — | `NOT TESTED` | Critical | Phase 3 |
| `R4-01` | Real Installation | Install from ISO to clean VM disk, detach ISO, reboot, update | *Not yet implemented* | *Planned* | — | `NOT TESTED` | Critical | Phase 4 |
| `R5-01` | Wayland Desktop Session | KDE Plasma/KWin Wayland + XWayland + PipeWire + NetworkManager | *Not yet implemented* | *Planned* | — | `NOT TESTED` | Critical | Phase 5 |
| `R6-12` | macOS Sequoia 15.x Visual & Interaction Fidelity | Original OS-1 identity, Menu Bar, Dock, Finder-class files, Search, Multitasking, Shortcuts | *Not yet implemented* | *Planned* | — | `NOT TESTED` | High | Phases 6–12 |
| `R13-15` | Hardware, Security, Release Qualification | Intel/AMD PCs, signed APT repo, SBOM, upgrade/rollback, release gates | *Not yet implemented* | *Planned* | — | `NOT TESTED` | High | Phases 13–15 |
