# OS-1 Known Gaps, Limitations & Gated Items

In accordance with OS-1's honesty and engineering discipline, this file records every remaining limitation and item requiring physical hardware or human review outside automated cloud CI.

For the historical baseline audit of defects resolved across Phases 16–23, see [`docs/audits/PHASE16_BASELINE_AUDIT.md`](audits/PHASE16_BASELINE_AUDIT.md).

## 1. Resolved Software Pre-GA Gates (Completed in `1.0-rc3`)

- **Upstream LTS Kernel Baseline:** Replaced `7.4.0-rc3` with pinned, SHA-256-verified **Linux `6.12.119` LTS** (`6.12.119-os1`, zero `-rc` suffix enforced by `build-kernel.sh`).
- **Desktop Security Hardening:** Enabled AppArmor LSM, balanced `sysctl` hardening, `unattended-upgrades`, and `zram` swap by default.
- **Installer & Encryption:** Added thin PyQt5 graphical wizard (`os1-install-gui`) wrapping `os1-install` and opt-in LUKS2 full-disk encryption (verified in QEMU/OVMF).
- **Hardware Firmware & App Ecosystem:** Bundled Debian `non-free-firmware` + Intel/AMD CPU microcode, plus Flatpak/Flathub + Plasma Discover.
- **Update Hosting & Signing:** Added GitHub Pages signed APT deployment, `OS1_GPG_PRIVATE_KEY` CI signing, offline signing helper (`os1-sign-release.sh`), MOK helper (`os1-mok-sign`), and 1-step GA cutover (`os1-cutover-ga.sh`).

## 2. Hardware-Gated Items (Require Physical PCs Outside Cloud VM)

See [`docs/SUPPORTED_HARDWARE.md`](SUPPORTED_HARDWARE.md) for the full Tier 0 / Tier 1 / Unsupported matrix and bare-metal qualification checklist.

- **Physical Intel / AMD GPU Acceleration & Peripherals:** Cloud CI runs on QEMU/OVMF (`virtio-gpu` + Mesa `llvmpipe`). Kernel modules (`i915`, `amdgpu`, `nouveau`, `iwlwifi`/`iwlmvm`, `ath10k`/`ath11k`, `rtw88`, HDA/USB audio, `btusb`, `uvcvideo`, `hid_multitouch`, `i2c_hid_acpi`) and `non-free-firmware` + CPU microcode are compiled/preinstalled and audited in CI, but bare-metal runtime validation on real Intel/AMD laptops and desktops remains **HARDWARE-GATED**.
- **Physical HiDPI & Multi-Monitor Hotplug:** Physical 4K/HiDPI scaling and external display hotplug require physical display hardware.
- **ARM64:** Explicitly deferred per ADR-0001 until an ARM64 support plan and test hardware exist.

## 3. Human Release & Governance Gates

- **Production Release Key Custody:** CI uses ephemeral test signing keys (`OS1_EPHEMERAL_GPG=1`) on non-tag runs; production release signing requires supplying `OS1_GPG_PRIVATE_KEY` in GitHub Secrets or running `distro/tools/os1-sign-release.sh` offline.
- **UEFI Secure Boot:** Standard UEFI boot (Secure Boot disabled) is required by default for `1.0` (local MOK enrollment supported via `os1-mok-sign`); Microsoft-signed `shim` requires an organization EV signing certificate post-1.0.
- **Human Accessibility & Legal Review:** Automated checks verify `orca`, AT-SPI D-Bus, and `os1-accessibility`; human assistive-technology usability and final trade-dress/legal sign-off remain human gates before tagging `v1.0.0`.
