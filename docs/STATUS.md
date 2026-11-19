# OS-1 Live Project Status & Acceptance Scorecard

- **Last Updated (UTC):** 2026-11-19
- **Active Branch:** `os1/phase6-7-design-and-shell` (PR #6)
- **Upstream Kernel Baseline:** `666539eecdf4db623f5e3c3e55cf9f2dfad24aa4` (`Linux 7.4.0-rc3`, "Baby Opossum Posse")
- **Current Phase:** Phases 0–7 **PASS** → Advancing to Phases 8–11 (Finder-class Files, Launchpad/Spotlight/Multitasking, Settings/Onboarding, Essential Native Apps)

## Verified Milestones

- [x] **Phase 0 Forensic Audit & Governance:** Durable docs (`docs/*`), ADRs, and `distro/` scaffolding verified (`T0-AUDIT` PASS).
- [x] **Phase 1 Real OS-1 Kernel Build & QEMU Serial Boot Proof:** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44461985823` (`7.4.0-rc3-os1`, 3.18s boot).
- [x] **Phase 2 Real Linux Userspace & Persistent Storage:** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44466206157` (Debian 12 `bookworm`, 2-boot login + NetworkManager + APT + persistence PASS).
- [x] **Phase 3 Bootable x86-64 UEFI Live ISO & Recovery Mode:** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44468834858` (151 MiB UEFI Live ISO, OVMF Live + Recovery Mode PASS).
- [x] **Phase 4 Real Installation on Virtual Disk:** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44471364131` (11m43s; nondestructive gate, GPT+ESP+ext4 install, detached ISO UEFI boot, custom user `alice@os1-installed`, APT install `jq`, 2nd reboot persistence PASS).
- [x] **Phase 5 Stable Graphical Wayland Session:** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44482048774` (6m21s; `7.4.0-rc3-os1`, SDDM, `kwin_wayland`, live `plasmashell`, `pipewire`, `konsole`, `1440×900` framebuffer screenshot verified).
- [x] **Phase 6 Visual Design System & Original OS-1 Identity + Phase 7 Top Menu Bar & Floating Dock:**
  - Verified CI Run: `https://github.com/mirzotipi-wq/OS-1/actions/runs/44486494590` (10m06s, exit 0)
  - Original OS-1 identity (`distro/branding/`): `tokens.json` (macOS Sequoia 15.x reference), deterministic `generate-assets.py` producing original `OS1Horizon` Light/Dark `1920×1080` PNG wallpapers, original `os1-logo.svg`, and `OS1Sequoia` Aurorae theme with left-aligned traffic-light window controls (`XIA`), `OS1Light.colors`, `OS1Dark.colors`, `org.os1.desktop` Look-and-Feel, all registered in `docs/LEGAL_AND_LICENSES.md` (zero Apple IP).
  - Shell layout (`distro/shell/`): 28px Top Menu Bar (OS-1 logo menu, `org.kde.plasma.appmenu`, System Tray, `Thu Nov 19 8:26 AM` clock) + centered floating bottom Dock (`org.kde.plasma.icontasks`, `org.kde.plasma.trash`) + `os1-appearance [light|dark]` + `os1-shell-init`. Visually verified in downloaded `1440×900` QEMU framebuffer screenshots.
- [ ] **Phases 8–11 Finder-class Files, Search/Multitasking, Settings/Onboarding, Native Apps:** Next active milestone.

## Acceptance Scorecard

| Req ID | System Area | Reference Behavior | Implementation | Test Command | Evidence | Status | Severity | Next Action |
|---|---|---|---|---|---|---|---|---|
| `R0-01` | Repo Audit & Governance | Project resumable from durable docs | `docs/*`, `distro/.gitignore` | `./distro/tools/os1.sh audit` | CI `44486494590` (exit 0) | `PASS` | High | Maintain every phase |
| `R1-01..04` | OS-1 Kernel & Serial Boot | Compile `7.4.0-rc3-os1`, boot in QEMU to PID 1 | `distro/kernel/*`, `distro/tests/qemu-serial-boot.sh` | `./distro/tools/os1.sh kernel && initramfs && boot-test` | CI `44461985823` (3.18s) | `PASS` | Critical | — |
| `R2-01` | Debian Userspace & Persistence | Debian 12 + systemd + non-root login + network + APT + reboot persistence | `distro/build/build-rootfs.sh`, `distro/tests/qemu-userspace-test.py` | `sudo ./distro/tools/os1.sh rootfs && ./distro/tools/os1.sh userspace-test` | CI `44466206157` (2-boot PASS) | `PASS` | Critical | — |
| `R3-01` | UEFI Live ISO & Recovery | One-command x86-64 UEFI live ISO booting cleanly in QEMU/OVMF + recovery mode | `distro/build/build-iso.sh`, `distro/tests/qemu-iso-uefi-test.py` | `sudo ./distro/tools/os1.sh iso && ./distro/tools/os1.sh iso-test` | CI `44468834858` (Live + Recovery PASS) | `PASS` | Critical | — |
| `R4-01` | Real Installation | Install from live ISO to clean VM disk, detach ISO, reboot, APT update, second reboot | `distro/installer/os1-install`, `distro/tests/qemu-install-test.py` | `sudo ./distro/tools/os1.sh iso && ./distro/tools/os1.sh install-test` | CI `44471364131` (3-boot PASS) | `PASS` | Critical | — |
| `R5-01` | Wayland Desktop Session | KDE Plasma/KWin Wayland + SDDM + XWayland + PipeWire + NetworkManager + terminal/files/browser | `distro/build/build-rootfs.sh` (`OS1_PROFILE=desktop`), `distro/tests/qemu-wayland-test.py` | `sudo OS1_PROFILE=desktop OS1_DESKTOP_AUTOLOGIN=1 ./distro/tools/os1.sh rootfs && ./distro/tools/os1.sh wayland-test` | CI `44482048774` (`1440×900` PNG verified) | `PASS` | Critical | — |
| `R6-01`, `R7-01` | OS-1 Visual Identity, Top Menu Bar & Floating Dock | Original wallpapers/logo/tokens, Light/Dark themes, left traffic lights, Top Menu Bar, Floating Bottom Dock | `distro/branding/*`, `distro/shell/*` | `sudo OS1_PROFILE=desktop OS1_DESKTOP_AUTOLOGIN=1 ./distro/tools/os1.sh rootfs && ./distro/tools/os1.sh wayland-test` | CI `44486494590` (screenshots visually verified) | `PASS` | High | Polish Dock pinned launcher icons & Dark repaint wait in Phase 8-11 |
| `R8-12` | Finder-class Files, Search, Multitasking, Settings, Apps, Shortcuts | Dolphin Finder defaults + fs suite, Spotlight/Overview, onboarding, native apps, shortcuts | *In progress (Phases 8–11 next)* | *Planned* | — | `NOT TESTED` | High | Implement Phases 8–12 |
| `R13-15` | Hardware, Security, Release Qualification | Native `.deb` packaging, signed APT repo, SBOM, full Desktop UEFI Live ISO, release gates | *Not yet implemented* | *Planned* | — | `NOT TESTED` | High | Implement Phases 13–15 |
