# AirMan Website Banners

Background artwork for the website header. The banners contain no text: the
title and tagline are meant to be set in HTML on top, so they stay sharp,
selectable, translatable and accessible.

| File | Artwork |
|---|---|
| `banner-note` | Laughing music note, night sky |
| `banner-moon` | Singing moon, night sky |
| `banner-sun` | Singing sun, day sky with clouds |

Each comes as `.png` (1600×400), `@2x.png` (3200×800, for high-DPI screens) and `.svg`.

The mascot sits on the left; the area from roughly 32 % to 70 % of the width is
kept clear for the text.

## Usage

```html
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;700&display=swap" rel="stylesheet">

<header class="hero hero--night">
  <div class="hero__text">
    <h1>AirMan</h1>
    <p>Your speakers, your music</p>
  </div>
</header>
```

```css
.hero {
  aspect-ratio: 4 / 1;
  min-height: 220px;
  display: flex;
  align-items: center;
  padding-left: 32%;
  background: #1A2550 url("/img/banner-note.png") left center / cover no-repeat;
  background-image: image-set(url("/img/banner-note.png") 1x, url("/img/banner-note@2x.png") 2x);
  font-family: "Sora", sans-serif;
}
.hero__text h1 { margin: 0; font-size: clamp(2.5rem, 8vw, 8rem); font-weight: 700; letter-spacing: -0.02em; line-height: 1; }
.hero__text p  { margin: .4em 0 0; font-size: clamp(1rem, 2.2vw, 2.1rem); }

.hero--night  { color: #FFFFFF; }
.hero--night p { color: #FFE9A8; }

.hero--day {
  color: #1D2B5C;
  background-color: #8CC8F0;
  background-image: image-set(url("/img/banner-sun.png") 1x, url("/img/banner-sun@2x.png") 2x);
}
.hero--day p { color: #2E4A7A; }

/* Phones: taller hero, keep the mascot visible, text below it */
@media (max-width: 640px) {
  .hero { aspect-ratio: auto; min-height: 260px; padding: 150px 20px 24px; align-items: flex-end; background-position: 10% center; }
}
```

Optional: switch between day and night automatically with
`@media (prefers-color-scheme: light) { … }`.

## Colours

| | Night | Day |
|---|---|---|
| Background | `#1A2550` → `#25346F` | `#6CB8EA` → `#A9DAF7` |
| Title | `#FFFFFF` | `#1D2B5C` |
| Tagline | `#FFE9A8` | `#2E4A7A` |

## Used in AirMan

The web page does not show the full banners. It uses parts made from the SVGs:

- `mascot-note.svg`, `mascot-moon.svg`, `mascot-sun.svg`: only the mascot with
  its glow, on a transparent background.
- `tile-night.svg`, `tile-day.svg`: seamless tiles of the night and day sky,
  used as the page background, so the mascot stands on the same sky without a
  visible banner edge.
