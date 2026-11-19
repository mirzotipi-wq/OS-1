# OS-1 Installer Safety & Credential Architecture

`distro/installer/os1-install` implements a deterministic, preflight-complete, 13-stage UEFI/GPT installation pipeline designed so that **no destructive disk operation can run until every input, environment, target-disk, and source-artifact check has passed**.

## 1. Explicit 13-Stage Pipeline

1. **Argument Parsing:** Rejects plaintext `--password` in `argv` immediately.
2. **Environment Discovery:** Discovers running kernel release and target rootfs metadata.
3. **User-Input Validation:** Validates RFC-1123 hostname, target timezone, Linux username syntax, reserved usernames (`root`, `os1`, service accounts), `/etc/passwd` collisions, and UTF-8 password rules (rejects NUL, CR, LF, empty, or > 256 bytes).
4. **Target-Disk Validation:** Requires a whole block device (rejects partitions), writable (not read-only), >= 2 GiB, not containing active `/`, not containing `/run/live*`, and having no mounted partitions.
5. **Source-Artifact Validation:** Verifies live rootfs and kernel binary exist and are non-empty.
6. **Plan Generation (`--plan`, `--dry-run`, `--json-plan`):** Emits complete disk, partition, user, kernel, and bootloader plan without ever printing or logging the password.
7. **Final Confirmation & Pre-Apply Revalidation:** Requires `--confirm-erase-disk` (and matching `--confirm-phrase "ERASE <disk>"` if supplied), then re-checks major/minor/realpath/size immediately before partitioning.
8. **Destructive Apply:** GPT label, 256 MiB FAT32 ESP, ext4 root partition.
9. **Filesystem Population:** Copies live rootfs and installs versioned `/boot/vmlinuz-<rel>` + ESP copy.
10. **Bootloader Installation:** Generates standalone UEFI `BOOTX64.EFI` and `/EFI/os1/grubx64.efi`.
11. **User & System Configuration:** Creates administrator user, sends credentials to `chpasswd` strictly over stdin pipe (zero shell interpolation), strips live SDDM `[Autologin]`, removes live `os1` user and `/etc/os1-live-mode`, writes UUID `/etc/fstab`, regenerates `/etc/machine-id` and SSH host keys.
12. **Post-Install Validation:** Asserts EFI bootloader, kernel, `fstab`, `os-release`, non-empty `machine-id`, nonzero user UID, absence of `/etc/os1-live-mode`, and absence of `[Autologin]`.
13. **Cleanup & Final Report:** Syncs, unmounts `/mnt/os1-target` cleanly via `finally`, and emits `=== OS-1_INSTALL_COMPLETE ===`.

## 2. Automated Verification

- **Unit & Preflight Suite (`distro/tests/installer-safety-test.py`):** Verifies 7 special-character/Unicode passwords, `--password-fd`, 18+ rejected preflight cases, and bit-for-bit identical target image checksums before and after every rejected run.
- **End-to-End QEMU Install (`distro/tests/qemu-install-test.py`):** Installs with a special-character password (`O'Brien $100 "safe" & clean!`) via `--password-stdin`, verifies zero password leakage in logs, verifies live SDDM autologin removal, and boots twice detached from the ISO.
