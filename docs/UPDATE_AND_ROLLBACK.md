# OS-1 Update and Kernel Rollback Guide

## Signed Package Updates

OS-1 uses Debian's `apt` with strict per-repository GPG verification (`signed-by=/usr/share/keyrings/os1-archive-keyring.gpg`). Unsigned repositories and `trusted=yes` entries are never enabled by OS-1.

To check for and apply updates:

```bash
sudo apt-get update
sudo apt-get upgrade
```

To verify installed OS-1 package integrity against package `md5sums`:

```bash
dpkg -V os1-release os1-keyring os1-branding os1-shell os1-firstboot os1-installer os1-tools
dpkg --audit
```

## Versioned Kernel Updates

OS-1 kernels are delivered as versioned Debian packages (`linux-image-os1-<release>`). Installing a new kernel package:

1. Installs `/boot/vmlinuz-<release>`, `/boot/System.map-<release>`, `/boot/config-<release>`, and `/lib/modules/<release>`.
2. Runs `depmod -a <release>`.
3. Runs `/usr/sbin/os1-update-boot`, which atomically regenerates `/boot/grub/grub.cfg` while retaining all previously installed kernels as fallback boot entries.

## Rolling Back a Bad Kernel

If a newly installed kernel fails to boot or misbehaves:

1. Reboot the machine. At the UEFI GRUB menu (3-second timeout on both graphical and serial console), press the Down Arrow key to select the previous known-good `OS-1 (<previous-release>)` entry and press Enter.
2. Once booted into the known-good kernel, inspect installed kernels and the currently running kernel:
   ```bash
   uname -r
   dpkg -l 'linux-image-os1-*'
   ```
3. Remove the faulty kernel package:
   ```bash
   sudo apt-get purge linux-image-os1-<bad-release>
   ```
   *(Note: `prerm` intentionally refuses to remove the currently running kernel.)*
4. `postrm` automatically invokes `/usr/sbin/os1-update-boot` to remove the faulty entry from `/boot/grub/grub.cfg` and restore the known-good kernel as default.
5. Reboot to confirm the system boots cleanly into the known-good kernel by default.

## Recovering from an Interrupted Update

If power loss or interruption occurs mid-upgrade:

```bash
sudo dpkg --configure -a
sudo apt-get -f install
sudo /usr/sbin/os1-update-boot
dpkg --audit
```

## Signing Key Custody Notice

Automated CI verification tests generate ephemeral per-run GPG keys that are destroyed immediately after test execution. Official production OS-1 releases require an offline, human-custodied GPG signing key outside this repository.
