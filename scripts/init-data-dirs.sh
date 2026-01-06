#!/bin/bash
# Initialize data directory structure

set -e

DATA_DIR="${DATA_DIR:-./RPG_LLM_DATA}"

echo "Creating data directory structure at $DATA_DIR..."

mkdir -p "$DATA_DIR"/{databases,vector_stores,rules,logs,backups}
mkdir -p "$DATA_DIR"/databases/{auth,game_session,being_registry,time_management,worlds,rules_engine,game_master,beings}
mkdir -p "$DATA_DIR"/vector_stores/{worlds,game_master,beings}

echo "Data directory structure created!"

