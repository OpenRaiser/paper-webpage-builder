#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: convert_figures.sh <source_images_dir> <target_figures_dir> [dpi]" >&2
  exit 2
fi

src_dir="$1"
dst_dir="$2"
dpi="${3:-180}"

mkdir -p "$dst_dir"

if ! command -v gs >/dev/null 2>&1; then
  echo "Ghostscript (gs) is required to convert PDF figures." >&2
  exit 1
fi

find "$src_dir" -maxdepth 1 -type f \( -name "*.pdf" -o -name "*.PDF" \) ! -name "._*" | while IFS= read -r pdf; do
  base="$(basename "$pdf")"
  base="${base%.*}"
  safe="$(printf '%s' "$base" | iconv -c -t ascii//TRANSLIT 2>/dev/null | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g')"
  if [ -z "$safe" ]; then
    safe="figure"
  fi
  out="$dst_dir/$safe.png"
  if [ -e "$out" ]; then
    i=2
    while [ -e "$dst_dir/$safe-$i.png" ]; do
      i=$((i + 1))
    done
    out="$dst_dir/$safe-$i.png"
  fi
  if gs -dSAFER -dBATCH -dNOPAUSE -sDEVICE=pngalpha -r"$dpi" -dFirstPage=1 -dLastPage=1 -sOutputFile="$out" "$pdf" >/dev/null 2>&1; then
    echo "$out"
  else
    echo "warning: failed to convert $pdf" >&2
    rm -f "$out"
  fi
done
