<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="airman-banners/banner-note.png">
    <img src="airman-banners/banner-sun.png" alt="AirMan" width="800">
  </picture>
</p>

<h1 align="center">AirMan</h1>
<p align="center"><em>Your speakers, your music</em></p>

<p align="center">
  <a href="https://github.com/pgadient/AirMan/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/pgadient/AirMan?sort=semver"></a>
  <a href="https://github.com/pgadient/AirMan/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/pgadient/AirMan/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/pgadient/AirMan"></a>
  <img alt="Platforms: Windows, macOS, Linux" src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-informational">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white">
  <a href="https://github.com/pgadient/AirMan/releases"><img alt="Downloads" src="https://img.shields.io/github/downloads/pgadient/AirMan/total"></a>
  <a href="#made-with-ai"><img alt="AI-generated with Claude" src="https://img.shields.io/badge/AI--generated-Claude-D97757"></a>
  <a href="https://ko-fi.com/pascalmontico"><img alt="Buy me a coffee" src="https://img.shields.io/badge/Ko--fi-buy%20me%20a%20coffee-FF5E5B?logo=ko-fi&logoColor=white"></a>
</p>

**AirMan plays YouTube, internet radio and your own music on AirPlay speakers
(HomePod, HomePod mini, Apple TV, AirPort Express, …) from a simple web page
in your home network.**

It was built for one job: put on the bedtime music in the kids' room without
leaving a phone lying next to the speaker. AirMan runs on a computer at home;
any old phone or tablet opens its page, and starting the music again takes one
tap. No cloud, no account, no telemetry.

> [!NOTE]
> This project was **generated with AI** (Claude by Anthropic). See
> [Made with AI](#made-with-ai).

## Highlights

- **Each speaker plays its own thing**, with its own playlist, loop and volume
- **Multiroom groups**: give speakers the same group number (G1, G2, …) and they
  play the same music in sync; play, skip and stop on any of them changes all,
  the volume stays per speaker
- **Search inside the app**: YouTube (or any link yt-dlp understands),
  30 000+ radio stations from [radio-browser.info](https://www.radio-browser.info),
  and your own files
- **One tap to play again**: "Play" continues where it stopped, "Restart" starts over
- **Sleep timer** that fades out gently
- **Stereo pairs** (two HomePods paired in the Home app) appear as one speaker,
  with a left/right test tone, a "which one is on the left" choice and balance
- **Apple TV** as a target too, e.g. to play through a surround system; Apple TVs
  that require it are paired once with the PIN they show on the TV
- **Starts within seconds**: YouTube songs play straight away while they are saved
  in the background, even 10-hour clips
- **Offline library**: songs you played stay on the computer and play without
  internet next time; upload your own music from the phone
- **Simple or playlist mode**: tap to play right away, or build a playlist
- **Day and night look**, 7 languages (English, German, Swiss German, French,
  Italian, Spanish, Portuguese)
- **Private by design**: home network only, password protected, HTTPS, no
  third-party content in the page (see [SECURITY.md](SECURITY.md))

## Download

| System | File | Start |
|---|---|---|
| Windows 10/11 (Intel/AMD) | [AirMan-windows-x64.exe](https://github.com/pgadient/AirMan/releases/latest/download/AirMan-windows-x64.exe) | double-click |
| Windows 11 on ARM | [AirMan-windows-arm64.exe](https://github.com/pgadient/AirMan/releases/latest/download/AirMan-windows-arm64.exe) | double-click |
| macOS (Apple silicon) | [AirMan-macos-arm64.zip](https://github.com/pgadient/AirMan/releases/latest/download/AirMan-macos-arm64.zip) | unzip, open `AirMan.app` |
| macOS (Intel) | [AirMan-macos-x64.zip](https://github.com/pgadient/AirMan/releases/latest/download/AirMan-macos-x64.zip) | unzip, open `AirMan.app` |
| Linux (x64) | [AirMan-linux-x64.tar.gz](https://github.com/pgadient/AirMan/releases/latest/download/AirMan-linux-x64.tar.gz) | `./AirMan` in a terminal |
| Linux (ARM64, e.g. Raspberry Pi 4/5) | [AirMan-linux-arm64.tar.gz](https://github.com/pgadient/AirMan/releases/latest/download/AirMan-linux-arm64.tar.gz) | `./AirMan` in a terminal |

Checksums are in `SHA256SUMS.txt` on the [release page](https://github.com/pgadient/AirMan/releases/latest).
The programs are not signed with a paid certificate, so the system warns the
first time:

- **Windows** (SmartScreen): *More info* → *Run anyway*.
- **macOS**: right-click `AirMan.app` → *Open* → *Open*. Or in the Terminal:
  `xattr -dr com.apple.quarantine AirMan.app`. Allow *Local Network* access when
  asked; without it AirMan finds no speakers.

The computer running AirMan must be in the same network (subnet) as the
speakers, because they are found via Bonjour/mDNS.

## Getting started

### Windows

Double-click `AirMan.exe`. On the first start AirMan asks for a web password and
offers to download its two helper programs, [ffmpeg](https://ffmpeg.org) and
[Deno](https://deno.com) (each pinned to an exact version and checked against a
built-in SHA-256 fingerprint). AirMan then runs in the background with an icon
in the system tray: *Open AirMan*, *Settings…* (port, HTTPS, music folders,
start with Windows, automatic updates), *Change password…*, *Check for updates*,
*Open data folder*, *Quit*.

Its data lives in a `data` folder next to the program, so the folder can be
copied anywhere.

### macOS

Open `AirMan.app`. It asks for a web password and offers to install what is
missing: Deno is downloaded (pinned and checked like on Windows), ffmpeg is
installed with [Homebrew](https://brew.sh) (`brew install ffmpeg`). Without
Homebrew, install it first or put an `ffmpeg` program into
`~/Library/Application Support/AirMan/bin`. AirMan then shows an icon in the
menu bar. Its data lives in `~/Library/Application Support/AirMan`.

### Linux

AirMan runs as a server in the terminal or as a service, without a tray icon.

```bash
tar -xzf AirMan-linux-x64.tar.gz
./AirMan --set-password            # choose the web password
./AirMan                           # start; Ctrl+C stops it
```

On the first start in a terminal AirMan asks whether to install what is
missing: ffmpeg with the system's package manager (`sudo apt-get install ffmpeg`,
dnf, pacman, zypper or apk; sudo asks for your password) and Deno as a pinned,
checked download into `bin/` next to the program. As a service it never asks;
install ffmpeg and Deno before. Without `--set-password` the first start prints
a random password once. Its
data lives in a `data` folder next to the program (or `--data <folder>` /
the `AIRMAN_DATA` environment variable). Everything is configured in
`data/config.json` (see [Configuration](#configuration)); restart AirMan after
changing it.

Run it as a service with systemd (`/etc/systemd/system/airman.service`):

```ini
[Unit]
Description=AirMan
After=network-online.target
Wants=network-online.target

[Service]
User=airman
ExecStart=/opt/airman/AirMan --data /var/lib/airman
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now airman
```

### On the phone

Open the address AirMan shows (for example `https://192.168.1.10:8770`) and
log in. The phone stays logged in for a year. Tip: *Add to Home Screen*.

AirMan serves the page over HTTPS with a certificate from its own local
certificate authority (see [SECURITY.md](SECURITY.md)). The first time, the
browser shows a warning you can accept. To get rid of it for good, tap
*Install certificate* on the login page:

- **iPhone / iPad**: download it, then *Settings → Profile Downloaded → Install*,
  then *Settings → General → About → Certificate Trust Settings* and switch it on.
- **Android**: *Settings → Security → Encryption & credentials → Install a
  certificate → CA certificate*.

## Speaker settings

- **HomePod**: in the Home app, under *Home Settings → Speakers & TV*, "Allow
  Speaker Access" must be *Everyone* or *Anyone on the Same Network*.
- **Apple TV**: if it asks for verification, AirMan shows a *Pair* button.
  Tap it, then type the PIN the TV shows. This is needed only once.

## Configuration

`config.json` in the data folder is created on the first start:

| Key | Default | Meaning |
|---|---|---|
| `host` / `port` | `0.0.0.0` / `8770` | where the web page listens |
| `https` | `true` | serve the page over HTTPS (see above) |
| `http_port` | `0` | optional extra port without encryption for old devices that can not open the HTTPS page (e.g. an old iPod); `0` = off |
| `tls_cert_file` / `tls_key_file` | `""` | your own certificate instead of the local CA |
| `allowed_networks` | private ranges | only these client addresses may connect |
| `media_dirs` | `[]` | folders with your own music, e.g. `["D:/Music"]`, shown in the *Files* tab |
| `youtube_cookies_file` | `""` | optional, see below |
| `ffmpeg_path` / `deno_path` | auto | set if the tools are not found automatically |
| `offline_max_mb` | `20000` | size limit of the offline YouTube library (`0` = keep everything) |
| `auto_update` | `true` | Windows program: install new releases automatically |
| `support_email` | `debug@pcproblem.ch` | address the *Report bug* button fills in |

Command line (all systems, also for the source version):

```bash
AirMan --set-password   # choose a new password (logs out all devices)
AirMan --scan           # list AirPlay speakers in the network
AirMan -p 9000          # other port (or environment variable AIRMAN_PORT)
AirMan --data <folder>  # other data folder
AirMan --help
```

### Logs

AirMan keeps the last 5000 log lines in memory and writes rotating log files to
`logs/` in the data folder (4 × 1 MB). Passwords, cookies and session tokens are
never logged. *Report bug* in the web page copies the logs or opens an issue or
a mail with them; nothing is sent by the server itself.

### YouTube login (optional)

Public videos need no login. AirMan never asks for your Google password. If you
really need it (e.g. members-only videos), export a `cookies.txt` from your
browser, store it outside the AirMan folder and set `youtube_cookies_file`.
Treat that file like a password.

## Updates

The Windows program looks for a new release once a day and installs it while
nothing is playing (can be switched off in *Settings*). It only takes the file
for its own processor from this repository's latest release, over HTTPS, and
checks it against the SHA-256 checksum GitHub lists for it. On macOS and Linux,
download the new version from the [releases](https://github.com/pgadient/AirMan/releases).

## Run from source

Needs Python 3.11+, ffmpeg and Deno.

```bash
git clone https://github.com/pgadient/AirMan.git
cd AirMan
python -m venv .venv
.venv/Scripts/python -m pip install --require-hashes -r requirements.txt   # Windows
.venv/bin/python -m pip install --require-hashes -r requirements.txt       # Linux / macOS
.venv/bin/python -m airman                                                 # start
```

With a tray icon: install `requirements-tray.txt` instead and start with
`python -m airman --tray`. Build the program yourself:

```bash
python -m pip install --require-hashes -r requirements-build.txt
python build.py        # result in dist/
```

## What is not supported

- **Apple Music / Spotify**: their songs are copy protected (DRM) and can not
  be streamed by third-party programs.
- **Synchronized multi-room**: each speaker gets its own stream. Two separate
  speakers playing the same song are not in sync. (The two HomePods of a stereo
  pair are kept in sync.)
- **Surround sound**: AirPlay audio is stereo. An Apple TV passes it on as two
  channels; many receivers can spread it to all speakers (upmix).

## Made with AI

AirMan was **generated with AI**: nearly all code, tests and
documentation were written by Claude (Anthropic) in
[Claude Code](https://claude.com/claude-code), directed, reviewed and tested
on real HomePods by [Pascal Montico-Gadient](https://github.com/pgadient).
It has been used daily at home, but it is a hobby project: read the code
before you rely on it, and please [report bugs](https://github.com/pgadient/AirMan/issues).

## Legal note

Downloading audio from YouTube may violate YouTube's Terms of Service. AirMan
is meant for private use in your own home; you are responsible for how you use
it. AirMan is not affiliated with Apple. AirPlay, HomePod and Apple TV are
trademarks of Apple Inc.

## Development

```bash
python -m unittest discover -s tests -v
```

Dependencies are pinned with hashes for all platforms:

| File | For |
|---|---|
| `requirements.txt` | AirMan itself |
| `requirements-tray.txt` | + tray icon (pystray, Pillow) |
| `requirements-build.txt` | + PyInstaller, to build the program |
| `requirements-ci.txt` | pip-audit for the CI vulnerability check |

How to update them and how to publish a release: [RELEASING.md](RELEASING.md).
Security design and how to report a problem: [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © Pascal Montico-Gadient
