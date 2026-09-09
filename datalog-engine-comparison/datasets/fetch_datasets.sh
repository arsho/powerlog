#!/usr/bin/env bash
# Download the graphs used by the Datalog engine comparison.
#
# The datasets are public and are not vendored in this repository (~400 MB).
# They come from SuiteSparse (https://sparse.tamu.edu) and SNAP
# (https://snap.stanford.edu/data). See datasets.csv for the full manifest.
#
# Usage:
#   ./fetch_datasets.sh [destination_dir]   # default: ./raw

set -euo pipefail

DEST="${1:-$(dirname "$0")/raw}"
mkdir -p "$DEST"

SUITESPARSE=(
  "https://suitesparse-collection-website.herokuapp.com/MM/DIMACS10/fe_body.tar.gz"
  "https://suitesparse-collection-website.herokuapp.com/MM/DIMACS10/fe_sphere.tar.gz"
  "https://suitesparse-collection-website.herokuapp.com/MM/DIMACS10/vsp_finan512_scagr7-2c_rlfddd.tar.gz"
  "https://suitesparse-collection-website.herokuapp.com/MM/Rajat/SF.cedge.tar.gz"
  "https://suitesparse-collection-website.herokuapp.com/MM/Gleich/usroads.tar.gz"
)

SNAP=(
  "https://snap.stanford.edu/data/ca-HepTh.txt.gz"
  "https://snap.stanford.edu/data/loc-brightkite_edges.txt.gz"
)

fetch() {
  local url="$1" name
  name="$(basename "$url")"
  if [ -f "$DEST/$name" ]; then
    echo "have   $name"
    return
  fi
  echo "fetch  $name"
  curl -fsSL --retry 3 -o "$DEST/$name" "$url"
}

for url in "${SUITESPARSE[@]}" "${SNAP[@]}"; do
  fetch "$url"
done

echo
echo "Extracting into $DEST ..."
for archive in "$DEST"/*.tar.gz; do
  [ -e "$archive" ] || continue
  tar -xzf "$archive" -C "$DEST"
done
for archive in "$DEST"/*.txt.gz; do
  [ -e "$archive" ] || continue
  gunzip -kf "$archive"
done

echo
echo "Done. Raw graphs are in: $DEST"
echo "Convert them to the per-engine edge-list / binary formats before running"
echo "harness/run_cpu_gpu_energy.sh (see the engine repositories for the"
echo "expected input layout)."
