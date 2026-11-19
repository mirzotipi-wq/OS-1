# OS-1 Session Handoff

## 1. Current Repository & Branch State

- **Repository:** `https://github.com/mirzotipi-wq/OS-1.git`
- **Branch:** `os1/phase0-1-foundation-kernel-boot` (branched from `master` at `666539eecdf4db623f5e3c3e55cf9f2dfad24aa4`)
- **Kernel Source:** Upstream Linux `7.4.0-rc3` (`Makefile`: `VERSION=7`, `PATCHLEVEL=4`, `SUBLEVEL=0`, `EXTRAVERSION=-rc3`), unmodified.
- **Working Tree:** Ephemeral build artifacts live exclusively in `distro/out/` (ignored by `distro/.gitignore`).

## 2. Environment & Toolchain Notes

- **Local Sandbox VM:** Debian 12 x86-64, 2 vCPU, 7.8 GiB RAM, 18 GiB free in `/home/antigravity`, non-root (`no sudo/apt`). Has `gcc 12.2.0`, `make 4.3`, `flex`, `bison`, `libssl-dev`, `python3`, `dpkg-deb`, `fakeroot`. Missing `bc`, `libelf-dev`, `cpio`, `kmod`, `qemu-system-x86_64`, `/dev/kvm`.
- **GitHub Actions CI (`ubuntu-latest`):** Enabled on `mirzotipi-wq/OS-1`. Runs full Phase 1 kernel compilation (`bzImage`), BusyBox initramfs build, and QEMU serial boot proof via `.github/workflows/phase1-kernel-boot.yml`.

## 3. Exact Commands to Reproduce / Resume

```bash
# 1. Inspect repo state & syntax
./distro/tools/os1.sh audit

# 2. Validate merged OS-1 x86_64 Kconfig (works even in minimal VMs)
./distro/tools/os1.sh kernel --config-only

# 3. Full Phase 1 pipeline (requires bc, libelf-dev, libssl-dev, qemu-system-x86, busybox-static)
./distro/tools/os1.sh kernel
./distro/tools/os1.sh initramfs
./distro/tools/os1.sh boot-test

# 4. Clean ephemeral build outputs
./distro/tools/os1.sh clean
```

## 4. Immediate Next Task

1. Verify GitHub Actions workflow `.github/workflows/phase1-kernel-boot.yml` passes end-to-end (`T1-KBUILD` + `T1-QEMU-BOOT`) and record the verified run URL, `uname -a`, and `bzImage` SHA-256 in `docs/STATUS.md`.
2. **Phase 2 Unblocker:** Implement `distro/build/build-rootfs.sh` (pinned Debian stable rootfs via `mmdebstrap`/`debootstrap` with `systemd`, `NetworkManager`, `PipeWire`, non-root `os1` user, `sudo`, persistent ext4 disk image) and `distro/tests/qemu-userspace-test.sh` (automated serial login, networking check, APT package install, file creation, reboot, and persistence verification using the OS-1 kernel).
