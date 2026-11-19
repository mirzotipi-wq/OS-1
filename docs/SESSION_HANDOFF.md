# OS-1 Session Handoff & Reproduction Guide

- **Last Updated (UTC):** 2026-11-19
- **Repository:** `https://github.com/mirzotipi-wq/OS-1.git`
- **Branch:** `master`
- **Status:** **OS-1 1.0-rc1 — Phases 0–15 COMPLETE & CI-VERIFIED**

## Quick Reproduction Commands (Linux Host or CI Runner)

```bash
# 1. Audit repository, script syntax, and disk space
./distro/tools/os1.sh audit

# 2. Build the in-repo OS-1 kernel (7.4.0-rc3-os1)
./distro/tools/os1.sh kernel

# 3. Build native OS-1 .deb packages & local APT repository
./distro/tools/os1.sh debs

# 4. Build full OS-1 Wayland Desktop rootfs & bootable x86-64 UEFI Live ISO (843 MiB)
sudo OS1_PROFILE=desktop OS1_DESKTOP_AUTOLOGIN=1 ./distro/tools/os1.sh rootfs
sudo ./distro/tools/os1.sh iso

# 5. Generate CycloneDX 1.5 JSON SBOM
./distro/tools/os1.sh sbom

# 6. Run automated verification suites in QEMU / OVMF
./distro/tools/os1.sh wayland-test
./distro/tools/os1.sh iso-test
OS1_INSTALL_DISK_GB=10 OS1_INSTALL_RAM=2048M ./distro/tools/os1.sh install-test
```

## Merged Pull Requests & Verified CI Runs

- **PR #1 (Phases 0–1):** Kernel `7.4.0-rc3-os1` + QEMU serial boot — CI `44461985823` (PASS)
- **PR #2 (Phase 2):** Debian 12 userspace + persistence — CI `44466206157` (PASS)
- **PR #3 (Phase 3):** UEFI Live ISO + Recovery Mode — CI `44468834858` (PASS)
- **PR #4 (Phase 4):** Clean-disk UEFI installation + 2 reboots — CI `44471364131` (PASS)
- **PR #5 (Phase 5):** KDE Plasma/KWin Wayland desktop — CI `44482048774` (PASS)
- **PR #6 (Phases 6–7):** OS-1 identity, Top Menu Bar, Floating Dock — CI `44486494590` (PASS)
- **PR #7 (Phases 8–12):** Finder-class Files, Spotlight/Overview, 11 Native Apps, A11y, Light/Dark screenshots — CI `44488906713` (PASS)
- **PR #8 (Phases 13–15):** Native `.deb`s, CycloneDX 1.5 SBOM (1,035 components), UFW firewall, Orca, 843 MiB full Desktop UEFI Live ISO + 10 GiB clean-install qualification — CI `44491035539` (PASS)

## Next Steps for Human Maintainer

1. Optionally test the 843 MiB UEFI Live ISO on physical Intel/AMD x86-64 UEFI hardware (see [`docs/KNOWN_GAPS.md`](KNOWN_GAPS.md)).
2. Sign `distro/out/apt-repo/Release` with a release GPG key and publish a GitHub Release with `os1-live-x86_64.iso`, `os1-sbom.cdx.json`, and `SHA256SUMS`.
3. Perform final legal/trade-dress review prior to public distribution.
