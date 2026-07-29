#!/usr/bin/env bash

set -euo pipefail

# ============================================
# Config
# ============================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CSV_ROOT="${PROJECT_ROOT}/data/csv"
PYTHON_SCRIPT_DIR="${PROJECT_ROOT}/scripts/python"

# Required env vars
: "${NEO4J_URI:?Need to set NEO4J_URI, e.g. bolt://localhost:7687}"
: "${NEO4J_USER:?Need to set NEO4J_USER}"
: "${NEO4J_PASSWORD:?Need to set NEO4J_PASSWORD}"
: "${NEO4J_DATABASE:=neo4j}"
: "${NEO4J_IMPORT_DIR:?Need to set NEO4J_IMPORT_DIR, e.g. /path/to/neo4j/import}"

# Optional flags
RUN_CLEAR="${RUN_CLEAR:-false}"
SKIP_VALIDATE="${SKIP_VALIDATE:-false}"

echo "============================================"
echo "Biomed KG Import Runner"
echo "============================================"
echo "PROJECT_ROOT      = ${PROJECT_ROOT}"
echo "CSV_ROOT          = ${CSV_ROOT}"
echo "NEO4J_URI         = ${NEO4J_URI}"
echo "NEO4J_USER        = ${NEO4J_USER}"
echo "NEO4J_DATABASE    = ${NEO4J_DATABASE}"
echo "NEO4J_IMPORT_DIR  = ${NEO4J_IMPORT_DIR}"
echo "RUN_CLEAR         = ${RUN_CLEAR}"
echo "SKIP_VALIDATE     = ${SKIP_VALIDATE}"
echo "============================================"

# ============================================
# Step 1: Validate CSV
# ============================================

if [[ "${SKIP_VALIDATE}" != "true" ]]; then
  echo "[1/4] Validating CSV files..."
  python3 "${PYTHON_SCRIPT_DIR}/validate_csv.py" --project-root "${PROJECT_ROOT}"
  echo "[1/4] CSV validation passed."
else
  echo "[1/4] Skipping CSV validation."
fi

# ============================================
# Step 2: Sync CSV to Neo4j import dir
# ============================================

echo "[2/4] Syncing CSV files to Neo4j import directory..."

mkdir -p "${NEO4J_IMPORT_DIR}/reference"
mkdir -p "${NEO4J_IMPORT_DIR}/entities"
mkdir -p "${NEO4J_IMPORT_DIR}/relations"

cp -f "${CSV_ROOT}/reference/"*.csv "${NEO4J_IMPORT_DIR}/reference/" || true
cp -f "${CSV_ROOT}/entities/"*.csv "${NEO4J_IMPORT_DIR}/entities/" || true
cp -f "${CSV_ROOT}/relations/"*.csv "${NEO4J_IMPORT_DIR}/relations/" || true

echo "[2/4] CSV sync completed."

# ============================================
# Step 3: Execute Cypher import files
# ============================================

echo "[3/4] Running Cypher import pipeline..."

python3 "${PYTHON_SCRIPT_DIR}/import_runner.py" \
  --project-root "${PROJECT_ROOT}" \
  --uri "${NEO4J_URI}" \
  --user "${NEO4J_USER}" \
  --password "${NEO4J_PASSWORD}" \
  --database "${NEO4J_DATABASE}" \
  $( [[ "${RUN_CLEAR}" == "true" ]] && echo "--run-clear" )

echo "[3/4] Import pipeline completed."

# ============================================
# Step 4: Done
# ============================================

echo "[4/4] Done."
echo "Import finished successfully."