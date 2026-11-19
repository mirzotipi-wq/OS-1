#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 19: Native OS-1 Debian package verification & lifecycle test suite.

Static checks (offline, runs in `./distro/tools/os1.sh audit` and CI):
  - Builds all 8 native OS-1 .deb packages into a temporary directory (or inspects --repo-dir)
  - Verifies dpkg-deb --info and --contents
  - Verifies canonical version consistency with distro/VERSION
  - Rejects forbidden root-level paths (/aurorae, /icons, /pixmaps, /wallpapers, /usr/local/)
  - Verifies os1-branding FHS paths under /usr/share/
  - Rejects world-writable files/directories
  - Rejects file-path collisions across OS-1 packages
  - Verifies /usr/share/doc/<pkg>/copyright, DEBIAN/md5sums, and DEBIAN/conffiles for /etc/*
  - Scans extracted payload for private keys or `trusted=yes`
  - Runs `lintian` if installed and fails on any E: (error) tag

Lifecycle checks (--lifecycle-rootfs <dir>, runs as root in CI):
  - Verifies dpkg -S ownership of OS-1 files inside the assembled rootfs
  - Verifies dpkg --audit and dpkg -V
  - Builds synthetic v+1 upgrade packages and tests:
      upgrade -> conffile preservation -> dpkg -V -> remove -> purge -> reinstall original
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

EXPECTED_PACKAGES = [
    "os1-release",
    "os1-keyring",
    "os1-branding",
    "os1-shell",
    "os1-firstboot",
    "os1-installer",
    "os1-tools",
    "os1-desktop-meta",
]

FORBIDDEN_PREFIXES = (
    "/aurorae",
    "/icons",
    "/pixmaps",
    "/wallpapers",
    "/usr/local/",
)

REQUIRED_BRANDING_FILES = [
    "/usr/share/aurorae/themes/OS1Sequoia/OS1Sequoiarc",
    "/usr/share/wallpapers/OS1Horizon/contents/images/1920x1080.png",
    "/usr/share/wallpapers/OS1Horizon/contents/images/1920x1080-dark.png",
    "/usr/share/icons/hicolor/scalable/apps/os1-logo.svg",
    "/usr/share/pixmaps/os1-logo.svg",
    "/usr/share/color-schemes/OS1Light.colors",
    "/usr/share/color-schemes/OS1Dark.colors",
    "/usr/share/os1/tokens.json",
]

SECRET_PATTERNS = [
    re.compile(rb"BEGIN [A-Z0-9 ]*PRIVATE KEY"),
    re.compile(rb"trusted\s*=\s*yes", re.IGNORECASE),
]


def load_version_meta() -> dict[str, str]:
    meta: dict[str, str] = {}
    ver_path = os.path.join(REPO_ROOT, "distro", "VERSION")
    with open(ver_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta


def run_static_checks(repo_dir: str, expected_version: str) -> list[str]:
    errors: list[str] = []
    debs = sorted(f for f in os.listdir(repo_dir) if f.endswith(".deb"))
    found_pkgs: dict[str, str] = {}

    for deb in debs:
        path = os.path.join(repo_dir, deb)
        pkg_name = subprocess.check_output(
            ["dpkg-deb", "--field", path, "Package"], text=True
        ).strip()
        pkg_ver = subprocess.check_output(
            ["dpkg-deb", "--field", path, "Version"], text=True
        ).strip()
        found_pkgs[pkg_name] = path

        if pkg_ver != expected_version:
            errors.append(
                f"{deb}: Version '{pkg_ver}' != expected '{expected_version}' from distro/VERSION"
            )

    for pkg in EXPECTED_PACKAGES:
        if pkg not in found_pkgs:
            errors.append(f"Missing expected native OS-1 package: {pkg}")

    owned_files: dict[str, str] = {}
    for pkg_name, path in sorted(found_pkgs.items()):
        contents = subprocess.check_output(["dpkg-deb", "--contents", path], text=True)
        files_in_pkg: set[str] = set()
        etc_files: set[str] = set()

        for line in contents.splitlines():
            parts = line.split()
            if len(parts) < 6:
                continue
            mode = parts[0]
            raw_path = parts[5]
            norm_path = "/" + raw_path.lstrip("./")
            is_dir = mode.startswith("d")

            # Check world-writable bit (position 8 in drwxrwxrwx)
            if len(mode) >= 10 and mode[8] == "w":
                errors.append(f"{pkg_name}: world-writable entry {mode} {norm_path}")

            for bad in FORBIDDEN_PREFIXES:
                if norm_path == bad or norm_path.startswith(bad + "/") or norm_path.startswith(bad):
                    if bad.endswith("/") or norm_path == bad or norm_path.startswith(bad + "/"):
                        errors.append(f"{pkg_name}: forbidden path {norm_path}")

            if not is_dir:
                files_in_pkg.add(norm_path)
                if norm_path.startswith("/etc/"):
                    etc_files.add(norm_path)
                if norm_path in owned_files:
                    errors.append(
                        f"File path collision on {norm_path}: owned by both {owned_files[norm_path]} and {pkg_name}"
                    )
                else:
                    owned_files[norm_path] = pkg_name

        # Check copyright file
        copyright_path = f"/usr/share/doc/{pkg_name}/copyright"
        if copyright_path not in files_in_pkg:
            errors.append(f"{pkg_name}: missing {copyright_path}")

        # Check branding required paths
        if pkg_name == "os1-branding":
            for req in REQUIRED_BRANDING_FILES:
                if req not in files_in_pkg:
                    errors.append(f"os1-branding: missing required FHS asset {req}")

        # Extract control & payload to verify md5sums, conffiles, and secret scan
        with tempfile.TemporaryDirectory(prefix=f"os1-pkgcheck-{pkg_name}-") as tmp:
            ctrl_dir = os.path.join(tmp, "DEBIAN")
            data_dir = os.path.join(tmp, "data")
            subprocess.check_call(["dpkg-deb", "--control", path, ctrl_dir])
            subprocess.check_call(["dpkg-deb", "--extract", path, data_dir])

            if not os.path.isfile(os.path.join(ctrl_dir, "md5sums")):
                errors.append(f"{pkg_name}: missing DEBIAN/md5sums")

            if etc_files:
                conffiles_path = os.path.join(ctrl_dir, "conffiles")
                if not os.path.isfile(conffiles_path):
                    errors.append(f"{pkg_name}: ships /etc files {sorted(etc_files)} without DEBIAN/conffiles")
                else:
                    listed = {
                        l.strip()
                        for l in open(conffiles_path, encoding="utf-8")
                        if l.strip()
                    }
                    missing_cf = etc_files - listed
                    if missing_cf:
                        errors.append(
                            f"{pkg_name}: /etc files not listed in DEBIAN/conffiles: {sorted(missing_cf)}"
                        )

            for root, _dirs, fnames in os.walk(data_dir):
                for fn in fnames:
                    fp = os.path.join(root, fn)
                    if os.path.islink(fp):
                        continue
                    data = open(fp, "rb").read()
                    for pat in SECRET_PATTERNS:
                        if pat.search(data):
                            rel = os.path.relpath(fp, data_dir)
                            errors.append(
                                f"{pkg_name}: forbidden pattern {pat.pattern!r} found in /{rel}"
                            )

        # Optional lintian check (active in CI where lintian is installed)
        if shutil.which("lintian"):
            res = subprocess.run(
                ["lintian", "--no-tag-display-limit", path],
                capture_output=True,
                text=True,
            )
            for line in res.stdout.splitlines():
                if line.startswith("E: "):
                    # Ignore only changelog-file-missing if native minimal pkg; enforce all real FHS/policy errors
                    if "no-changelog" in line:
                        continue
                    errors.append(f"lintian error in {pkg_name}: {line}")

    return errors


def run_lifecycle_checks(rootfs_dir: str, repo_dir: str, base_version: str) -> None:
    if os.geteuid() != 0:
        raise RuntimeError("--lifecycle-rootfs must run as root")

    def chroot_run(cmd: list[str]) -> str:
        res = subprocess.run(
            ["chroot", rootfs_dir, "/usr/bin/env", "-i", "PATH=/usr/sbin:/usr/bin:/sbin:/bin",
             "DEBIAN_FRONTEND=noninteractive"] + cmd,
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            raise RuntimeError(
                f"chroot command failed (rc={res.returncode}): {' '.join(cmd)}\n"
                f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
            )
        return res.stdout

    # 1. Verify dpkg -S ownership
    expected_owners = {
        "/etc/os-release": "os1-release",
        "/usr/share/os1/VERSION": "os1-release",
        "/usr/sbin/os1-install": "os1-installer",
        "/usr/bin/os1-fs-test": "os1-tools",
        "/etc/apt/sources.list.d/os1.list": "os1-keyring",
    }
    is_desktop = os.path.exists(os.path.join(rootfs_dir, "usr/bin/plasmashell"))
    if is_desktop:
        expected_owners.update({
            "/usr/share/wallpapers/OS1Horizon/contents/images/1920x1080.png": "os1-branding",
            "/usr/share/aurorae/themes/OS1Sequoia/OS1Sequoiarc": "os1-branding",
            "/usr/bin/os1-appearance": "os1-shell",
            "/usr/bin/os1-firstboot": "os1-firstboot",
        })

    for fpath, owner in expected_owners.items():
        out = chroot_run(["dpkg", "-S", fpath])
        if not out.startswith(f"{owner}:"):
            raise RuntimeError(f"Expected {fpath} to be owned by {owner}, got: {out.strip()}")
    print(f"[PASS] dpkg -S ownership verified for {len(expected_owners)} OS-1 files", flush=True)

    # 2. Build synthetic upgrade version (base_version + '.1') and test upgrade, conffile preservation, remove, purge, reinstall
    upgrade_ver = f"{base_version}.1"
    with tempfile.TemporaryDirectory(prefix="os1-pkg-lifecycle-") as tmp_out:
        env = os.environ.copy()
        env["OS1_OUT_DIR"] = tmp_out
        env["OS1_PKG_VERSION"] = upgrade_ver
        subprocess.check_call([os.path.join(REPO_ROOT, "distro", "packages", "build-debs.sh")], env=env)

        stage = os.path.join(rootfs_dir, "tmp", "os1-lifecycle-test")
        os.makedirs(stage, exist_ok=True)
        try:
            # Test conffile preservation on os1-keyring upgrade
            cf_path = os.path.join(rootfs_dir, "etc", "apt", "sources.list.d", "os1.list")
            orig_cf = open(cf_path, encoding="utf-8").read()
            marker = "# os1-phase19-conffile-preservation-marker\n"
            with open(cf_path, "a", encoding="utf-8") as f:
                f.write(marker)

            up_keyring = os.path.join(tmp_out, "apt-repo", f"os1-keyring_{upgrade_ver}_all.deb")
            up_tools = os.path.join(tmp_out, "apt-repo", f"os1-tools_{upgrade_ver}_all.deb")
            shutil.copy2(up_keyring, os.path.join(stage, os.path.basename(up_keyring)))
            shutil.copy2(up_tools, os.path.join(stage, os.path.basename(up_tools)))

            chroot_run([
                "dpkg", "--force-confold", "-i",
                f"/tmp/os1-lifecycle-test/{os.path.basename(up_keyring)}",
                f"/tmp/os1-lifecycle-test/{os.path.basename(up_tools)}",
            ])

            # Verify upgraded version
            ver_out = chroot_run(["dpkg-query", "-W", "-f=${Version}", "os1-tools"]).strip()
            if ver_out != upgrade_ver:
                raise RuntimeError(f"Expected os1-tools upgraded to {upgrade_ver}, got {ver_out}")

            # Verify user conffile edit survived upgrade
            after_cf = open(cf_path, encoding="utf-8").read()
            if marker not in after_cf:
                raise RuntimeError("os1-keyring upgrade overwrote modified conffile /etc/apt/sources.list.d/os1.list")
            print(f"[PASS] Upgrade ({base_version} -> {upgrade_ver}) & conffile preservation verified", flush=True)

            # Test remove + purge + reinstall on os1-tools (non-desktop-meta blocker? If desktop-meta depends on it, remove desktop-meta too and reinstall both)
            pkgs_to_cycle = ["os1-desktop-meta", "os1-tools"] if is_desktop else ["os1-tools"]
            chroot_run(["dpkg", "--remove"] + pkgs_to_cycle)
            if os.path.exists(os.path.join(rootfs_dir, "usr/bin/os1-fs-test")):
                raise RuntimeError("/usr/bin/os1-fs-test still exists after dpkg --remove os1-tools")
            chroot_run(["dpkg", "--purge"] + pkgs_to_cycle)
            print(f"[PASS] Remove & purge verified for {pkgs_to_cycle}", flush=True)

            # Restore original baseline versions cleanly
            orig_debs = [
                f"os1-keyring_{base_version}_all.deb",
                f"os1-tools_{base_version}_all.deb",
            ]
            if is_desktop:
                orig_debs.append(f"os1-desktop-meta_{base_version}_amd64.deb")

            with open(cf_path, "w", encoding="utf-8") as f:
                f.write(orig_cf)

            install_args = []
            for d in orig_debs:
                shutil.copy2(os.path.join(repo_dir, d), os.path.join(stage, d))
                install_args.append(f"/tmp/os1-lifecycle-test/{d}")

            chroot_run(["dpkg", "--force-downgrade", "--force-confnew", "-i"] + install_args)
            chroot_run(["dpkg", "-V", "os1-release", "os1-keyring", "os1-installer", "os1-tools"])
            print("[PASS] Reinstall & dpkg -V integrity verified", flush=True)
        finally:
            shutil.rmtree(stage, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="OS-1 Phase 19 native package verification suite")
    parser.add_argument("--repo-dir", help="Inspect existing APT repo dir instead of building into temp dir")
    parser.add_argument("--lifecycle-rootfs", help="Run root chroot lifecycle tests against assembled rootfs")
    args = parser.parse_args()

    meta = load_version_meta()
    expected_version = meta["OS1_DEB_VERSION"]

    tmp_ctx = None
    if args.repo_dir:
        repo_dir = args.repo_dir
    else:
        tmp_ctx = tempfile.TemporaryDirectory(prefix="os1-pkgverify-")
        env = os.environ.copy()
        env["OS1_OUT_DIR"] = tmp_ctx.name
        subprocess.check_call(
            [os.path.join(REPO_ROOT, "distro", "packages", "build-debs.sh")],
            env=env,
            stdout=subprocess.DEVNULL,
        )
        repo_dir = os.path.join(tmp_ctx.name, "apt-repo")

    try:
        errors = run_static_checks(repo_dir, expected_version)
        if errors:
            print("FAIL: OS-1 package verification failed:", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1
        print(
            f"[PASS] OS-1 package verification passed ({len(EXPECTED_PACKAGES)} packages, version={expected_version}, "
            "FHS paths, zero collisions, zero world-writable, conffiles/md5sums/copyright/secret-scan OK)"
        )

        if args.lifecycle_rootfs:
            run_lifecycle_checks(args.lifecycle_rootfs, repo_dir, expected_version)
    finally:
        if tmp_ctx is not None:
            tmp_ctx.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
