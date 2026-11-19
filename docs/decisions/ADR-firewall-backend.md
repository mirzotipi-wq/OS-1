# ADR: OS-1 Default Firewall Backend and Kernel Configuration

- **Status:** Accepted
- **Date:** 2026-11-19
- **Phase:** Phase 17 — Firewall and Network-Security Correction

## Context

Baseline forensic inspection of `phase14-15-release-qualification.yml` (run `44493992921`) revealed that `ufw.service` failed to start on boot (`[FAILED] Failed to start ufw.service - Uncomplicated firewall.`), while the qualification script passed because it only grepped `/etc/ufw/ufw.conf` and `/etc/default/ufw`.

Root-cause analysis showed:
1. Debian 12 (`bookworm`) ships `iptables` configured via `update-alternatives` to use the `iptables-nft` backend by default.
2. `arch/x86/configs/x86_64_defconfig` disables `CONFIG_NETFILTER_ADVANCED` and does not enable `CONFIG_NF_TABLES` or `CONFIG_NFT_COMPAT`.
3. `distro/kernel/os1_x86_64.fragment` did not enable `nf_tables`, `nft_compat`, `nf_conntrack` match/target extensions, or IPv4/IPv6 logging/rejection support required by UFW.

## Decision

1. **Firewall Frontend & Backend:** OS-1 uses **UFW** (`ufw.service`) backed by the kernel **`nf_tables` (`iptables-nft`)** subsystem, with `nftables` (`nft`) installed in userspace for ruleset inspection and verification.
2. **Default Policy:** `DEFAULT_INPUT_POLICY="DROP"` (deny unsolicited incoming connections), `DEFAULT_OUTPUT_POLICY="ACCEPT"` (allow outbound connections and established/related return traffic), loopback allowed.
3. **Built-in Core Netfilter (`=y`):** Core `nf_tables`, `nft_compat`, `nf_conntrack`, IPv4/IPv6 filter/reject/log/nat, and required `xt_*` match/target primitives are compiled built-in (`=y`) in `distro/kernel/os1_x86_64.fragment`. This guarantees `ufw.service` activates reliably before `network-pre.target` in both live ISO and installed environments without early-boot module-loading races.
4. **Module Loading Enabled:** `CONFIG_MODULES=y` and `CONFIG_MODULE_UNLOAD=y` are enabled, kernel modules are built (`--with-modules`) and installed with `depmod -a`, ensuring modular drivers and optional netfilter extensions load cleanly via `modprobe`.
5. **Mandatory Behavioral Release Gate:** Configuration-text checks alone are forbidden as a release gate. Release qualification MUST verify `systemctl is-active ufw.service`, `ufw status verbose`, `nft list ruleset`, loopback, outbound traffic, and real external-peer packet blocking/allowing/removal across reboots (`distro/tests/qemu-firewall-test.py` and `distro/tests/qemu-install-test.py`).

## Consequences

- **Positive:** Incoming firewall protection is genuinely active on every live and installed boot; `ufw` and `nft` work out of the box; regressions are caught immediately by real network traffic tests.
- **Negative / Trade-offs:** Slightly larger `bzImage` (~200–300 KiB) due to built-in netfilter/nftables core, which is negligible for x86-64 desktop/VM targets and eliminates early-boot initramfs module fragility.
