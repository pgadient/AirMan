# Releasing AirMan

1. Raise the version: `python build.py --bump` counts the last number up
   (0.1.16 -> 0.1.17) and builds; for bigger steps edit `__version__` in
   `airman/__init__.py` by hand.
2. Test it locally:

   ```bash
   python -m pip install --require-hashes -r requirements-build.txt
   python -m unittest discover -s tests
   ```

3. Commit, then tag the commit with the same number and push both:

   ```bash
   git tag v0.1.17
   git push origin main v0.1.17
   ```

The [Release workflow](.github/workflows/release.yml) builds AirMan on GitHub
for every platform, runs the tests there and publishes the release with these
files:

| File | For |
|---|---|
| `AirMan-windows-x64.exe` | Windows 10/11 on Intel/AMD |
| `AirMan-windows-arm64.exe` | Windows 11 on ARM |
| `AirMan-macos-arm64.zip` | macOS on Apple silicon (M1 and newer) |
| `AirMan-macos-x64.zip` | macOS on Intel |
| `AirMan-linux-x64.tar.gz` | Linux on Intel/AMD (glibc 2.35+) |
| `AirMan-linux-arm64.tar.gz` | Linux on ARM, e.g. Raspberry Pi 4/5 with a 64-bit OS |
| `SHA256SUMS.txt` | checksums of all files |

The workflow stops if the tag does not match `__version__`.

Installed Windows programs find the release within a day (or via the tray menu
*Check for updates*) and replace themselves while nothing is playing. They only
take the file for their own processor from this repository's latest release
over HTTPS and check it against the SHA-256 checksum GitHub lists for it.
Protect the GitHub account with two-factor authentication: whoever can publish a
release here can ship an update.

## Updating dependencies

All lock files are made with [uv](https://docs.astral.sh/uv/) for every
platform at once (Windows, macOS, Linux) and contain a hash for every file:

```bash
uv pip compile --universal --python-version 3.11 --generate-hashes -o requirements.txt requirements.in
uv pip compile --universal --python-version 3.11 --generate-hashes -o requirements-tray.txt requirements.in requirements-tray.in
uv pip compile --universal --python-version 3.11 --generate-hashes -o requirements-build.txt requirements.in requirements-tray.in requirements-build.in
uv pip compile --universal --python-version 3.11 --generate-hashes -o requirements-ci.txt requirements-ci.in
```

## Updating ffmpeg / Deno for the one-click install

`airman/deps.py` pins the exact download URL, size and SHA-256 of each package:

- ffmpeg for Windows x64: gyan.dev (`…zip.sha256` next to the download).
- ffmpeg for Windows on ARM: [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases),
  the `ffmpeg-n<version>-…-winarm64-gpl-….zip` of a **month-end** `autobuild-YYYY-MM-…`
  release (daily ones are deleted after a few weeks); the SHA-256 is shown on the
  release page.
- Deno for every platform: the official release on GitHub (`…zip.sha256sum`).
- ffmpeg on macOS and Linux comes from the package manager, nothing is pinned.

Then release a new AirMan version.
