# OS-1 Session Handoff & Reproduction Guide

- **Last Updated (UTC):** 2026-11-23
- **Repository:** `https://github.com/mirzotipi-wq/OS-1.git`
- **Branch:** `master`
- **Status:** **OS-1 1.0-rc3 — All 1.0 GA Software & Engineering Requirements Implemented**

## Quick Reproduction Commands (Linux Host or CI Runner)

```bash
# 1. Audit repository, script syntax, GA cutover preflight, installer/LUKS2, packages, SBOM & reproducibility
./distro/tools/os1.sh audit

# 2. Build the pinned, SHA-256-verified Linux 6.12.119 LTS kernel + modules (80 audited symbols)
./distro/tools/os1.sh kernel --with-modules

# 3. Build signed native OS-1 .deb packages & local APT repository
OS1_EPHEMERAL_GPG=1 ./distro/tools/os1.sh debs

# 4. Build full OS-1 Wayland Desktop rootfs & bootable x86-64 UEFI Live ISO
sudo OS1_PROFILE=desktop OS1_DESKTOP_AUTOLOGIN=1 ./distro/tools/os1.sh rootfs
sudo ./distro/tools/os1.sh iso

# 5. Generate & strictly validate CycloneDX 1.5 JSON SBOM
./distro/tools/os1.sh sbom
python3 distro/tests/sbom-verify-test.py --require-iso

# 6. Run automated verification suites in QEMU / OVMF
./distro/tools/os1.sh wayland-test
./distro/tools/os1.sh iso-test
OS1_INSTALL_DISK_GB=10 OS1_INSTALL_RAM=2048M ./distro/tools/os1.sh install-test
./distro/tools/os1.sh luks-install-test
./distro/tools/os1.sh update-rollback-test
OS1_INSTALL_DISK_GB=10 OS1_DESKTOP_RAM=2560M ./distro/tools/os1.sh installed-desktop-test
```

## Maintainer Steps for Final `v1.0.0` GA Promotion

1. **Bare-Metal Tier 1 Testing:** Flash `os1-1.0-rc3-x86_64.iso` to USB and complete the Intel + AMD physical UEFI checklist in [`docs/SUPPORTED_HARDWARE.md`](SUPPORTED_HARDWARE.md).
2. **Production GPG Key Setup:** Add `OS1_GPG_PRIVATE_KEY` (and optional `OS1_GPG_PASSPHRASE`) to GitHub Repository Secrets (or sign release bundles offline with `./distro/tools/os1-sign-release.sh`).
3. **Enable GitHub Pages:** Set repository Pages source to **GitHub Actions** so `publish-apt-pages` deploys `https://mirzotipi-wq.github.io/OS-1/apt` on tag push.
4. **1-Step GA Cutover:** Run `./distro/tools/os1-cutover-ga.sh`, commit `distro/VERSION`, and push signed tag `v1.0.0`.
