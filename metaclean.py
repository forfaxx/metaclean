#!/usr/bin/env python3
"""
metaclean — Scan, strip, and sanitize image metadata (EXIF, GPS, copyright tags).

Usage Examples:
    # Scan all JPEGs in folder
    metaclean --scan *.jpg

    # Scan only, but print ONLY files with metadata (for piping)
    metaclean --scan --positives ~/Pictures/*.jpg

    # Strip metadata from files listed by another command
    find ~/Pictures -name '*.jpg' | metaclean --strip --outdir cleaned

Author: forfaxx
License: MIT
"""

import argparse
import sys
import signal
import shutil
import tempfile
from pathlib import Path
from PIL import Image, ExifTags, ImageOps, PngImagePlugin

VERSION = "1.3.0"

# ────────────────────────────────────────────────
# ⚙️  CONFIGURATION
# ────────────────────────────────────────────────

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

EXIF_TAGS_REVERSE = {v: k for k, v in ExifTags.TAGS.items()}
TAG_DATETIME_ORIGINAL = EXIF_TAGS_REVERSE.get("DateTimeOriginal")
TAG_ORIENTATION = EXIF_TAGS_REVERSE.get("Orientation")
TAG_COPYRIGHT = EXIF_TAGS_REVERSE.get("Copyright")
TAG_GPS_IFD = EXIF_TAGS_REVERSE.get("GPSInfo", 34853)  # 34853 by spec

# ────────────────────────────────────────────────
# 🎯 METADATA FUNCTIONS
# ────────────────────────────────────────────────

def pretty_exif_items(exif):
    for tag_id, val in exif.items(): # Iterate over EXIF items
        tag = ExifTags.TAGS.get(tag_id, f"Unknown({tag_id})") # Get tag name
        yield tag, val

def scan_metadata(path, verbose=True, show_gps=True):
    """
    Scan and print EXIF metadata for an image file.

    Returns:
        bool: True if metadata was found, False otherwise.
    """
    try:
        with Image.open(path) as img:
            exif = img.getexif()
    except Exception as e:
        if verbose:
            print(f"[ERROR] Cannot open {path}: {e}")
        return False

    if not exif or len(exif) == 0:
        if verbose:
            print(f"[INFO] No EXIF metadata found in {path}")
        return False

    if verbose:
        print(f"=== Metadata for {path} ===")
        for tag, val in pretty_exif_items(exif):
            print(f"{tag}: {val}")

        # Optional: expand GPS IFD if present
        if show_gps and TAG_GPS_IFD in exif:
            gps_ifd = exif.get_ifd(TAG_GPS_IFD) if hasattr(exif, "get_ifd") else exif.get(TAG_GPS_IFD)
            if gps_ifd:
                print("---- GPS ----")
                # Map known GPS tags if possible
                gpstags = getattr(ExifTags, "GPSTAGS", {}) # Fallback to empty dict if not available
                for k, v in gps_ifd.items(): # Iterate over GPS IFD items
                    name = gpstags.get(k, f"GPS_{k}") # Get GPS tag name
                    print(f"{name}: {v}")

    return True

# ────────────────────────────────────────────────
# 🧽 STRIP HELPERS
# ────────────────────────────────────────────────

def build_new_exif(src_exif, keep_date, keep_orientation, copyright_text):
    new_exif = Image.Exif()
    if src_exif:
        if keep_date and TAG_DATETIME_ORIGINAL in src_exif:
            new_exif[TAG_DATETIME_ORIGINAL] = src_exif[TAG_DATETIME_ORIGINAL]
        if keep_orientation and TAG_ORIENTATION in src_exif:
            new_exif[TAG_ORIENTATION] = src_exif[TAG_ORIENTATION]
    if copyright_text and TAG_COPYRIGHT is not None:
        new_exif[TAG_COPYRIGHT] = copyright_text
    return new_exif

def is_multiframe(img: Image.Image) -> bool:
    try:
        return getattr(img, "is_animated", False) or getattr(img, "n_frames", 1) > 1
    except Exception:
        return False

def save_atomic(img: Image.Image, outpath: Path, **save_kwargs):
    outpath.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=str(outpath.parent), delete=False, suffix=outpath.suffix) as tmp:
        tmp_name = tmp.name
    try:
        img.save(tmp_name, **save_kwargs)
        # atomic replace where possible
        Path(tmp_name).replace(outpath)
    except Exception:
        # clean up temp on failure
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except Exception:
            pass
        raise

def strip_metadata(path, outdir=None, copyright_text=None,
                   keep_date=False, keep_orientation=False,
                   keep_icc=False, keep_dpi=False,
                   inplace=False, force=False,
                   quality=95, progressive=None):
    """
    Strip metadata from an image, optionally preserving tags and/or adding copyright.
    """
    p = Path(path)
    try:
        with Image.open(p) as img: # Open image file
            fmt = (img.format or "").upper() # Get image format
            src_exif = img.getexif() # Get EXIF data
            icc_profile = img.info.get("icc_profile") if keep_icc else None
            dpi = img.info.get("dpi") if keep_dpi else None

            if is_multiframe(img) and not force:
                print(f"[SKIP] Animated/multi-frame image: {p} (use --force to process first frame)")
                return

            # Apply EXIF orientation to pixels if we are NOT keeping the orientation tag
            # This ensures visual orientation stays correct after stripping the tag.
            if not keep_orientation:
                img = ImageOps.exif_transpose(img)

            # Decide output filename
            if inplace:
                outname = p
            else:
                outdir = Path(outdir) if outdir else p.parent
                outname = outdir / (p.stem + "_clean" + p.suffix)

            # Build optional EXIF to keep
            new_exif = build_new_exif(src_exif, keep_date, keep_orientation, copyright_text)

            save_kwargs = {}
            # Format-specific save behavior
            if fmt in {"JPEG", "JPG", "TIFF", "WEBP"}:
                # For these, pass exif bytes; empty bytes => stripped
                exif_bytes = new_exif.tobytes() if len(new_exif) else b""
                save_kwargs["exif"] = exif_bytes

                if fmt in {"JPEG", "JPG"}:
                    save_kwargs["quality"] = quality
                    # Let Pillow pick optimal if not specified by user
                    if progressive is not None:
                        save_kwargs["progressive"] = bool(progressive)
                    save_kwargs["optimize"] = True

                if fmt == "WEBP":
                    # default settings; lossy by default—user can re-export losslessly later if needed
                    pass

                if icc_profile:
                    save_kwargs["icc_profile"] = icc_profile
                if dpi:
                    save_kwargs["dpi"] = dpi

                try:
                    save_atomic(img, outname, **save_kwargs)
                except Exception as e:
                    print(f"[ERROR] Could not save {outname}: {e}")
                    return

            elif fmt == "PNG":
                # PNG stores text chunks and ancillary data in a PngInfo
                pnginfo = PngImagePlugin.PngInfo()  # empty => no tEXt/iTXt/zTXt
                # No EXIF for PNG by spec; Pillow can write an "exif" chunk, but we omit to truly strip.
                if icc_profile:
                    save_kwargs["icc_profile"] = icc_profile
                if dpi:
                    save_kwargs["dpi"] = dpi

                try:
                    save_atomic(img, outname, pnginfo=pnginfo, **save_kwargs)
                except Exception as e:
                    print(f"[ERROR] Could not save {outname}: {e}")
                    return
            else:
                # Fallback: try generic save without metadata field
                try:
                    save_atomic(img, outname) # No metadata, no special save kwargs
                    print(f"[WARN] Unknown/less-tested format {fmt or p.suffix}; saved without explicit metadata.")
                except Exception as e:
                    print(f"[ERROR] Could not save {outname}: {e}")
                    return

    except Exception as e:
        print(f"[ERROR] Cannot open {p}: {e}")
        return

    if inplace:
        print(f"[OK] Stripped metadata IN PLACE → {outname}")
    else:
        print(f"[OK] Cleaned {path} → {outname}")

    if copyright_text:
        print(f"[OK] Added copyright: {copyright_text}")

# ────────────────────────────────────────────────
# 🛠️ UTILITY FUNCTIONS
# ────────────────────────────────────────────────

def files_from_stdin_or_args(files):
    """
    Yield file paths from CLI args or stdin (for pipe support).
    """
    any_yielded = False
    if not sys.stdin.isatty():
        for line in sys.stdin:
            line = line.strip()
            if line:
                any_yielded = True
                yield line
    for f in files:
        any_yielded = True
        yield f
    if not any_yielded:
        return

# ────────────────────────────────────────────────
# 🎯 MAIN CLI
# ────────────────────────────────────────────────

def main():
    """Main CLI entrypoint."""

    parser = argparse.ArgumentParser(
        prog="metaclean",
        description="Scan, strip, and sanitize image metadata (EXIF, GPS, copyright tags).",
        epilog="Example: find ./photos -name '*.jpg' | metaclean --strip --outdir cleaned"
    )

    # Main modes
    parser.add_argument("--scan", action="store_true", help="Scan and report metadata")
    parser.add_argument("--strip", action="store_true", help="Strip metadata from files")

    # Optional scan tweaks
    parser.add_argument("--positives", action="store_true",
                        help="Only show files that contain metadata (scan mode).")
    parser.add_argument("--show-gps", action="store_true",
                        help="If present, expand GPS sub-IFD (scan mode).")

    # Optional strip tweaks
    parser.add_argument("--copyright", help="Add copyright tag (only when stripping)")
    parser.add_argument("--keep-date", action="store_true", help="Preserve DateTimeOriginal tag")
    parser.add_argument("--keep-orientation", action="store_true", help="Preserve Orientation tag (pixels still corrected if not kept)")
    parser.add_argument("--keep-icc", action="store_true", help="Preserve ICC profile (color)")
    parser.add_argument("--keep-dpi", action="store_true", help="Preserve DPI")

    parser.add_argument("--force", action="store_true",
                        help="Process first frame of animated images (otherwise they are skipped)")

    # Output control
    parser.add_argument("--inplace", action="store_true",
                        help="Strip metadata and overwrite the original image (safe atomic replace).")
    parser.add_argument("--outdir", default=str(Path.home() / "Pictures/cleaned"),
                        help="Directory for cleaned images (default: ~/Pictures/cleaned)")

    # Encoding knobs
    parser.add_argument("--quality", type=int, default=95, help="JPEG quality (default: 95)")
    parser.add_argument("--progressive", type=int, choices=[0,1], help="Force progressive=1 or disable with 0 (JPEG)")

    # Version & Help
    parser.add_argument("-v", "--version", action="version", version=f"metaclean {VERSION}")

    # Input files
    parser.add_argument("files", nargs="*", help="Image files to process (or pipe via stdin)")

    args = parser.parse_args()

    # Handle Ctrl-C gracefully
    def handle_sigint(sig, frame):
        print("\n[ABORT] Metaclean interrupted by user")
        sys.exit(130)
    signal.signal(signal.SIGINT, handle_sigint)

    # Require at least one mode
    if not args.scan and not args.strip:
        parser.print_help()
        sys.exit(0)

    # Create outdir if needed
    if args.strip and not args.inplace:
        Path(args.outdir).mkdir(parents=True, exist_ok=True)

    any_input = False
    for path in files_from_stdin_or_args(args.files):
        any_input = True
        p = Path(path)

        # Skip directories
        if p.is_dir():
            print(f"[SKIP] Directory: {p}")
            continue

        # Skip unsupported file types
        if p.suffix.lower() not in SUPPORTED_EXTS:
            print(f"[SKIP] Not a supported image type: {p}")
            continue

        # Scan mode
        if args.scan:
            has_meta = scan_metadata(path, verbose=not args.positives, show_gps=args.show_gps)
            if args.positives and has_meta:
                # Print only the filename for chaining
                print(path)

        # Strip mode
        if args.strip:
            strip_metadata(
                path,
                args.outdir,
                copyright_text=args.copyright,
                keep_date=args.keep_date,
                keep_orientation=args.keep_orientation,
                keep_icc=args.keep_icc,
                keep_dpi=args.keep_dpi,
                inplace=args.inplace,
                force=args.force,
                quality=args.quality,
                progressive=args.progressive
            )

    if not any_input:
        # No files via args or stdin
        if not (args.scan or args.strip):
            parser.print_help()
        else:
            print("[INFO] No files provided on CLI or stdin.")

if __name__ == "__main__":
    # Pillow lazy import sometimes leaves plugins uninitialized until first use; open once to ensure
    main()
