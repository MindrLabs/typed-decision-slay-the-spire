#!/usr/bin/env bash
# Downloads the game text the models read (card, relic, potion, event and monster descriptions)
# into data/sts1. It comes from the spire-archive dump at the commit the benchmark used.
# The text belongs to the game and has no license, so this repository never ships it.
set -euo pipefail
cd "$(dirname "$0")/.."

COMMIT=687e6dce1f325234425e1b75f09d13ddd6ce7000
BASE=https://raw.githubusercontent.com/nkhoit/spire-archive/$COMMIT/data/sts1

mkdir -p data/sts1
while read -r sum file; do
  curl -sfL "$BASE/$file" -o "data/sts1/$file"
  echo "$sum  data/sts1/$file" | sha256sum --quiet -c -
done <<'EOF'
01fbd640d83c4455aa9631443e60784b9a0ff0b6e5034ea4f5ffdd0f63558360 cards.json
b3c3b2ac7f51c3bcda4e67e3c3f2f46a8c06de4a7b0bfad0e76ccbe4b27b3ac2 events.json
3664e3542252e1a6cb35646fc514546f0e0d2df72827c61f086cb0910176ad7e monsters.json
0efcd00f0d30c8a5e7627d584084f50299b1df34e72205fd41abd0929e561a2a potions.json
6d80107642b4add6c4f2c0219a19266b7476ab36ef0dd425fc7e1290e4fe85cf relics.json
EOF
echo "$COMMIT" > data/sts1/SOURCE_COMMIT
echo "game text: data/sts1 (spire-archive $COMMIT)"
