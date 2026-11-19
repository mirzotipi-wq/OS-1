# OS-1 Reproducible Builds & Supply-Chain Provenance

## Deterministic Native Debian Packages

`distro/packages/build-debs.sh` normalizes file ownership (`--root-owner-group`) and file timestamps (`SOURCE_DATE_EPOCH`, defaulting to the `HEAD` commit timestamp) before invoking `dpkg-deb --build`.

### Automated Verification

Run the dual-build reproducibility check locally or via `./distro/tools/os1.sh audit`:

```bash
python3 distro/tests/reproducibility-check.py
```

This builds all 8 native OS-1 `.deb` packages twice in isolated temporary directories under the same `SOURCE_DATE_EPOCH` and fails if any `.deb` SHA-256 digest differs.

## CycloneDX 1.5 SBOM & Strict Validation

`distro/build/generate-sbom.py` generates `distro/out/release/os1-sbom.cdx.json` recording:
- `linux-os1-kernel` with real 64-hex SHA-256 of `bzImage` and `os1_x86_64.config` (read from `distro/out/kernel/provenance.json`; fails loudly if missing or invalid).
- All 8 native OS-1 `.deb` packages + versioned `linux-image-os1-*.deb` with SHA-256 digests.
- The generated UEFI Live ISO with its SHA-256 digest.
- Complete Debian userspace package inventory (`rootfs-packages.tsv`).

`distro/tests/sbom-verify-test.py` validates every release SBOM in CI and rejects any missing or `"unknown"` kernel/package/ISO hash.

## Kernel CI Cache Integrity

All 6 GitHub Actions workflows compute the kernel cache key from:
- Exact Git tree hashes of kernel source directories (`arch/x86`, `drivers`, `kernel`, `mm`, `net`, `fs`, `include`, `Makefile`, `distro/kernel`, `distro/tests/kernel-driver-audit.py`)
- Exact host compiler version (`gcc --version | head -n 1`)

This prevents stale cached kernel artifacts from ever being restored after kernel source, fragment, or toolchain changes.

## GitHub Actions Supply-Chain Hardening

- Every workflow sets explicit least-privilege `permissions:` (`contents: read` by default; `contents: write` scoped strictly to the tag-only `publish-release` job).
- All third-party GitHub Actions (`actions/checkout`, `actions/cache`, `actions/upload-artifact`) are pinned to full 40-character commit SHAs.
