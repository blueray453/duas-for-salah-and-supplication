#!/usr/bin/env bash
set -uo pipefail

FONTS=(
    "Scheherazade"
    "KacstBook"
    "KFGQPC Uthman Taha Naskh"
    "KFGQPC Uthmanic Script HAFS"
    "AlQuran IndoPak by QuranWBW"
    "Amiri Quran"
    "Katibeh"
    "_PDMS_Saleem_QuranFont"
    "Muhammadi Quranic Font"
    "Al Qalam Quran Majeed Web"
    "Noto Serif Bengali"
)

DEST="./fonts"
mkdir -p "$DEST"

# Dump the whole font list ONCE: "path: Family1,Family2:style=..."
ALL_FONTS="$(fc-list)"

FOUND=()
MISSING=()

for font in "${FONTS[@]}"; do
    echo "Searching for: $font"

    # Case-insensitive substring match against the whole fc-list dump
    matches="$(echo "$ALL_FONTS" | grep -i -- "$font" || true)"

    if [ -z "$matches" ]; then
        echo "  NOT FOUND on system: $font"
        MISSING+=("$font")
        continue
    fi

    while IFS= read -r line; do
        # Extract file path: everything before the FIRST ':'
        filepath="${line%%:*}"
        if [ -f "$filepath" ]; then
            cp -v -n "$filepath" "$DEST/"
            FOUND+=("$font -> $filepath")
        fi
    done <<< "$matches"
done

echo
echo "===== Summary ====="
echo "Copied ${#FOUND[@]} file(s) to $DEST/"
if [ ${#MISSING[@]} -gt 0 ]; then
    echo
    echo "Not found on this system (${#MISSING[@]}):"
    for m in "${MISSING[@]}"; do
        echo "  - $m"
    done
fi
