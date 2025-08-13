# 🧹 metaclean

**Scan, strip, and sanitize image metadata — before you share it.**

`metaclean` is a tiny, pipe-friendly CLI utility that inspects images for EXIF metadata (GPS, camera serials, copyright tags) and removes it safely. Perfect for:

- Preparing photos for blog posts or public sharing
- Stripping GPS from family shots before you upload
- Sweeping an entire image folder without accidentally trashing originals

It’s built to be safe, scriptable, and easy to understand — no 40-character `exiftool` incantations required.

---

## ✨ Features

- 🕵️ **Scan** JPG, PNG, WebP, TIFF for metadata (EXIF, GPS, copyright)
- 🧹 **Strip** all metadata by default (EXIF is rebuilt clean)
- 🏷 **Optional copyright tag** (`--copyright "© Your Name"`)
- 🎛 **Granular control** — preserve `--keep-date` or `--keep-orientation` if you choose
- 🔄 **Safe by default**: makes a `_clean` copy in `~/Pictures/cleaned/` unless you ask for `--inplace`
- 📡 **Pipe-friendly**: plays well with `find`, `xargs`, `fd`, etc.

---

## 🚀 Installation

```bash
git clone https://github.com/you/metaclean.git
cd metaclean
chmod +x metaclean.py
sudo mv metaclean.py /usr/local/bin/metaclean
```

---

## 🔧 Usage

### 🕵️ **Scan for metadata**

```bash
# Scan a single image
metaclean --scan photo.jpg

# Scan multiple images (globs expand in shell)
metaclean --scan *.jpg

# Scan recursively using find
find ~/Pictures -name '*.jpg' | metaclean --scan
```

---

### 🎯 **Only show images that HAVE metadata**

```bash
# Only print “positive” files (quietly skips clean images)
metaclean --scan --positives *.jpg
```

This makes it easy to pipe only “dirty” files to a strip command:

```bash
metaclean --scan --positives ~/Pictures/*.jpg | metaclean --strip
```

---

### 🧹 **Strip metadata**

```bash
# Default: creates clean copies in ~/Pictures/cleaned/
metaclean --strip *.jpg

# Keep date/orientation info
metaclean --strip --keep-date --keep-orientation *.jpg

# Add a copyright tag to YOUR images only
metaclean --strip --copyright "© forfaxx" *.jpg
```

---

### ⚠️ **Overwrite originals (in-place)**

```bash
# Strip metadata and overwrite files
metaclean --strip --inplace *.jpg
```

By default, metaclean **never overwrites originals**.  
`--inplace` tells it to overwrite, for trusted workflows (like prepping all images for a blog post).

---

### 📦 **Batch & pipe examples**

```bash
# Strip metadata from all JPGs in a folder
metaclean --strip ~/Pictures/*.jpg

# Scan recursively with find, strip only files that have metadata
find ~/Pictures -name '*.jpg' | metaclean --scan --positives | metaclean --strip --inplace

# Add copyright ONLY to images with metadata and keep orientation
find ~/Photos -name '*.jpg' | metaclean --scan --positives | metaclean --strip --copyright "© forfaxx" --keep-orientation
```

---

## 🛡 Defaults & Safety

- **Does NOT overwrite originals** unless you use `--inplace`.
- **Skips non-images and directories** automatically.
- **Wipes all metadata** by default — only keeps tags you explicitly `--keep-*`.
- ✅ Orientation: **pixels are saved “baked in”** so the cleaned image *looks* correct even if EXIF is stripped.
- ✅ GPS: always removed unless you explicitly re-add.

---

## 🔮 Roadmap

- 📝 `--report` CSV mode for “privacy inventory”
- 🔍 Optional `--stego` invisible watermarking for ownership tracking
- 🧩 Optional backend “modes” (`--use-exiftool`) for exotic file types

---

## ⚖️ License

MIT — because image hygiene should be free and easy.

---

> *“Just because you don’t see metadata doesn’t mean it’s not there.”*
