#!/bin/bash

# Enable BuildKit
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Stop and remove containers
docker compose down

# Rebuild and start services in parallel
docker compose build --parallel
docker compose up -d 