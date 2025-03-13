#!/usr/bin/env bash
set -e

GROVER_DB_PATH="/data/grover.db"

# Ensure Grover DB exists
if [ ! -f "$GROVER_DB_PATH" ]; then
    echo "Initializing Grover database..."
    python database/setup_database.py
else
    echo "Grover database already exists, skipping init..."
fi

exec "$@"
