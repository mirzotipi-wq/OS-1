# OS-1 Supported Hardware Policy & Qualification Matrix

- **Release Target:** `OS-1 1.0-rc3` (1.0 GA Track)
- **Architecture:** `x86_64` (UEFI 64-bit, GPT)
- **Kernel Baseline:** Pinned, SHA-256-verified upstream **Linux `6.12.119` LTS** (`6.12.119-os1`, zero `-rc` suffix)
- **Kernel Policy:** See [`docs/decisions/ADR-kernel-release-policy.md`](decisions/ADR-kernel-release-policy.md)

OS-1 strictly separates **automated CI-verified virtual platforms** from **driver-compiled, bare-metal hardware-gated platforms**. Drivers being compiled into the kernel or modules never constitute bare-metal hardware certification.

---

## Tier 0 — Automated CI-Verified (PASSING)

| Platform | Firmware | Graphics | Storage / Net / Audio | Qualification Status |
|---|---|---|---|---|
| **QEMU/KVM & QEMU/TCG x86-64** | OVMF UEFI (`q35`) | `virtio-gpu` DRM/KMS + Mesa `llvmpipe` fallback | `virtio-blk`, `virtio-net`, `intel-hda` + PipeWire | **CI-VERIFIED** (Live ISO, Recovery, Clean GPT Install, LUKS2 Encrypted Install & Unlock, SDDM Graphical Login, Wayland/KWin/Plasma, AppArmor, zram, UFW/nftables, Signed APT Update, Kernel Rollback) |

---

## Tier 1 — Target Physical x86-64 UEFI Hardware (HARDWARE-GATED)

The following device classes have kernel drivers enabled in `distro/kernel/os1_x86_64.fragment` and verified compiled by `distro/tests/kernel-driver-audit.py` (`driver-manifest.json`), and Debian `non-free-firmware` packages (`firmware-linux-free`, `firmware-misc-nonfree`, `firmware-iwlwifi`, `firmware-amd-graphics`, `firmware-realtek`, `firmware-atheros`, `intel-microcode`, `amd64-microcode`) are preinstalled on the Desktop ISO. **All physical-hardware runtime behavior remains HARDWARE-GATED until verified on real machines.**

| Subsystem | Kernel Drivers & Firmware Enabled | Qualification Status |
|---|---|---|
| **Graphics (DRM/KMS)** | `i915` (Intel), `amdgpu` (AMD, incl. SI/CIK + `firmware-amd-graphics`), `nouveau` (NVIDIA open), `simpledrm` | **DRIVER-COMPILED / HARDWARE-GATED** |
| **CPU Microcode** | `intel-microcode`, `amd64-microcode` | **PREINSTALLED / HARDWARE-GATED** |
| **Wired Ethernet** | `e1000e`, `igb`, `igc` (Intel), `r8169` (Realtek + `firmware-realtek`), USB `cdc_ether`, `rndis_host`, `r8152` | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Wi-Fi (802.11)** | `iwlwifi`/`iwlmvm` (`firmware-iwlwifi`), `ath10k_pci`/`ath11k_pci` (`firmware-atheros`), `rtw88_pci` (`firmware-realtek`) | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Storage & USB** | `nvme`, `ahci`, `xhci_hcd`, `ehci_hcd`, `usb_storage`, `uas`, `dm_crypt` (LUKS2) | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Audio** | `snd_hda_intel` (Realtek/HDMI/Generic codecs), `snd_usb_audio` + PipeWire | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Bluetooth** | `btusb`, `rfcomm`, `bnep`, `hidp` | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Input & Touchpads** | `usbhid`, `hid_multitouch`, `i2c_hid_acpi`, `i2c_designware`, PS/2 Synaptics/Elantech | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Webcam** | `uvcvideo` (USB Video Class) | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Power, ACPI & TPM** | `acpi` (AC/Battery/Video), `backlight`, `intel_pstate`/`amd_pstate`, `tpm_tis`/`tpm_crb` | **DRIVER-COMPILED / HARDWARE-GATED** |

---

## Opt-In Proprietary NVIDIA Driver Guidance

OS-1 ships open-source Mesa and `nouveau` by default. Users with modern NVIDIA GPUs who require the proprietary NVIDIA driver can opt in after installation via Debian Bookworm `non-free` repositories (`nvidia-driver` + kernel headers/DKMS) or switch to `nouveau` for open-source Wayland operation.

---

## Unsupported / Out of Scope for OS-1 1.0

- **ARM64 / Apple Silicon (`aarch64`)**: Deferred per ADR-0001.
- **Legacy BIOS-only (non-UEFI) systems**: Not targeted; OS-1 targets UEFI x86-64 GPT.
- **Microsoft-signed UEFI Secure Boot `shim`**: Deferred to a post-1.0 organization EV certificate milestone; standard UEFI boot (Secure Boot disabled) is required by default, with local MOK signing supported via `os1-mok-sign`.

---

## Physical-Hardware Qualification Checklist (Required Before `OS-1 1.0` GA)

Before tagging `v1.0.0` GA (minimum: 1 Intel iGPU laptop, 1 AMD GPU desktop/laptop):

1. Boot `os1-1.0-rc3-x86_64.iso` from USB on UEFI bare metal (Secure Boot disabled, or after local MOK enrollment).
2. Run `os1-hw-diag --json` and attach the redacted report to the qualification record.
3. Verify native display resolution, refresh rate, and Wayland hardware acceleration (KWin DRM backend, not `llvmpipe`).
4. Verify wired Ethernet and Wi-Fi association + DHCP + DNS via NetworkManager.
5. Verify Bluetooth pairing, internal speakers/headphones, microphone, and UVC webcam.
6. Verify touchpad multi-finger gestures, brightness keys, battery reporting, and suspend/resume (S0ix/S3).
7. Perform clean GPT installation via `os1-install-gui` (or `os1-install --encrypt`), reboot without USB, log in via SDDM, verify active `ufw.service`, AppArmor, zram swap, Discover/Flathub, and signed APT update + kernel rollback on bare metal.
