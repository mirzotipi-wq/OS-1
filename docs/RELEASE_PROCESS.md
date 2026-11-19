# OS-1 Release Process & Qualification Gates

## Canonical Version Source

All OS-1 artifacts read their release version from [`distro/VERSION`](../distro/VERSION):
- `OS1_VERSION` (e.g., `1.0-rc2`)
- `OS1_DEB_VERSION` (e.g., `1.0.0~rc2-1`)

## Release Candidate (`1.0-rc2`) Automated Gates

Every release-candidate tag (`v1.0.0-rc2`) **MUST** pass all 6 mandatory GitHub Actions workflows on the exact tagged commit:
1. `phase1-kernel-boot.yml` — Kernel + modules build, `T22-DRIVERS` (69 symbols + `.ko` check), QEMU serial boot.
2. `phase2-userspace.yml` — Debian 12 userspace, native `.deb` assembly, NetworkManager, APT, 2-boot persistence, `T17-FIREWALL` behavioral traffic drop/allow/re-drop/reboot persistence.
3. `phase3-live-iso.yml` — Minimal UEFI Live ISO + Recovery mode in OVMF.
4. `phase4-installer.yml` — `T4-INSTALL` (special-char password, live user/autologin removal, 2 reboots) + `T20-UPDATE-ROLLBACK` (unsigned rejection, signed upgrade, kernel A→B upgrade, bad-kernel B→A GRUB rollback).
5. `phase5-wayland-desktop.yml` — KDE Plasma/KWin Wayland session, Light/Dark screenshots, notifications, apps, audio, accessibility, reboot persistence.
6. `phase14-15-release-qualification.yml` — Signed `.deb`s + versioned kernel `.deb`, `lintian` 0 errors, `T19-PKG` lifecycle, Desktop UEFI Live ISO, `T17-FIREWALL`, CycloneDX 1.5 SBOM + strict `sbom-verify-test.py`, `T15-ISO-BOOT`, `T21-INSTALLED-GUI` (genuine SDDM graphical login as installer-created user `alice`), and tag-triggered GitHub Release asset publication.

## Durable GitHub Release Assets

On pushing a `v*` tag, `phase14-15-release-qualification.yml` publishes the exact tested artifacts to the GitHub Release:
- `os1-<version>-x86_64.iso`
- All 8 native OS-1 `.deb` packages + `linux-image-os1-*.deb`
- Signed APT repository metadata (`InRelease`, `Release`, `Release.gpg`, `Packages`, `Packages.gz`, `os1-archive-keyring.gpg`)
- `SHA256SUMS`, `os1-sbom.cdx.json`, `provenance.json`, `driver-manifest.json`

## Mandatory Human & Hardware Gates Before `OS-1 1.0` GA

A release candidate **MUST NOT** be promoted to `OS-1 1.0` General Availability until:
1. **Kernel Baseline:** Kernel is rebased onto an upstream final stable or LTS Linux release (zero `-rc` suffix).
2. **Physical Hardware (Tier 1):** Bare-metal UEFI qualification checklist in [`docs/SUPPORTED_HARDWARE.md`](SUPPORTED_HARDWARE.md) passes on at least one Intel and one AMD physical x86-64 machine.
3. **Production Signing Key Custody:** Release APT metadata and checksums are signed with an offline-held production release GPG key (not an ephemeral CI key).
4. **Human Accessibility & Legal Review:** Sign-off on screen reader/keyboard usability and open-source asset/trade-dress compliance.
