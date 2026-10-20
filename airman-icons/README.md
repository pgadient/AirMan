# AirMan icon set

Two variants with the same file structure:

- `night/` – singing moon in a starry sky (night blue)
- `day/` – singing sun in a blue sky

| File | Purpose |
|---|---|
| `favicon.svg` | Favicon for modern browsers (simplified, readable at 16–32 px) |
| `favicon.ico` | Fallback favicon (16/32/48 px) |
| `favicon-16.png`, `favicon-32.png` | PNG favicons |
| `apple-touch-icon.png` | iOS "Add to Home Screen" (180 px, full bleed – iOS rounds the corners itself) |
| `icon-192.png`, `icon-512.png` | PWA icons (`purpose: any`, rounded corners) |
| `icon-maskable-192.png`, `icon-maskable-512.png` | PWA icons for Android (`purpose: maskable`, motif inside the 80 % safe zone) |
| `airman-icon.svg` / `-square.svg` / `-maskable.svg` | Master SVGs |
| `airman-icon-1024.png` | Large export (README, GitHub social preview) |

## `<head>` – the favicon follows the device's light/dark mode

```html
<link rel="icon" href="/icons/day/favicon.svg" type="image/svg+xml" media="(prefers-color-scheme: light)">
<link rel="icon" href="/icons/night/favicon.svg" type="image/svg+xml" media="(prefers-color-scheme: dark)">
<link rel="icon" href="/icons/night/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/icons/night/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#74BDEB" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#1A2550" media="(prefers-color-scheme: dark)">
```

The Apple touch icon and the PWA manifest can not switch between light and dark,
so pick one there (suggestion: `night`, which fits the main use: bedtime music).

## `manifest.webmanifest`

```json
{
  "name": "AirMan",
  "short_name": "AirMan",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#1A2550",
  "theme_color": "#1A2550",
  "icons": [
    { "src": "/icons/night/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any" },
    { "src": "/icons/night/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any" },
    { "src": "/icons/night/icon-maskable-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable" },
    { "src": "/icons/night/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
```

## Colours

| | Night | Day |
|---|---|---|
| Background | `#1A2550` | `#74BDEB` |
| Moon / sun | `#FFE9A8` | `#FFD45C` |
| Face | `#1A2550` | `#3A3F6B` |
| Cheeks | `#F29C8A` | `#F29C8A` |
| Notes, stars, clouds | `#FFFFFF` | `#FFFFFF` |
