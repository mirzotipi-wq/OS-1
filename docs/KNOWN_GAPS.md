# OS-1 Known Gaps & Honest Limitations

## 1. Distribution Components That Do NOT Yet Exist (Post-Phase 0 Audit)

As of baseline commit `666539eecdf4db623f5e3c3e55cf9f2dfad24aa4`, this repository contains **only** the upstream Linux `7.4.0-rc3` kernel source tree plus Phase 0–1 scaffolding. None of the following exist yet:

- **Userspace OS (Phase 2):** No Debian rootfs image, `systemd` init, PAM/login, `NetworkManager`, `PipeWire`, APT configuration, or persistent writable disk image.
- **Bootable Live ISO (Phase 3):** No UEFI GRUB/systemd-boot image, SquashFS rootfs, live boot menu, or recovery mode.
- **System Installer (Phase 4):** No Calamares integration, disk partitioning UI, bootloader installation, or first-user setup.
- **Graphical Wayland Desktop (Phase 5):** No KDE Plasma/KWin Wayland session, SDDM/display manager, Mesa/GPU acceleration tests, or XWayland integration.
- **OS-1 Visual Identity & macOS-Reference UI (Phases 6–12):** No original icon set, typography bundle, wallpapers, light/dark theme tokens, top menu bar, Dock, Finder-class file manager, Launchpad app grid, Spotlight search, Mission Control overview, System Settings, notification center, or macOS-like keyboard/touchpad bindings.
- **Hardware Support & Release Security (Phases 13–15):** No physical Intel/AMD hardware test matrix, Wi-Fi/Bluetooth/suspend validation, signed APT repository, SBOM automation, or Secure Boot signing plan.

## 2. Permanent Platform & Legal Limitations

- **Not macOS:** OS-1 is a GNU/Linux distribution. It does **not** natively execute arbitrary macOS `.app` bundles, Darwin/Mach binaries, Apple Cocoa/AppKit/Metal frameworks, iMessage, FaceTime, AirDrop, iCloud, or Apple ID services.
- **Toolkit Menu/Shortcut Parity:** Under Linux/Wayland, some GTK, Electron, and XWayland applications do not export DBus global menus or respect identical macOS-style `Cmd` (`Super`) shortcuts. These gaps will be tracked per-app in Phase 7 and Phase 12.
- **No Apple Assets:** OS-1 will never ship Apple fonts (SF Pro), icons, sounds, wallpapers, or trademarks. Visual fidelity is achieved through original, legally redistributable assets.

## 3. Environment & Tooling Gaps

- **Kernel RC Status:** `Makefile` is at `7.4.0-rc3` (release candidate). Release candidates can exhibit regressions on physical hardware or filesystems; stability testing and a future move to `7.4` final or an LTS branch are tracked in [`decisions/ADR-0002-kernel-rc-strategy.md`](decisions/ADR-0002-kernel-rc-strategy.md).
- **Sandbox Execution Limits:** The ephemeral development VM lacks `sudo`/`apt`, `bc`, `libelf-dev`, `cpio`, `qemu-system-x86_64`, and `/dev/kvm`. Full kernel compilation and QEMU serial boot verification are therefore automated and executed via GitHub Actions (`ubuntu-latest`) as well as supported on any standard Linux dev host with those packages installed.
