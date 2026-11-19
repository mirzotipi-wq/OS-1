# OS-1 Live Project Status & Acceptance Scorecard

- **Last Updated (UTC):** 2026-11-19
- **Branch:** `master` (`6a8fdcfe2c` + final docs update)
- **Upstream Kernel Baseline:** `666539eecdf4db623f5e3c3e55cf9f2dfad24aa4` (`Linux 7.4.0-rc3`, "Baby Opossum Posse", built as `7.4.0-rc3-os1`)
- **Current Release Status:** **OS-1 1.0-rc1 — Phases 0–15 COMPLETE & CI-VERIFIED** (QEMU/OVMF x86-64 UEFI virtualization target)

## Verified Milestones (Phases 0–15)

- [x] **Phase 0 — Forensic Audit & Governance (PR #1):** Durable docs (`docs/*`), ADRs, and `distro/` scaffolding verified (`T0-AUDIT` PASS).
- [x] **Phase 1 — Real OS-1 Kernel Build & QEMU Serial Boot Proof (PR #1):** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44461985823` (`7.4.0-rc3-os1`, 3.18s boot).
- [x] **Phase 2 — Real Linux Userspace & Persistent Storage (PR #2):** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44466206157` (Debian 12 `bookworm`, 2-boot login + NetworkManager + APT + persistence PASS).
- [x] **Phase 3 — Bootable x86-64 UEFI Live ISO & Recovery Mode (PR #3):** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44468834858` (OVMF Live + Recovery Mode PASS).
- [x] **Phase 4 — Real Installation on Virtual Disk (PR #4):** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44471364131` (11m43s; nondestructive gate rc=3, GPT+ESP+ext4 install, detached ISO UEFI boot, custom user `alice@os1-installed`, APT install `jq`, 2nd reboot persistence PASS).
- [x] **Phase 5 — Stable Graphical Wayland Session (PR #5):** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44482048774` (6m21s; `7.4.0-rc3-os1`, SDDM, `kwin_wayland`, live `plasmashell`, `pipewire`, `konsole`, `1440×900` framebuffer screenshot verified).
- [x] **Phases 6 & 7 — Visual Design System, Original OS-1 Identity, Top Menu Bar & Floating Dock (PR #6):** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44486494590` (10m06s; `OS1Horizon` Light/Dark wallpapers, `os1-logo.svg`, `OS1Sequoia` left traffic-light Aurorae theme, 28px Top Menu Bar, Floating Bottom Dock, `os1-appearance`).
- [x] **Phases 8–12 — Finder-class Files, Spotlight/Overview/Spaces, Controls/Onboarding, 11 Native Apps & Accessibility (PR #7):** CI `https://github.com/mirzotipi-wq/OS-1/actions/runs/44488906713` (9m14s; `os1-fs-test` 6/6, 11/11 native apps, `notify-send`, `nmcli`, `upower`, `os1-accessibility`, `os1-firstboot` Dark mode switch, Light & Dark `1440×900` QEMU screenshots visually verified with all 7 pinned Dock icons + Trash).
- [x] **Phases 13–15 — Hardware/A11y Baseline, Native `.deb` Packaging, CycloneDX 1.5 SBOM, UFW Security & Full Desktop UEFI Live ISO Release Qualification (PR #8):**
  - Verified CI Run: `https://github.com/mirzotipi-wq/OS-1/actions/runs/44491035539` (19m11s, exit 0)
  - Native `.deb` packages + local APT repo (`os1-branding_1.0.0_all.deb`, `os1-shell_1.0.0_all.deb`, `os1-desktop-meta_1.0.0_amd64.deb`, `Packages`, `Packages.gz`, `Release`, `SHA256SUMS`).
  - Full Desktop UEFI Live ISO (`843 MiB`, SHA-256 `4f5690e6f0432094fb538b744d88ca93eaf8e8f15681bc27b98eeb9eec9c5147`) + CycloneDX 1.5 JSON SBOM (`1,035` components).
  - Full Desktop ISO booted via OVMF UEFI (Live + Recovery Mode), clean-installed to blank 10 GiB virtual disk, ISO detached, booted installed OS-1 disk, verified UFW default-deny incoming firewall, `orca` screen reader, `os1-fs-test`, live `apt-get install jq`, and 2nd reboot persistence with zero kernel panics.

## Acceptance Scorecard

| Req ID | System Area | Implementation | Evidence | Status |
|---|---|---|---|---|
| `R0-01` | Repo Audit & Governance | `docs/*`, `distro/.gitignore`, `distro/tools/os1.sh` | CI `44491035539` (`T0-AUDIT`) | `PASS` |
| `R1-01..04` | OS-1 Kernel & Serial Boot | `distro/kernel/*`, `distro/tests/qemu-serial-boot.sh` | CI `44461985823` (`7.4.0-rc3-os1`) | `PASS` |
| `R2-01` | Debian Userspace & Persistence | `distro/build/build-rootfs.sh`, `qemu-userspace-test.py` | CI `44466206157` (2-boot PASS) | `PASS` |
| `R3-01` | UEFI Live ISO & Recovery | `distro/build/build-iso.sh`, `qemu-iso-uefi-test.py` | CI `44468834858` & `44491035539` | `PASS` |
| `R4-01` | Real Installation | `distro/installer/os1-install`, `qemu-install-test.py` | CI `44471364131` & `44491035539` | `PASS` |
| `R5-01` | Wayland Desktop Session | `OS1_PROFILE=desktop`, `qemu-wayland-test.py` | CI `44482048774` (`1440×900` PNG) | `PASS` |
| `R6-01`, `R7-01` | Visual Identity, Menu Bar & Dock | `distro/branding/*`, `distro/shell/*` | CI `44486494590` & `44488906713` | `PASS` |
| `R8-12` | Files, Search, Controls, 11 Apps, A11y | `distro/apps/*`, `os1-firstboot`, `os1-accessibility`, `os1-fs-test` | CI `44488906713` (Light + Dark PNGs) | `PASS` |
| `R13-15` | Hardware/A11y, `.deb`s, SBOM, UFW, Desktop ISO Qualification | `build-debs.sh`, `generate-sbom.py`, `phase14-15-release-qualification.yml` | CI `44491035539` (843 MiB Desktop ISO, 1,035 SBOM components) | `PASS` (VM) / `HARDWARE-GATED` (Bare Metal) |
