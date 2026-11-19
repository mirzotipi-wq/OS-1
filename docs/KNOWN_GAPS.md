# OS-1 Known Gaps, Limitations & Gated Items

In accordance with OS-1's honesty and engineering discipline, this file records every remaining limitation, pre-GA requirement, and item requiring physical hardware or human review outside automated cloud CI.

For the historical baseline audit of defects resolved across Phases 16–23, see [`docs/audits/PHASE16_BASELINE_AUDIT.md`](audits/PHASE16_BASELINE_AUDIT.md).

## 1. Pre-GA Software & Release Engineering Gates

- **Upstream Kernel Baseline (`7.4.0-rc3-os1`):** `OS-1 1.0-rc2` ships Linux `7.4.0-rc3-os1` from this repository's kernel source tree. Per [`docs/decisions/ADR-kernel-release-policy.md`](decisions/ADR-kernel-release-policy.md), this is strictly a **release-candidate kernel**. Before `OS-1 1.0` GA, the kernel branch must be rebased onto an official upstream final stable or LTS Linux release (zero `-rc` suffix).
- **Secure Boot:** `OS-1 1.0-rc2` targets standard x86-64 UEFI GPT boot without a Microsoft/third-party signed `shim` binary.

## 2. Hardware-Gated Items (Require Physical PCs Outside Cloud VM)

See [`docs/SUPPORTED_HARDWARE.md`](SUPPORTED_HARDWARE.md) for the full Tier 0 / Tier 1 / Unsupported matrix and bare-metal qualification checklist.

- **Physical Intel / AMD GPU Acceleration:** Cloud CI runs on QEMU/OVMF (`virtio-gpu` + Mesa `llvmpipe`). Kernel modules (`i915`, `amdgpu`, `nouveau`, `iwlwifi`/`iwlmvm`, `ath10k`/`ath11k`, `rtw88`, HDA/USB audio, `btusb`, `uvcvideo`, `hid_multitouch`, `i2c_hid_acpi`) are compiled and audited in CI (`driver-manifest.json`), but bare-metal runtime validation on real Intel/AMD laptops and desktops (GPU acceleration, Wi-Fi, Bluetooth, audio, webcam, external HDMI/DP, lid suspend/resume, battery reporting, and bare-metal update/rollback) remains **HARDWARE-GATED**.
- **Physical HiDPI & Multi-Monitor Hotplug:** Physical 4K/HiDPI scaling and external display hotplug require physical display hardware.
- **ARM64:** Explicitly deferred per ADR-0001 until an ARM64 support plan and test hardware exist.

## 3. Human Release & Legal Gates

- **Human Accessibility Review:** Automated checks verify `orca` presence, AT-SPI D-Bus reachability, and `os1-accessibility` reduced-motion/high-contrast/transparency toggles, but full assistive-technology usability requires human review.
- **Legal / Trade-Dress Review:** All OS-1 assets are independently created with zero Apple IP, and open fonts (`Noto`, `DejaVu`, `Liberation`) are used (see [`docs/LEGAL_AND_LICENSES.md`](LEGAL_AND_LICENSES.md)); a human legal review is required before declaring a stable public `1.0` GA release.
- **Production Release Key Custody:** CI uses ephemeral test signing keys (`OS1_EPHEMERAL_GPG=1`); production release signing key custody and rotation require offline human release-manager governance.

## 4. Platform Scope Realities

- OS-1 is a GNU/Linux desktop distribution. It does not execute proprietary macOS applications, Apple frameworks, iMessage, FaceTime, AirDrop, or Apple ID services.
