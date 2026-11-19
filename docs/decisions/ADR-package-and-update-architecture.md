# ADR-0004: OS-1 Package Ownership, Signed Updates, and Versioned Kernel Rollback

- **Status:** Accepted
- **Date:** 2026-11-19
- **Context:** Phases 19–20 (OS-1 1.0-rc2 Qualification)

## Context

Prior to Phase 19, OS-1 assembled its root filesystem by directly copying shell scripts, branding assets, and installer binaries into `/usr/local` and `/usr/share`, while building separate `.deb` packages that were never installed into the image. In addition, the kernel was copied to a fixed `/boot/vmlinuz` path with no package ownership, no previous-kernel retention, and no cryptographic APT repository signing.

This created four unacceptable reliability and security defects:
1. End-user packages diverged from the actual ISO rootfs (including root-level `/aurorae`, `/icons`, `/wallpapers` bugs).
2. OS-1 components could not be cleanly upgraded, verified with `dpkg -V`, or removed.
3. Users had no cryptographic trust anchor (`signed-by`) for OS-1 updates.
4. A bad kernel update overwrote `/boot/vmlinuz` with no previous-kernel rollback path.

## Decision

1. **Package-Owned System Assembly (Phase 19):**
   - All OS-1-owned files are delivered exclusively via native Debian packages built from a single canonical version source (`distro/VERSION`): `os1-release`, `os1-keyring`, `os1-branding`, `os1-shell`, `os1-firstboot`, `os1-installer`, `os1-tools`, `os1-desktop-meta`, and versioned `linux-image-os1-<release>` kernel packages.
   - All packaged binaries install into `/usr/bin` and `/usr/sbin` (never `/usr/local`), all branding assets install under `/usr/share`, all `/etc` files are declared in `DEBIAN/conffiles`, and every package ships `DEBIAN/md5sums` and `/usr/share/doc/<pkg>/copyright`.
   - `distro/build/build-rootfs.sh` installs these `.deb` packages via `dpkg -i` and validates `dpkg --audit` and `dpkg -V`.

2. **GPG-Signed APT Repository & Strict `signed-by` Trust (Phase 20):**
   - `distro/packages/build-debs.sh` signs APT metadata into both `InRelease` (clearsigned) and `Release.gpg` (detached) using GPG.
   - The public keyring is packaged in `os1-keyring` at `/usr/share/keyrings/os1-archive-keyring.gpg`.
   - `/etc/apt/sources.list.d/os1.list` strictly enforces `[signed-by=/usr/share/keyrings/os1-archive-keyring.gpg]`. `trusted=yes` is forbidden and rejected by automated package tests.
   - **Key Custody:** Private signing keys are NEVER committed to git. Automated CI tests generate ephemeral per-run GPG keys in temporary directories and shred them after signing. Production release signing requires an offline human-custodied GPG key outside this repository.

3. **Versioned Kernel Packages & Atomic GRUB Rollback (Phase 20):**
   - OS-1 kernels are packaged as versioned `linux-image-os1-<release>` `.deb` packages installing `/boot/vmlinuz-<release>`, `/boot/System.map-<release>`, `/boot/config-<release>`, and `/lib/modules/<release>`.
   - `BOOTX64.EFI` embeds a minimal GRUB bootstrap stub that locates `LABEL=OS1_ROOT` and loads `/boot/grub/grub.cfg` via `configfile`.
   - `/usr/sbin/os1-update-boot` (in `os1-tools`) scans all installed `/boot/vmlinuz-*` kernels, sorts them newest-first, and atomically writes `/boot/grub/grub.cfg` (temp file + `fsync` + `os.replace`) with standard and recovery entries for every installed kernel.
   - `linux-image-os1-<release>` `prerm` scripts refuse to remove the currently running kernel (`uname -r`), guaranteeing at least one known-good kernel remains bootable.

## Consequences

- Every OS-1 file on disk is traceable via `dpkg -S` and verifiable via `dpkg -V`.
- Unsigned or wrongly-signed APT repositories are rejected by `apt-get update`.
- Upgrading to a new OS-1 kernel retains the previous kernel in the GRUB menu so users can roll back immediately if a new kernel fails to boot.
