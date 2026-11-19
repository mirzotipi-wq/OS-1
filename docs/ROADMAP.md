# OS-1 Master Roadmap (Phases 0–15)

## Compute & Disk Budget Guidelines

- **Kernel out-of-tree build (`distro/out/kernel-build`):** ~2.5–4.5 GB disk, 4–12 min on 4 vCPU.
- **Minimal initramfs (`distro/out/initramfs`):** < 20 MB disk, < 10 s.
- **Debian desktop rootfs + live ISO:** ~6–12 GB disk during build; final full Desktop UEFI Live ISO is **843 MiB** (well under the 2.5 GB target).
- **CI Artifact Retention:** Maximum 7 days for non-release CI logs/manifests; release ISOs published via GitHub Releases with SHA-256 checksums, never committed to Git.
- **Preflight Gate:** Every build script checks free disk space before executing.

## Phase Gates & Dependency Graph

| Phase | Name | Depends On | Objective Pass Gate | Current Status |
|---|---|---|---|---|
| **0** | Forensic audit & technical plan | — | Repo audited; `docs/*`, ADRs, and `distro/` scaffolding committed; project resumable without chat history. | **PASS** (PR #1) |
| **1** | Build real OS-1 kernel + QEMU serial boot | Phase 0 | Deterministic x86-64 `os1` kernel built from exact SHA; boots in QEMU to serial console + minimal initramfs PID 1 proof; logs & SHA-256 provenance recorded. | **PASS** (CI `44461985823`) |
| **2** | Real Linux userspace & persistent storage | Phase 1 | Debian stable rootfs + systemd + networking + APT + non-root user on persistent ext4 disk image; boots with OS-1 kernel, installs a package, persists file across reboot. | **PASS** (CI `44466206157`) |
| **3** | Bootable UEFI live ISO & recovery | Phase 2 | One-command x86-64 UEFI live ISO boots cleanly in fresh QEMU/OVMF VM without host bind mounts; recovery mode works; SHA-256 + provenance recorded. | **PASS** (CI `44468834858`) |
| **4** | Real installation on virtual disk | Phase 3 | Installer writes GPT+ESP+ext4+GRUB+OS-1 kernel from live ISO to clean VM disk; ISO detached; boots installed OS-1 kernel, updates packages, survives reboot. | **PASS** (CI `44471364131`) |
| **5** | Stable graphical Wayland session | Phase 4 | KDE Plasma/KWin Wayland + XWayland + SDDM + PipeWire + NetworkManager; clean graphical login, terminal/browser/files, `1440×900` framebuffer proof. | **PASS** (CI `44482048774`) |
| **6** | Visual design system & OS-1 identity | Phase 5 | Original wallpapers (`OS1Horizon`), emblem (`os1-logo.svg`), Light/Dark tokens & color schemes, left traffic-light Aurorae theme (`OS1Sequoia`), license inventory. | **PASS** (CI `44486494590`) |
| **7** | Menu bar & Dock | Phase 6 | Working 28px Top Menu Bar (`appmenu`, System Tray, clock) + centered Floating Bottom Dock (`icontasks` + 7 pinned apps + Trash) visually verified in Light & Dark modes. | **PASS** (CI `44486494590` & `44488906713`) |
| **8** | Finder-class file experience | Phase 6 | Dolphin Finder defaults + automated `os1-fs-test` suite (create/copy/move/rename, XDG Trash & restore, symlinks, Unicode/emoji, 16 MiB SHA-256, EACCES). | **PASS** (CI `44488906713`) |
| **9** | App launcher, Spotlight search, multitasking | Phase 7 | Global shortcuts (`Meta+Space` KRunner, `Meta+Up` Overview, `Meta+Left/Right` Spaces, `Meta+Shift+3/4` Spectacle) + local-first KRunner privacy defaults. | **PASS** (CI `44488906713`) |
| **10** | Notifications, quick controls, System Settings, onboarding | Phase 7 | `notify-send`, NetworkManager, UPower, System Settings, `os1-firstboot` onboarding CLI with persisted appearance & accessibility config. | **PASS** (CI `44488906713`) |
| **11** | Essential native applications | Phase 8–10 | 11 real native apps (`dolphin`, `firefox-esr`, `konsole`, `kate`, `gwenview`, `okular`, `kcalc`, `ark`, `spectacle`, `plasma-systemmonitor`, `systemsettings`) verified via `apps-manifest.json`. | **PASS** (CI `44488906713`) |
| **12** | Usability & interaction fidelity | Phase 7–11 | `os1-accessibility` (`reduced-motion`, `reduced-transparency`), full keyboard/pointer/touchpad parity matrix (`docs/INTERACTION_MATRIX.md`). | **PASS** (CI `44488906713`) |
| **13** | Hardware, performance, power, accessibility | Phase 5–12 | `orca` screen reader, `power-profiles-daemon`, `upower`, Mesa DRM/KMS + `llvmpipe` fallback (`10-os1-gpu-env`), `docs/HARDWARE_AND_A11Y.md`. | **PASS (VM)** / Bare-Metal Hardware-Gated |
| **14** | Distribution maintenance & security | Phase 4–13 | Native `.deb` packages (`os1-branding`, `os1-shell`, `os1-desktop-meta`), local APT repo, CycloneDX 1.5 SBOM (1,035 components), UFW default-deny incoming firewall, locked root, license inventory. | **PASS** (CI `44491035539`) |
| **15** | Release qualification | Phase 0–14 | 843 MiB full Desktop UEFI Live ISO passes OVMF Live + Recovery boot, 10 GiB clean-disk installation, detached-ISO 2-reboot persistence, UFW/Orca/`os1-fs-test`, SHA-256 sums, zero kernel panics. | **PASS (1.0-rc1 VM)** (CI `44491035539`) |
