# OS-1 Live Project Status & Acceptance Scorecard

- **Last Updated (UTC):** 2026-11-19
- **Active Branch:** `os1/phase0-1-foundation-kernel-boot`
- **Upstream Kernel Baseline:** `666539eecdf4db623f5e3c3e55cf9f2dfad24aa4` (`Linux 7.4.0-rc3`, "Baby Opossum Posse")
- **Current Phase:** Phase 0 → Phase 1 (Foundation, x86-64 OS-1 Kernel Build, Minimal Initramfs, QEMU Serial Boot Proof)

## Verified Milestones

- [x] **Phase 0 Forensic Audit:** Confirmed upstream Linux `7.4.0-rc3` kernel tree with zero pre-existing distro/desktop/CI infrastructure; reviewed `AGENTS.md`, `COPYING`, `Documentation/process/coding-assistants.rst`, and `Documentation/process/generated-content.rst`.
- [x] **Durable Governance & Architecture Docs:** Created `docs/MISSION.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/TEST_MATRIX.md`, `docs/KNOWN_GAPS.md`, `docs/LEGAL_AND_LICENSES.md`, `docs/STATUS.md`, `docs/SESSION_HANDOFF.md`, `ADR-0001`, and `ADR-0002`.
- [x] **Distro Scaffolding & Phase 1 Scripts:** Created `distro/` layout, `os1_x86_64.fragment`, `build-kernel.sh`, `build-initramfs.sh`, `pack-initramfs.py`, `qemu-serial-boot.sh`, `os1.sh`, and `.github/workflows/phase1-kernel-boot.yml`.
- [x] **Local Verification (`T0-AUDIT`, `T1-KCONFIG`, `T1-INITRAMFS`):** Passed locally in sandbox VM (`kernelrelease=7.4.0-rc3-os1-g666539eecdf4-dirty`; static C initramfs packed to 323 KiB).
- [ ] **CI Full Kernel Build & QEMU Serial Boot (`T1-KBUILD`, `T1-QEMU-BOOT`):** Pending GitHub Actions run on pushed branch/PR.

## Acceptance Scorecard

| Req ID | System Area | Reference Behavior | Implementation | Test Command | Evidence | Status | Severity | Next Action |
|---|---|---|---|---|---|---|---|---|
| `R0-01` | Repo Audit & Governance | Project resumable from durable docs without chat memory | `docs/*`, `distro/.gitignore` | `./distro/tools/os1.sh audit` | Local audit run (exit 0) | `PASS` | High | Keep updated each session |
| `R1-01` | Kernel Config | Deterministic x86-64 QEMU/UEFI/systemd config with `-os1` identity | `distro/kernel/os1_x86_64.fragment`, `build-kernel.sh` | `./distro/tools/os1.sh kernel --config-only` | `os1_x86_64.config`, `7.4.0-rc3-os1-*` | `PASS` | Critical | — |
| `R1-02` | Kernel Build | Compile real OS-1 `bzImage` with SHA-256 provenance | `distro/kernel/build-kernel.sh` | `./distro/tools/os1.sh kernel` | Pending CI run | `NOT TESTED` | Critical | Run via GitHub Actions `phase1-kernel-boot.yml` |
| `R1-03` | Minimal Userspace | Smallest bootable initramfs (PID 1) | `distro/build/build-initramfs.sh`, `pack-initramfs.py` | `./distro/tools/os1.sh initramfs` | Local 323 KiB `.cpio.gz` (exit 0) | `PASS` | High | Verify BusyBox path in CI |
| `R1-04` | QEMU Serial Boot | Boot OS-1 `bzImage` + initramfs to serial console, verify `uname -a` & clean poweroff | `distro/tests/qemu-serial-boot.sh` | `./distro/tools/os1.sh boot-test` | Pending CI run | `NOT TESTED` | Critical | Run via GitHub Actions & inspect serial log |
| `R2-01` | Debian Userspace & Persistence | Debian stable rootfs + systemd + non-root login + network + APT + reboot persistence | *Not yet implemented* | *Planned* | — | `NOT TESTED` | Critical | Start Phase 2 after R1-04 passes |
| `R3-01` | UEFI Live ISO | One-command UEFI ISO booting in clean QEMU/OVMF | *Not yet implemented* | *Planned* | — | `NOT TESTED` | Critical | Phase 3 |
| `R4-01` | Real Installation | Install from ISO to clean VM disk, detach ISO, reboot, update | *Not yet implemented* | *Planned* | — | `NOT TESTED` | Critical | Phase 4 |
| `R5-01` | Wayland Desktop Session | KDE Plasma/KWin Wayland + XWayland + PipeWire + NetworkManager | *Not yet implemented* | *Planned* | — | `NOT TESTED` | Critical | Phase 5 |
| `R6-12` | macOS Sequoia 15.x Visual & Interaction Fidelity | Original OS-1 identity, Menu Bar, Dock, Finder-class files, Search, Multitasking, Shortcuts | *Not yet implemented* | *Planned* | — | `NOT TESTED` | High | Phases 6–12 |
| `R13-15` | Hardware, Security, Release Qualification | Intel/AMD PCs, signed APT repo, SBOM, upgrade/rollback, release gates | *Not yet implemented* | *Planned* | — | `NOT TESTED` | High | Phases 13–15 |
