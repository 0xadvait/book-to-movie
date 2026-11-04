#!/usr/bin/env bash
# One-time setup: system tools, a local Python environment, and a .env for your keys.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }

need_node=1
if command -v node >/dev/null 2>&1 && command -v npx >/dev/null 2>&1; then
  major="$(node -v | sed -E 's/^v([0-9]+).*/\1/')"
  [ "$major" -ge 22 ] && need_node=0
fi

missing=()
command -v ffmpeg >/dev/null 2>&1 || missing+=(ffmpeg)
command -v rsvg-convert >/dev/null 2>&1 || missing+=(librsvg)
command -v pdftotext >/dev/null 2>&1 || missing+=(poppler)
[ "$need_node" -eq 0 ] || missing+=(node)

if [ "${#missing[@]}" -gt 0 ]; then
  bold "Missing: ${missing[*]}"
  if command -v brew >/dev/null 2>&1; then
    cmd="brew install ${missing[*]}"
  elif command -v apt-get >/dev/null 2>&1; then
    debs=()
    for m in "${missing[@]}"; do
      case "$m" in
        librsvg) debs+=(librsvg2-bin) ;;
        poppler) debs+=(poppler-utils) ;;
        node) ;;      # apt's node is usually too old
        *) debs+=("$m") ;;
      esac
    done
    cmd="sudo apt-get install -y ${debs[*]:-}"
    [ "$need_node" -eq 0 ] || echo "Node 22 or newer: https://nodejs.org (apt's version is usually too old)"
  else
    cmd=""
  fi
  if [ -n "$cmd" ] && [ -t 0 ]; then
    read -r -p "Run: $cmd ? [Y/n] " answer
    case "${answer:-y}" in
      y|Y|yes) $cmd ;;
      *) echo "Install them yourself, then run this again." ; exit 1 ;;
    esac
  else
    echo "Install them, then run this again${cmd:+: $cmd}"
    exit 1
  fi
fi

bold "Python environment"
if command -v uv >/dev/null 2>&1; then
  uv venv --quiet --allow-existing --python ">=3.10" .venv
  uv pip install --quiet --python .venv/bin/python -e ".[dev]"
else
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -e ".[dev]"
fi

[ -f .env ] || cp .env.example .env
chmod +x movie

bold "Checking everything"
./movie doctor

cat <<'EOF'

Next:
  ./movie demo                       make a one-minute film, free, to see it work
  claude                             then: /book-to-movie path/to/your-book.pdf
EOF
