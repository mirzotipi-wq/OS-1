# OS-1 Live Project Status & Acceptance Scorecard

- **Last Updated (UTC):** 2026-11-19
- **Active Branch:** `os1/phase4-real-installer` (PR #4)
- **Upstream Kernel Baseline:** `666539eecdf4db623f5e3c3e55cf9f2dfad24aa4` (`Linux 7.4.0-rc3`, "Baby Opossum Posse")
- **Current Phase:** Phases 0, 1, 2, 3, 4 **PASS** → Advancing to Phase 5 (Stable Graphical Wayland Session)

## Verified Milestones

- [x] **Phase 0 Forensic Audit & Governance:** Durable docs (`docs/*`), ADRs, and `distro/` scaffolding verified (`T0-AUDIT` PASS).
- [x] **Phase 1 Real OS-1 Kernel Build & QEMU Serial Boot Proof:** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44461985823` (`7.4.0-rc3-os1`, 3.18s boot).
- [x] **Phase 2 Real Linux Userspace & Persistent Storage:** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44466206157` (Debian 12 `bookworm`, 2-boot login + NetworkManager + APT + persistence PASS).
- [x] **Phase 3 Bootable x86-64 UEFI Live ISO & Recovery Mode:** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44468834858` (151 MiB UEFI Live ISO, OVMF Live + Recovery Mode PASS).
- [x] **Phase 4 Real Installation on Virtual Disk:**
  - Verified CI Run: `https://github.com/mirzotipi-wq/OS-1/actions/runs/44471364131` (11m43s, exit 0)
  - Nondestructive safety gate: `os1-install` refused without `--confirm-erase-disk` (rc=3).
  - Real GPT + FAT32 ESP + ext4 root + UEFI GRUB `BOOTX64.EFI` + OS-1 kernel (`7.4.0-rc3-os1-g553e7c4c2080`) installed from Live ISO to blank 4 GiB VM disk.
  - ISO completely detached → booted installed disk via OVMF UEFI → logged in as custom user `alice@os1-installed`, verified `/sys/firmware/efi`, `ext4` root, timezone `America/Los_Angeles`, live `apt-get update && apt-get install -y jq`, wrote `/home/alice/installed-proof.txt` → 2nd reboot verified `OS1-PHASE4-INSTALLED-PERSISTENCE-2026` and `jq-1.6` survived cleanly with zero panics.
- [ ] **Phase 5 Stable Graphical Wayland Session:** Next active milestone.

## Acceptance Scorecard

| Req ID | System Area | Reference Behavior | Implementation | Test Command | Evidence | Status | Severity | Next Action |
|---|---|---|---|---|---|---|---|---|
| `R0-01` | Repo Audit & Governance | Project resumable from durable docs | `docs/*`, `distro/.gitignore` | `./distro/tools/os1.sh audit` | CI `44471364131` (exit 0) | `PASS` | High | Maintain every phase |
| `R1-01..04` | OS-1 Kernel & Serial Boot | Compile `7.4.0-rc3-os1`, boot in QEMU to PID 1 | `distro/kernel/*`, `distro/tests/qemu-serial-boot.sh` | `./distro/tools/os1.sh kernel && initramfs && boot-test` | CI `44461985823` (3.18s) | `PASS` | Critical | — |
| `R2-01` | Debian Userspace & Persistence | Debian 12 + systemd + non-root login + network + APT + reboot persistence | `distro/build/build-rootfs.sh`, `distro/tests/qemu-userspace-test.py` | `sudo ./distro/tools/os1.sh rootfs && ./distro/tools/os1.sh userspace-test` | CI `44466206157` (2-boot PASS) | `PASS` | Critical | — |
| `R3-01` | UEFI Live ISO & Recovery | One-command x86-64 UEFI live ISO booting cleanly in QEMU/OVMF + recovery mode | `distro/build/build-iso.sh`, `distro/tests/qemu-iso-uefi-test.py` | `sudo ./distro/tools/os1.sh iso && ./distro/tools/os1.sh iso-test` | CI `44468834858` (Live + Recovery PASS) | `PASS` | Critical | — |
| `R4-01` | Real Installation | Install from live ISO to clean VM disk, detach ISO, reboot, APT update, second reboot | `distro/installer/os1-install`, `distro/tests/qemu-install-test.py` | `sudo ./distro/tools/os1.sh iso && ./distro/tools/os1.sh install-test` | CI `44471364131` (3-boot PASS) | `PASS` | Critical | — |
| `R5-01` | Wayland Desktop Session | KDE Plasma/KWin Wayland + SDDM + XWayland + PipeWire + NetworkManager + terminal/files/browser | *In progress (Phase 5)* | *Planned* | — | `NOT TESTED` | Critical | Implement desktop profile + `qemu-wayland-test.py` |
| `R6-12` | macOS Sequoia 15.x Visual & Interaction Fidelity | Original OS-1 identity, Menu Bar, Dock, Finder-class files, Search, Multitasking, Shortcuts | *Not yet implemented* | *Planned* | — | `NOT TESTED` | High | Phases 6–12 |
| `R13-15` | Hardware, Security, Release Qualification | Intel/AMD PCs, signed APT repo, SBOM, upgrade/rollback, release gates | *Not yet implemented* | *Planned* | — | `NOT TESTED` | High | Phases 13–15 |
