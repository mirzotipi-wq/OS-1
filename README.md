# OS-1 GNU/Linux

OS-1 is an independent, Debian 12 (Bookworm)-based GNU/Linux desktop distribution built around a pinned, SHA-256-verified upstream **Linux `6.12.119` LTS** kernel, `systemd`, KDE Plasma / KWin on Wayland, NetworkManager, PipeWire, AppArmor LSM, UFW (`nftables`), `zram` swap, `unattended-upgrades`, Flatpak/Flathub + Plasma Discover, native Debian packaging, a preflight-safe UEFI GPT CLI & PyQt5 graphical installer with opt-in LUKS2 full-disk encryption, and GPG-signed package/kernel updates with GRUB rollback.

> **Upstream Linux Kernel Preservation:** This repository preserves its upstream Linux kernel tree ([`README`](README), [`COPYING`](COPYING), `Documentation/`). OS-1 distribution engineering lives under [`distro/`](distro/) and [`docs/`](docs/), and builds production kernels from the pinned, SHA-256-verified upstream LTS manifest in [`distro/kernel/KERNEL_LTS.env`](distro/kernel/KERNEL_LTS.env).

---

## Honest Qualification Status (`OS-1 1.0-rc3` — 1.0 GA Engineering Complete)

| Area | Status | Evidence / Boundary |
|---|---|---|
| **Kernel & Modules (`6.12.119-os1` LTS)** | **CI-Verified (x86-64 UEFI)** | Pinned, SHA-256-verified upstream Linux `6.12.119` LTS (zero `-rc` enforced). Built-in Virtio/UEFI/Storage/Netfilter/AppArmor/Yama/dm-crypt/zram + 80 verified desktop driver & security symbols (`i915`, `amdgpu`, `nouveau`, `iwlwifi`, `ath10k`/`ath11k`, `rtw88`, HDA/USB audio, `btusb`, `uvcvideo`, touchpads, TPM) ([ADR](docs/decisions/ADR-kernel-release-policy.md)). |
| **Security Hardening (AppArmor / UFW / Sysctl)** | **CI-Verified** | AppArmor LSM enabled, balanced `sysctl` hardening (`90-os1-hardening.conf`), `unattended-upgrades`, `zram` swap, and behavioral QEMU UFW/`nftables` traffic probe proving inbound DROP, explicit ALLOW, re-DROP, loopback, outbound, and reboot persistence ([`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md)). |
| **Installer (`os1-install` + `os1-install-gui`)** | **CI-Verified** | 13-stage preflight, stdin/fd credential handling (tested with `O'Brien $100 "safe" & clean!`), PyQt5 graphical wizard wrapping `os1-install`, opt-in **LUKS2 full-disk encryption** (QEMU/OVMF encrypted install + initramfs unlock verified), zero credential leakage, live SDDM `[Autologin]` & `os1` user removal ([`docs/INSTALLER_SAFETY.md`](docs/INSTALLER_SAFETY.md)). |
| **Native Packaging, Hosted APT & Updates** | **CI-Verified** | 8 native `.deb` packages (`os1-release`, `os1-keyring`, `os1-branding`, `os1-shell`, `os1-firstboot`, `os1-installer`, `os1-tools`, `os1-desktop-meta`) + versioned `linux-image-os1-<krel>`, `lintian` 0-error pass, byte-for-byte `.deb` reproducibility, GPG-signed APT repo + GitHub Pages deployment, kernel A→B upgrade & broken-kernel B→A GRUB rollback ([`docs/UPDATE_AND_ROLLBACK.md`](docs/UPDATE_AND_ROLLBACK.md)). |
| **Installed Graphical Desktop & Apps** | **CI-Verified (QEMU/OVMF)** | Clean Desktop ISO install (with `non-free-firmware`, CPU microcode, Flatpak/Flathub, Plasma Discover, `os1-mok-sign`) → SDDM greeter (no autologin) → genuine graphical login as installer-created user → Wayland/KWin/Plasma/PipeWire/UFW/AppArmor → Light & Dark screenshots, app launches, preference preservation, reboot persistence. |
| **Physical x86-64 Hardware (Tier 1)** | **HARDWARE-GATED** | Drivers compiled and `non-free-firmware` + CPU microcode preinstalled; bare-metal testing on real Intel/AMD UEFI laptops/desktops is required before running `os1-cutover-ga.sh` for `v1.0.0` GA ([`docs/SUPPORTED_HARDWARE.md`](docs/SUPPORTED_HARDWARE.md)). |
| **Legal / Accessibility / Release Key Custody** | **HUMAN-GATED** | Requires human accessibility usability review, human legal/trade-dress review, and production GPG key (`OS1_GPG_PRIVATE_KEY` secret or offline `os1-sign-release.sh`) before `v1.0.0` GA ([`docs/LEGAL_AND_LICENSES.md`](docs/LEGAL_AND_LICENSES.md)). |

OS-1 is **not** macOS and does **not** run proprietary macOS applications or Apple services. All OS-1 artwork, wallpapers, themes, and icons are original and open-source.

---

## Quick Start (Build, Audit & GA Cutover)

```bash
# Run full repository, workflow, installer/LUKS2, package, first-boot, SBOM & reproducibility audit
./distro/tools/os1.sh audit

# Build pinned Linux 6.12.119 LTS x86_64 kernel + modules and verify 80 driver & security symbols
./distro/tools/os1.sh kernel --with-modules

# Build signed native .deb packages & local APT repository (ephemeral test key)
OS1_EPHEMERAL_GPG=1 ./distro/tools/os1.sh debs

# Build Full Desktop UEFI Live ISO (includes non-free-firmware, microcode, Flatpak, Discover, os1-install-gui)
sudo OS1_PROFILE=desktop ./distro/tools/os1.sh rootfs
sudo ./distro/tools/os1.sh iso

# After bare-metal Tier 1 sign-off & GPG key setup, promote to 1.0 GA in 1 step:
./distro/tools/os1-cutover-ga.sh
```

---

## Key Documentation

- [`docs/STATUS.md`](docs/STATUS.md) — Live CI status and release scorecard
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — System architecture
- [`docs/SUPPORTED_HARDWARE.md`](docs/SUPPORTED_HARDWARE.md) — Tier 0 / Tier 1 / Unsupported hardware policy & opt-in NVIDIA guidance
- [`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md) — AppArmor, UFW, sysctl hardening, LUKS2, unattended-upgrades & MOK Secure Boot
- [`docs/INSTALLER_SAFETY.md`](docs/INSTALLER_SAFETY.md) — Installer preflight and safety guarantees
- [`docs/UPDATE_AND_ROLLBACK.md`](docs/UPDATE_AND_ROLLBACK.md) — Signed APT updates, versioned kernels, and GRUB rollback
- [`docs/RELEASE_PROCESS.md`](docs/RELEASE_PROCESS.md) — Release candidate vs. GA promotion gates, GitHub Pages APT repo & offline signing
- [`docs/REPRODUCIBLE_BUILDS.md`](docs/REPRODUCIBLE_BUILDS.md) — Deterministic packaging and SBOM verification
- [`SECURITY.md`](SECURITY.md) — Vulnerability reporting policy
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — Contribution guidelines
