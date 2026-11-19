# ADR-0001: OS-1 Baseline Distribution Architecture

- **Status:** Accepted
- **Date:** 2026-11-18
- **Decision Makers:** OS-1 Architecture Lead

## Context

The repository `mirzotipi-wq/OS-1` begins as a pure upstream Linux kernel source tree (`7.4.0-rc3`). To build a real, bootable, installable, daily-usable x86-64 Linux desktop distribution with high visual and interaction fidelity to a modern macOS reference (macOS Sequoia 15.x), we need a maintainable userspace, graphics stack, packaging format, installer, and repository layout.

## Decision

1. **Userspace:** Pinned Debian stable GNU/Linux (`systemd`, `glibc`, `APT`, `NetworkManager`, `PipeWire`, XDG portals) built reproducibly via `mmdebstrap`/`debootstrap` and native `.deb` packages.
2. **Graphics & Compositor:** Wayland-first KDE Plasma / KWin with Qt/QML and KDE Frameworks, plus XWayland for legacy applications. Custom OS-1 shell components (top menu bar, Dock, Launchpad grid, Spotlight search) will be built as maintainable Qt/QML modules and KWin plugins/scripts rather than fragile third-party GNOME Shell monkey-patches.
3. **Installer:** Calamares on an x86-64 UEFI live ISO (`grub-efi` + SquashFS + OS-1 kernel/initramfs).
4. **Repository Organization:** Keep the upstream kernel source tree intact at `/` and place all distribution orchestration, kernel configs, packaging, shell, apps, branding, installer, and tests under `distro/`, with durable governance and handoff docs under `docs/`.

## Consequences

- **Positive:** Standard upstream Linux kernel build remains unbroken; proven Debian security/driver/package ecosystem; KWin natively supports blur, rounded corners, global menus, virtual desktops, and HiDPI scaling on Wayland.
- **Negative / Trade-offs:** Repository is large because it hosts the full Linux kernel tree; CI must use shallow checkouts, out-of-tree builds (`distro/out/`), and strict artifact retention limits. If repository size ever impedes desktop CI, desktop packages can later be split into companion repos while still pinning exact OS-1 kernel commits.
