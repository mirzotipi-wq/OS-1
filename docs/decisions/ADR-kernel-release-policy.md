# ADR: OS-1 Kernel Release, Module, and Driver Baseline Policy

- **Status:** Accepted
- **Date:** 2026-11-19
- **Phase:** Phase 22 — Stable Kernel Baseline, Driver Coverage, Modules & Hardware Policy

## Context

The OS-1 repository was forked from an upstream Linux kernel tree at `7.4.0-rc3` (`VERSION = 7`, `PATCHLEVEL = 4`, `SUBLEVEL = 0`, `EXTRAVERSION = -rc3`).
Prior to Phase 22:
1. Documentation did not clearly distinguish between a **release-candidate kernel** (`-rc3`) and a **final stable/LTS kernel** required for general availability (`OS-1 1.0`).
2. `distro/kernel/os1_x86_64.fragment` focused on QEMU/virtio bring-up and omitted critical physical x86-64 desktop drivers (such as `DRM_AMDGPU`, `DRM_I915`, `DRM_NOUVEAU`, `IWLWIFI`/`IWLMVM`, `ATH10K`/`ATH11K`, `RTW88`, `SND_HDA_INTEL`, `BT_HCIBTUSB`, `I2C_HID_ACPI`, and `USB_VIDEO_CLASS`).
3. Kernel modules were not consistently compiled, audited, and packaged alongside `bzImage`.

## Decision

1. **Honest Kernel Baseline Policy (RC vs. GA):**
   - `OS-1 1.0-rc2` ships kernel `7.4.0-rc3-os1` built directly from this repository's kernel source tree. It is explicitly labeled as a **release-candidate kernel**, never as a final stable or LTS kernel.
   - **Mandatory Pre-GA Gate:** Before any `OS-1 1.0` General Availability (GA) release is tagged, the OS-1 kernel branch **MUST** be rebased onto or pinned to an official upstream **final stable** or **Long-Term Support (LTS)** Linux release (zero `-rc` suffix), with a documented security-update cadence tracking upstream `stable` point releases.
2. **Modular + Built-In x86-64 Desktop Driver Baseline:**
   - Boot-critical storage, UEFI, Virtio, filesystems, USB host/HID, ACPI power, TPM, and Netfilter/nftables remain built-in (`=y`) in `distro/kernel/os1_x86_64.fragment` for deterministic early boot and firewall activation.
   - Physical x86-64 desktop hardware drivers (Intel `i915`, AMD `amdgpu`, NVIDIA open `nouveau`, Intel/Realtek Ethernet, Intel `iwlwifi`/`iwlmvm`, Qualcomm `ath10k`/`ath11k`, Realtek `rtw88`, HD Audio & USB Audio, Bluetooth `btusb`, I2C/multitouch touchpads, UVC webcams) are enabled as loadable kernel modules (`=m`) with compressed firmware loader support (`CONFIG_FW_LOADER_COMPRESS_XZ`/`ZSTD`).
3. **Consistent Module Build, Audit & Packaging:**
   - CI kernel builds invoke `distro/kernel/build-kernel.sh --with-modules` so `/lib/modules/<krel>` is always compiled, indexed via `depmod`, and packaged into the versioned `linux-image-os1-<krel>` Debian package.
   - `distro/tests/kernel-driver-audit.py` verifies every required driver symbol in `os1_x86_64.config` (and compiled `.ko` presence when `--check-modules` is set) and emits `distro/out/kernel/driver-manifest.json`.
4. **Honest Hardware Qualification Boundary:**
   - Passing `kernel-driver-audit.py` proves that drivers are **configured and compiled**, NOT that physical bare-metal devices have been tested. Physical hardware remains explicitly **Hardware-Gated** in [`docs/SUPPORTED_HARDWARE.md`](../SUPPORTED_HARDWARE.md) until tested on real UEFI x86-64 machines.

## Consequences

- `OS-1 1.0-rc2` delivers genuine, versioned kernel + module packages with broad x86-64 hardware driver coverage and automated verification, while maintaining strict honesty about its `-rc3` kernel baseline and bare-metal hardware gate.
- Cache-miss kernel builds in CI take longer when `amdgpu`/`i915`/`nouveau` modules are compiled, but are cached per kernel source + fragment + compiler state across workflows.
