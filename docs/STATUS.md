# OS-1 Live Project Status & Acceptance Scorecard

- **Last Updated (UTC):** 2026-11-19
- **Active Branch:** `os1/phase3-uefi-live-iso` (PR #3)
- **Upstream Kernel Baseline:** `666539eecdf4db623f5e3c3e55cf9f2dfad24aa4` (`Linux 7.4.0-rc3`, "Baby Opossum Posse")
- **Current Phase:** Phases 0, 1, 2, 3 **PASS** → Advancing to Phase 4 (Real Installation on a Virtual Disk)

## Verified Milestones

- [x] **Phase 0 Forensic Audit & Governance:** Repo audited; durable docs (`docs/*`), ADRs, and `distro/` scaffolding committed and verified (`T0-AUDIT` PASS).
- [x] **Phase 1 Real OS-1 Kernel Build & QEMU Serial Boot Proof:** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44461985823` (`7.4.0-rc3-os1-g9e716dcb5530`, 3.18s boot).
- [x] **Phase 2 Real Linux Userspace & Persistent Storage:** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44466206157` (Debian 12 `bookworm`, 238 packages, 2-boot login + NetworkManager + `apt-get install tree` + reboot persistence PASS).
- [x] **Phase 3 Bootable x86-64 UEFI Live ISO & Recovery Mode:**
  - Verified CI Run: `https://github.com/mirzotipi-wq/OS-1/actions/runs/44468834858` (4m05s, exit 0)
  - ISO Artifact: `os1-live-x86_64.iso` (158,492,672 bytes / 151 MiB, SHA-256 `e690c61538273c789a20543d7140c1dcca751101fd31e8ebd838016b27963fd2`)
  - Kernel Booted via UEFI GRUB: `7.4.0-rc3-os1-gd76dde9d39e4`
  - OVMF Proof: Fresh ISO booted purely through OVMF UEFI firmware (zero `-kernel`/`-initrd` shortcuts, zero host bind mounts) → verified `/sys/firmware/efi`, `overlay` root, `ID=os1`, non-root `os1` login, NetworkManager IPv4, clean poweroff, AND GRUB Recovery Mode (`OS-1_RECOVERY_MODE_READY`, `e2fsck 1.47.0`, clean poweroff in 5.46s).
- [ ] **Phase 4 Real Installation on Virtual Disk:** Next active milestone.

## Acceptance Scorecard

| Req ID | System Area | Reference Behavior | Implementation | Test Command | Evidence | Status | Severity | Next Action |
|---|---|---|---|---|---|---|---|---|
| `R0-01` | Repo Audit & Governance | Project resumable from durable docs | `docs/*`, `distro/.gitignore` | `./distro/tools/os1.sh audit` | CI `44468834858` (exit 0) | `PASS` | High | Maintain every phase |
| `R1-01..04` | OS-1 Kernel & Serial Boot | Compile `7.4.0-rc3-os1`, boot in QEMU to PID 1 | `distro/kernel/*`, `distro/tests/qemu-serial-boot.sh` | `./distro/tools/os1.sh kernel && initramfs && boot-test` | CI `44461985823` (3.18s) | `PASS` | Critical | — |
| `R2-01` | Debian Userspace & Persistence | Debian 12 + systemd + non-root login + network + APT + reboot persistence | `distro/build/build-rootfs.sh`, `distro/tests/qemu-userspace-test.py` | `sudo ./distro/tools/os1.sh rootfs && ./distro/tools/os1.sh userspace-test` | CI `44466206157` (2-boot PASS) | `PASS` | Critical | — |
| `R3-01` | UEFI Live ISO & Recovery | One-command x86-64 UEFI live ISO booting cleanly in QEMU/OVMF + recovery mode | `distro/build/build-iso.sh`, `distro/tests/qemu-iso-uefi-test.py` | `sudo ./distro/tools/os1.sh iso && ./distro/tools/os1.sh iso-test` | CI `44468834858` (151 MiB ISO, Live + Recovery PASS) | `PASS` | Critical | — |
| `R4-01` | Real Installation | Install from live ISO to clean VM disk, detach ISO, reboot, APT update, second reboot | *In progress (Phase 4)* | *Planned* | — | `NOT TESTED` | Critical | Implement `os1-install` + Calamares config + `qemu-install-test.py` |
| `R5-01` | Wayland Desktop Session | KDE Plasma/KWin Wayland + XWayland + PipeWire + NetworkManager | *Not yet implemented* | *Planned* | — | `NOT TESTED` | Critical | Phase 5 |
| `R6-12` | macOS Sequoia 15.x Visual & Interaction Fidelity | Original OS-1 identity, Menu Bar, Dock, Finder-class files, Search, Multitasking, Shortcuts | *Not yet implemented* | *Planned* | — | `NOT TESTED` | High | Phases 6–12 |
| `R13-15` | Hardware, Security, Release Qualification | Intel/AMD PCs, signed APT repo, SBOM, upgrade/rollback, release gates | *Not yet implemented* | *Planned* | — | `NOT TESTED` | High | Phases 13–15 |
