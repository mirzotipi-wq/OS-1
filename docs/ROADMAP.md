# OS-1 Master Roadmap (Phases 0–15)

## Compute & Disk Budget Guidelines

- **Kernel out-of-tree build (`distro/out/kernel-build`):** ~2.5–4.5 GB disk, 4–12 min on 4 vCPU.
- **Minimal initramfs (`distro/out/initramfs`):** < 20 MB disk, < 10 s.
- **Debian rootfs + live ISO (Phases 2–3):** ~6–12 GB disk during build; final ISO target < 2.5 GB.
- **CI Artifact Retention:** Maximum 7 days for non-release CI logs/manifests; release ISOs published via GitHub Releases with SHA-256 checksums, never committed to Git.
- **Preflight Gate:** Every build script checks free disk space before executing.

## Phase Gates & Dependency Graph

| Phase | Name | Depends On | Objective Pass Gate | Current Status |
|---|---|---|---|---|
| **0** | Forensic audit & technical plan | — | Repo audited; `docs/*`, ADRs, and `distro/` scaffolding committed; project resumable without chat history. | **IN PROGRESS** |
| **1** | Build real OS-1 kernel + QEMU serial boot | Phase 0 | Deterministic x86-64 `os1` kernel built from exact SHA; boots in QEMU to serial console + minimal initramfs PID 1 proof; logs & SHA-256 provenance recorded. | **IN PROGRESS** |
| **2** | Real Linux userspace & persistent storage | Phase 1 | Debian stable rootfs + systemd + networking + APT + non-root user on persistent ext4 disk image; boots with OS-1 kernel, installs a package, persists file across reboot. | NOT STARTED |
| **3** | Bootable UEFI live ISO & recovery | Phase 2 | One-command x86-64 UEFI live ISO boots cleanly in fresh QEMU/OVMF VM without host bind mounts; recovery mode works; SHA-256 + provenance recorded. | NOT STARTED |
| **4** | Real installation on virtual disk | Phase 3 | Calamares (or scripted+GUI) installs from live ISO to clean VM disk; ISO detached; boots installed OS-1 kernel, updates packages, survives reboot. | NOT STARTED |
| **5** | Stable graphical Wayland session | Phase 4 | KDE Plasma/KWin Wayland + XWayland + display manager + PipeWire + NetworkManager; clean graphical login, terminal/browser/files, resize, audio, logout, reboot. | NOT STARTED |
| **6** | Visual design system & OS-1 identity | Phase 5 | Original icons, typography, wallpapers, light/dark tokens, materials, window chrome, shadows, blur; screenshot baseline at `1440×900`, `1920×1080`, HiDPI; license inventory. | NOT STARTED |
| **7** | Menu bar & Dock | Phase 6 | Working top menu bar (app identity, global menu where supported, clock, status, quick controls) + Dock (pin/reorder/launch/minimize/indicators/trash/drag-drop) verified with automated flows. | NOT STARTED |
| **8** | Finder-class file experience | Phase 6 | Native file manager with sidebar, tabs, views, search, Quick Look preview, mounts, trash, copy/move/undo; automated fs test suite (symlinks, Unicode, large files, permissions). | NOT STARTED |
| **9** | App launcher, Spotlight search, multitasking | Phase 7 | Real desktop-entry app grid, fast global search with privacy controls, Mission Control overview, virtual desktops/Spaces, tiling/full-screen; measured latency & multi-monitor tests. | NOT STARTED |
| **10** | Notifications, quick controls, System Settings, onboarding | Phase 7 | Notification center, real OS-backed toggles (network/BT/audio/display/power), unified System Settings, first-run onboarding; settings persist across reboot. | NOT STARTED |
| **11** | Essential native applications | Phase 8–10 | Working terminal, text editor, media/image/PDF viewers, calculator, notes, archive manager, browser, screenshot/recording, process monitor, software center; no decorative shells. | NOT STARTED |
| **12** | Usability & interaction fidelity | Phase 7–11 | Command/Super bindings, window shortcuts, clipboard, scrolling/gestures, animations, reduced-motion/transparency modes; full comparison matrix with reproducers. | NOT STARTED |
| **13** | Hardware, performance, power, accessibility | Phase 5–12 | Intel/AMD GPU acceleration + fallback, Wi-Fi/BT/audio/webcam/external display/HiDPI/suspend/battery, screen reader, high contrast, keyboard-only navigation; baselines recorded. | NOT STARTED |
| **14** | Distribution maintenance & security | Phase 4–13 | Signed `.deb` repos, kernel security update process, SBOM, firewall defaults, least privilege, upgrade & rollback drills, license compliance audit. | NOT STARTED |
| **15** | Release qualification | Phase 0–14 | Alpha → Beta → RC → Stable release candidates passing full clean-install, upgrade, regression, accessibility, security, and visual-fidelity gates. | NOT STARTED |
