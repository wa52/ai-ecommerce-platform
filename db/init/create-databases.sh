#!/bin/bash
# Creates Saleor + AI platform databases on first container init.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE ${SALEOR_DB:-saleor};
    CREATE DATABASE ${AI_DB:-ai_platform};
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${AI_DB:-ai_platform}" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL
