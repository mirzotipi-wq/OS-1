# OS-1 Live Project Status & Acceptance Scorecard

- **Last Updated (UTC):** 2026-11-19
- **Active Branch:** `os1/phase5-wayland-desktop` (PR #5)
- **Upstream Kernel Baseline:** `666539eecdf4db623f5e3c3e55cf9f2dfad24aa4` (`Linux 7.4.0-rc3`, "Baby Opossum Posse")
- **Current Phase:** Phases 0–5 **PASS** → Advancing to Phase 6 (Visual Design System & OS-1 Identity)

## Verified Milestones

- [x] **Phase 0 Forensic Audit & Governance:** Durable docs (`docs/*`), ADRs, and `distro/` scaffolding verified (`T0-AUDIT` PASS).
- [x] **Phase 1 Real OS-1 Kernel Build & QEMU Serial Boot Proof:** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44461985823` (`7.4.0-rc3-os1`, 3.18s boot).
- [x] **Phase 2 Real Linux Userspace & Persistent Storage:** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44466206157` (Debian 12 `bookworm`, 2-boot login + NetworkManager + APT + persistence PASS).
- [x] **Phase 3 Bootable x86-64 UEFI Live ISO & Recovery Mode:** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44468834858` (151 MiB UEFI Live ISO, OVMF Live + Recovery Mode PASS).
- [x] **Phase 4 Real Installation on Virtual Disk:** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44471364131` (11m43s; nondestructive gate, GPT+ESP+ext4 install, detached ISO UEFI boot, custom user `alice@os1-installed`, APT install `jq`, 2nd reboot persistence PASS).
- [x] **Phase 5 Stable Graphical Wayland Session:**
  - Verified CI Run: `https://github.com/mirzotipi-wq/OS-1/actions/runs/44482048774` (6m21s, exit 0)
  - Desktop rootfs (`OS1_PROFILE=desktop`): Debian 12 `bookworm`, 948 packages, 6144 MiB ext4 image (`a7365613a48f58a57713d17b4b0a9bd1b5f71033d65b56b8b2e4a7a6c5260baf`).
  - Booted on OS-1 kernel (`7.4.0-rc3-os1`) in QEMU (`virtio-vga,xres=1440,yres=900`, `intel-hda`, `virtio-net-pci`, `-cpu Haswell` TCG): verified `sddm.service` active, `kwin_wayland` + `/run/user/1000/wayland-0`, live `plasmashell`, `pipewire`/`pipewire-pulse`, core apps (`konsole 22.12.3`, `dolphin 22.12.3`, `firefox-esr 140.12.0esr`), launched `konsole` inside Wayland session, captured & visually verified real `1440×900` framebuffer screenshot (`phase5-wayland-desktop.png`), clean poweroff with zero panics.
- [ ] **Phase 6 Visual Design System & OS-1 Identity:** Next active milestone.

## Acceptance Scorecard

| Req ID | System Area | Reference Behavior | Implementation | Test Command | Evidence | Status | Severity | Next Action |
|---|---|---|---|---|---|---|---|---|
| `R0-01` | Repo Audit & Governance | Project resumable from durable docs | `docs/*`, `distro/.gitignore` | `./distro/tools/os1.sh audit` | CI `44482048774` (exit 0) | `PASS` | High | Maintain every phase |
| `R1-01..04` | OS-1 Kernel & Serial Boot | Compile `7.4.0-rc3-os1`, boot in QEMU to PID 1 | `distro/kernel/*`, `distro/tests/qemu-serial-boot.sh` | `./distro/tools/os1.sh kernel && initramfs && boot-test` | CI `44461985823` (3.18s) | `PASS` | Critical | — |
| `R2-01` | Debian Userspace & Persistence | Debian 12 + systemd + non-root login + network + APT + reboot persistence | `distro/build/build-rootfs.sh`, `distro/tests/qemu-userspace-test.py` | `sudo ./distro/tools/os1.sh rootfs && ./distro/tools/os1.sh userspace-test` | CI `44466206157` (2-boot PASS) | `PASS` | Critical | — |
| `R3-01` | UEFI Live ISO & Recovery | One-command x86-64 UEFI live ISO booting cleanly in QEMU/OVMF + recovery mode | `distro/build/build-iso.sh`, `distro/tests/qemu-iso-uefi-test.py` | `sudo ./distro/tools/os1.sh iso && ./distro/tools/os1.sh iso-test` | CI `44468834858` (Live + Recovery PASS) | `PASS` | Critical | — |
| `R4-01` | Real Installation | Install from live ISO to clean VM disk, detach ISO, reboot, APT update, second reboot | `distro/installer/os1-install`, `distro/tests/qemu-install-test.py` | `sudo ./distro/tools/os1.sh iso && ./distro/tools/os1.sh install-test` | CI `44471364131` (3-boot PASS) | `PASS` | Critical | — |
| `R5-01` | Wayland Desktop Session | KDE Plasma/KWin Wayland + SDDM + XWayland + PipeWire + NetworkManager + terminal/files/browser | `distro/build/build-rootfs.sh` (`OS1_PROFILE=desktop`), `distro/tests/qemu-wayland-test.py` | `sudo OS1_PROFILE=desktop OS1_DESKTOP_AUTOLOGIN=1 ./distro/tools/os1.sh rootfs && ./distro/tools/os1.sh wayland-test` | CI `44482048774` (`1440×900` PNG verified) | `PASS` | Critical | — |
| `R6-12` | macOS Sequoia 15.x Visual & Interaction Fidelity | Original OS-1 identity, Menu Bar, Dock, Finder-class files, Search, Multitasking, Shortcuts | *In progress (Phase 6 next)* | *Planned* | — | `NOT TESTED` | High | Phases 6–12 |
| `R13-15` | Hardware, Security, Release Qualification | Intel/AMD PCs, signed APT repo, SBOM, upgrade/rollback, release gates | *Not yet implemented* | *Planned* | — | `NOT TESTED` | High | Phases 13–15 |
