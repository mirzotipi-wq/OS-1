# OS-1 GNU/Linux

OS-1 is an independent, Debian-based GNU/Linux desktop distribution built around a repository-maintained Linux kernel, `systemd`, KDE Plasma / KWin on Wayland, NetworkManager, PipeWire, UFW (`nftables`), native Debian packaging, a preflight-safe UEFI GPT installer, and signed package/kernel updates with GRUB rollback.

> **Upstream Linux Kernel Preservation:** This repository carries the full Linux kernel source tree (currently `7.4.0-rc3`, preserved with its upstream [`README`](README), [`COPYING`](COPYING), and `Documentation/`). OS-1 distribution engineering lives under [`distro/`](distro/) and [`docs/`](docs/).

---

## Honest Qualification Status (`OS-1 1.0-rc2`)

| Area | Status | Evidence / Boundary |
|---|---|---|
| **Kernel & Modules (`7.4.0-rc3-os1`)** | **RC Kernel — CI-Verified (x86-64 UEFI)** | Built-in Virtio/UEFI/Storage/Netfilter + 69 verified desktop driver symbols (`i915`, `amdgpu`, `nouveau`, `iwlwifi`, `ath10k`/`ath11k`, `rtw88`, HDA/USB audio, `btusb`, `uvcvideo`, touchpads, TPM). Must rebase onto a final upstream stable/LTS kernel before `1.0` GA ([ADR](docs/decisions/ADR-kernel-release-policy.md)). |
| **Network Security (`ufw` / `nftables`)** | **CI-Verified** | Behavioral QEMU traffic probe proves inbound DROP, explicit ALLOW, re-DROP, loopback, outbound, and reboot persistence ([`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md)). |
| **Installer (`os1-install`)** | **CI-Verified** | 13-stage preflight, stdin/fd credential handling (tested with `O'Brien $100 "safe" & clean!`), zero credential leakage, reserved-user rejection, live SDDM `[Autologin]` & `os1` user removal ([`docs/INSTALLER_SAFETY.md`](docs/INSTALLER_SAFETY.md)). |
| **Native Packaging & Signed Updates** | **CI-Verified** | 8 native `.deb` packages (`os1-release`, `os1-keyring`, `os1-branding`, `os1-shell`, `os1-firstboot`, `os1-installer`, `os1-tools`, `os1-desktop-meta`) + versioned `linux-image-os1-<krel>`, `lintian` 0-error pass, byte-for-byte `.deb` reproducibility, GPG-signed APT repo, kernel A→B upgrade & broken-kernel B→A GRUB rollback ([`docs/UPDATE_AND_ROLLBACK.md`](docs/UPDATE_AND_ROLLBACK.md)). |
| **Installed Graphical Desktop** | **CI-Verified (QEMU/OVMF)** | Clean Desktop ISO install → SDDM greeter (no autologin) → genuine graphical login as installer-created user → Wayland/KWin/Plasma/PipeWire/UFW → Light & Dark screenshots, app launches, preference preservation, reboot persistence. |
| **Physical x86-64 Hardware (Tier 1)** | **HARDWARE-GATED** | Drivers compiled and audited; bare-metal testing on real Intel/AMD UEFI laptops/desktops is required before `1.0` GA ([`docs/SUPPORTED_HARDWARE.md`](docs/SUPPORTED_HARDWARE.md)). |
| **Legal / Accessibility / Release Key Custody** | **HUMAN-GATED** | Requires human accessibility usability review, human legal/trade-dress review, and offline production GPG key custody before `1.0` GA ([`docs/LEGAL_AND_LICENSES.md`](docs/LEGAL_AND_LICENSES.md)). |

OS-1 is **not** macOS and does **not** run proprietary macOS applications or Apple services. All OS-1 artwork, wallpapers, themes, and icons are original and open-source.

---

## Quick Start (Build & Audit)

```bash
# Run full repository, workflow, installer, package, first-boot, SBOM & reproducibility audit
./distro/tools/os1.sh audit

# Build OS-1 x86_64 kernel + modules and verify 69 driver symbols
./distro/tools/os1.sh kernel --with-modules

# Build signed native .deb packages & local APT repository (ephemeral test key)
OS1_EPHEMERAL_GPG=1 ./distro/tools/os1.sh debs

# Build Full Desktop UEFI Live ISO
sudo OS1_PROFILE=desktop ./distro/tools/os1.sh rootfs
sudo ./distro/tools/os1.sh iso
```

---

## Key Documentation

- [`docs/STATUS.md`](docs/STATUS.md) — Live CI status and release scorecard
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — System architecture
- [`docs/SUPPORTED_HARDWARE.md`](docs/SUPPORTED_HARDWARE.md) — Tier 0 / Tier 1 / Unsupported hardware policy
- [`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md) — Firewall, privilege, and credential security model
- [`docs/INSTALLER_SAFETY.md`](docs/INSTALLER_SAFETY.md) — Installer preflight and safety guarantees
- [`docs/UPDATE_AND_ROLLBACK.md`](docs/UPDATE_AND_ROLLBACK.md) — Signed APT updates, versioned kernels, and GRUB rollback
- [`docs/RELEASE_PROCESS.md`](docs/RELEASE_PROCESS.md) — Release candidate vs. GA promotion gates
- [`docs/REPRODUCIBLE_BUILDS.md`](docs/REPRODUCIBLE_BUILDS.md) — Deterministic packaging and SBOM verification
- [`SECURITY.md`](SECURITY.md) — Vulnerability reporting policy
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — Contribution guidelines
