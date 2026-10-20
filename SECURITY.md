# Security

## Reporting a problem

Please report security issues privately through GitHub's
"Report a vulnerability" button (Security tab) instead of opening a public issue.

## Design

AirMan is meant to run inside a home network. It is built so that nothing
sensitive ends up in the repository or leaves your network:

- **No accounts stored.** AirMan never asks for a Google or Apple password.
  An optional YouTube `cookies.txt` stays on your machine and is git-ignored.
- **Local network only.** Requests from outside the configured networks
  (by default private address ranges) are refused before anything else runs.
- **Login.** The web password is stored as a scrypt hash. Session tokens are
  stored only as SHA-256 hashes. Cookies are `HttpOnly` and `SameSite=Strict`.
  Repeated wrong passwords lock the address out with growing delays.
- **No cross-site requests.** State changes are only accepted as same-origin
  JSON POST requests; a strict Content Security Policy blocks inline and
  third-party scripts, and the page loads nothing from other servers.
- **Restricted helpers.** ffmpeg runs with a protocol whitelist (only
  `http(s)` for streams, only `file` for local files). Local files are limited
  to the configured folders. yt-dlp may not download extra code at runtime;
  YouTube's JavaScript challenge runs in Deno, which is sandboxed by default.
- **Apple TV pairing.** Apple TVs that require it are paired once with the PIN
  they show on the screen. The resulting credentials are stored in
  `data/pairings.json`, readable only by your user account and git-ignored.
- **No telemetry.** AirMan only contacts: your speakers; YouTube (search, audio,
  `i.ytimg.com` for preview images) when you use it; radio-browser.info when you
  search radio; GitHub once a day for updates (standalone program); and gyan.dev /
  GitHub when you choose the one-click download of ffmpeg / Deno.
- **No requests into your network on behalf of users.** Links and radio streams
  must point to the internet; addresses of this computer or the home network are
  refused, so the server can not be used to probe other devices.
- **Updates (Windows program).** Only taken from the latest release of
  `pgadient/AirMan` on GitHub over HTTPS, checked against the SHA-256 checksum
  GitHub lists for the file, and installed only while nothing is playing. Can be
  switched off in Settings. Releases are built by GitHub Actions from the tagged
  source code.
- **Supply chain.** Few dependencies, pinned with hashes in `requirements.txt`,
  checked by `pip-audit` and Dependabot. CI actions are pinned to commit SHAs
  and a secret scanner (gitleaks) runs on every push.
- **HTTPS by default.** AirMan creates its own small certificate authority in
  `data/tls/` (readable only by your user account). It is limited with X.509
  *name constraints* to private IP ranges, `localhost` and `<computer>.local`, and
  may only vouch for web servers, so even a leaked CA key can not be used to
  impersonate real websites or sign programs on a phone that trusts it. Installing the CA
  on phones is optional (it only removes the browser warning).

## Optional plain HTTP

`http_port` (off by default) adds a second port without encryption for old
devices. It needs the same password and uses its own session cookie, but
anyone in the network could read the password and the session from that
traffic. Only switch it on if a device really can not use HTTPS.

## Not covered

- Do not expose AirMan to the internet (port forwarding). Use a VPN instead.
  Behind a port forward or reverse proxy every visitor can appear as one local
  address, which defeats the network restriction and the per-address lockout.
