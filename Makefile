# Check for .env.local file
ifeq (,$(wildcard ./.env.local))
$(error ".env.local file not found. Please create it by copying .env.local.example")
endif

# Allow overriding of UID, GID, and Docker Compose command
MY_UID ?= $(shell id -u)
MY_GID ?= $(shell id -g)
DOCKER_COMPOSE_CMD ?= docker compose

# Docker Compose command with environment variables
DOCKER_COMPOSE = MY_UID=${MY_UID} MY_GID=${MY_GID} ${DOCKER_COMPOSE_CMD}

# Default target
.PHONY: help
help:
	@echo "Usage: make {env|build|download|scrape <scrapeModule>}"
	@echo ""
	@echo "Available scrape modules:"
	@ls -1 app/crawls | sed 's/\.py$$//' | sed 's/^/ - /'

# Targets for docker compose commands
.PHONY: build download scrape env list

# Generic target to handle additional arguments
define run_target
	@if [ "$(filter-out $@,$(MAKECMDGOALS))" = "" ]; then \
		echo "Error: No scrape module specified."; \
		echo "Please specify a scrape module. Available options are:"; \
		ls -1 app/crawls | sed 's/\.py$$//' | sed 's/^/ - /'; \
		exit 1; \
	else \
		${DOCKER_COMPOSE} run --rm -e SCRAPE_MODULE="$(filter-out $@,$(MAKECMDGOALS))" scrapy_service $1; \
	fi
endef

# Targets for docker compose commands with environment variables
env:
	@echo "MY_UID=${MY_UID}"
	@echo "MY_GID=${MY_GID}"
	@echo "DOCKER_COMPOSE_CMD=${DOCKER_COMPOSE_CMD}"
	@echo "DOCKER_COMPOSE=${DOCKER_COMPOSE}"
	@echo "SCRAPE_MODULE=$(filter-out $@,$(MAKECMDGOALS))"

build:
	@${DOCKER_COMPOSE} build

download:
	@${DOCKER_COMPOSE} run scrapy_service download

scrape:
	@$(call run_target,scrape)

# List available crawl modules
list:
	@echo "Available crawl modules:"
	@ls -1 app/crawls | sed 's/\.py$$//' | sed 's/^/ - /'

# This line allows passing additional arguments to targets
%:
	@:
