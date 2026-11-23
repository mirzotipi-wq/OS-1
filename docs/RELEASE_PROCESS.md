# OS-1 Release Process & Qualification Gates

## Canonical Version & Kernel Sources

- **Release Version:** [`distro/VERSION`](../distro/VERSION) (`OS1_VERSION`, `OS1_DEB_VERSION`, `OS1_APT_PAGES_URL`)
- **Pinned LTS Kernel:** [`distro/kernel/KERNEL_LTS.env`](../distro/kernel/KERNEL_LTS.env) (`OS1_KERNEL_VERSION`, `OS1_KERNEL_CHANNEL`, `OS1_KERNEL_URL`, `OS1_KERNEL_SHA256`)

## Automated CI Qualification Gates

Every release tag (`v1.0.0-rc3`, `v1.0.0`) **MUST** pass all 6 mandatory GitHub Actions workflows on the exact tagged commit:
1. `phase1-kernel-boot.yml` — Pinned SHA-256-verified Linux LTS kernel + modules build (zero `-rc` enforced), `T22-DRIVERS` (80 verified symbols + `.ko` check), QEMU serial boot.
2. `phase2-userspace.yml` — Debian 12 userspace, native `.deb` assembly, NetworkManager, APT, 2-boot persistence, `T17-FIREWALL` behavioral traffic drop/allow/re-drop/reboot persistence.
3. `phase3-live-iso.yml` — Minimal UEFI Live ISO + Recovery mode in OVMF.
4. `phase4-installer.yml` — `T4-INSTALL` (special-char password, live user/autologin removal, AppArmor/sysctl/zram verification, 2 reboots), `T25-LUKS` (opt-in LUKS2 full-disk encryption install, initramfs passphrase unlock, encrypted root boot), and `T20-UPDATE-ROLLBACK` (unsigned rejection, signed upgrade, kernel A→B upgrade, bad-kernel B→A GRUB rollback).
5. `phase5-wayland-desktop.yml` — KDE Plasma/KWin Wayland session, Light/Dark screenshots, notifications, apps, audio, accessibility, reboot persistence.
6. `phase14-15-release-qualification.yml` — Signed `.deb`s + versioned kernel `.deb`, `lintian` 0 errors, `T19-PKG` lifecycle, Desktop UEFI Live ISO (with `non-free-firmware`, microcode, Flatpak/Flathub, Discover, `os1-install-gui`), `T17-FIREWALL`, CycloneDX 1.5 SBOM + strict `sbom-verify-test.py`, `T15-ISO-BOOT`, `T21-INSTALLED-GUI` (genuine SDDM graphical login as installer-created user `alice`), GitHub Release publication, and GitHub Pages signed APT repository deployment.

## Durable Release & Hosted APT Artifacts

On pushing a `v*` tag, `phase14-15-release-qualification.yml` publishes:
1. **GitHub Release Assets:** `os1-<version>-x86_64.iso`, all 8 native OS-1 `.deb` packages + `linux-image-os1-*.deb`, signed APT metadata (`InRelease`, `Release`, `Release.gpg`, `Packages`, `Packages.gz`, `os1-archive-keyring.gpg`), `SHA256SUMS`, `os1-sbom.cdx.json`, `provenance.json`, `driver-manifest.json`.
2. **GitHub Pages Signed APT Repository (`https://mirzotipi-wq.github.io/OS-1/apt`):** Deployed via `publish-apt-pages` so installed OS-1 systems receive signed package and LTS kernel updates over HTTPS.

## Production GPG Key Custody & 1-Step GA Cutover

- **CI Production Signing:** Configure `OS1_GPG_PRIVATE_KEY` (and optional `OS1_GPG_PASSPHRASE`) in GitHub Repository Secrets before pushing a GA tag.
- **Air-Gapped Offline Signing:** Download the qualified release bundle and run `./distro/tools/os1-sign-release.sh <bundle-dir> <gpg-key-id>` on an offline signing workstation to re-sign `InRelease`, `Release.gpg`, and `SHA256SUMS.asc`.
- **1-Step GA Cutover:** Once bare-metal Tier 1 hardware testing and human legal/accessibility sign-off are complete, run `./distro/tools/os1-cutover-ga.sh` to verify all software gates, bump `distro/VERSION` to `1.0` (`1.0.0-1`), run `os1.sh audit`, and tag `v1.0.0`.
