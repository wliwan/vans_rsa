# Build configuration
# -------------------

APP_NAME := `sed -n 's/^ *name.*=.*"\([^"]*\)".*/\1/p' pyproject.toml`
APP_VERSION := `sed -n 's/^ *version.*=.*"\([^"]*\)".*/\1/p' pyproject.toml`
GIT_REVISION = `git rev-parse HEAD`

# Introspection targets
# ---------------------

.PHONY: help
help: header targets

.PHONY: header
header:
	@echo "\033[34mEnvironment\033[0m"
	@echo "\033[34m---------------------------------------------------------------\033[0m"
	@printf "\033[33m%-23s\033[0m" "APP_NAME"
	@printf "\033[35m%s\033[0m" $(APP_NAME)
	@echo ""
	@printf "\033[33m%-23s\033[0m" "APP_VERSION"
	@printf "\033[35m%s\033[0m" $(APP_VERSION)
	@echo ""
	@printf "\033[33m%-23s\033[0m" "GIT_REVISION"
	@printf "\033[35m%s\033[0m" $(GIT_REVISION)
	@echo "\n"

.PHONY: targets
targets:
	@echo "\033[34mDevelopment Targets\033[0m"
	@echo "\033[34m---------------------------------------------------------------\033[0m"
	@perl -nle'print $& if m{^[a-zA-Z_-]+:.*?## .*$$}' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# Development targets
# -------------

.PHONY: install
install: ## Install Python dependencies
	uv add pyproject.toml

.PHONY: install-web
install-web: ## Install frontend dependencies
	cd web && pnpm i

.PHONY: run
run: start

.PHONY: start
start: ## Starts the dev server
	python run.py

.PHONY: dev
dev: ## Start backend + frontend dev servers
	@echo "Starting backend on :9999 and frontend on :3000..."
	python run.py & cd web && pnpm dev

# Build targets
# -------------

.PHONY: build-web
build-web: ## Build frontend to web/dist/
	cd web && pnpm build

.PHONY: build-docker
build-docker: ## Build Docker image
	docker build --no-cache . -t vue-fastapi-admin:$(APP_VERSION)

.PHONY: build
build: build-web ## Full build (frontend only; backend is Python, no compile needed)

# Release targets
# -------------

.PHONY: release
release: build-docker ## Build and tag Docker image as latest
	docker tag vue-fastapi-admin:$(APP_VERSION) vue-fastapi-admin:latest
	@echo "Release image: vue-fastapi-admin:$(APP_VERSION) / vue-fastapi-admin:latest"

.PHONY: publish
publish: release ## Push Docker image to registry
	@echo "docker push vue-fastapi-admin:$(APP_VERSION)"
	@echo "docker push vue-fastapi-admin:latest"

# Check, lint and format targets
# ------------------------------

.PHONY: check
check: check-format lint

.PHONY: check-format
check-format: ## Dry-run code formatter
	black ./ --check
	isort ./ --profile black --check

.PHONY: lint
lint: ## Run ruff
	ruff check ./app 
 
.PHONY: format
format: ## Run code formatter
	black ./
	isort ./ --profile black


.PHONY: test
test: ## Run the test suite
	$(eval include .env)
	$(eval export $(sh sed 's/=.*//' .env))
	pytest -vv -s --cache-clear ./

.PHONY: clean-db
clean-db: ## 删除migrations文件夹和db.sqlite3
	find . -type d -name "migrations" -exec rm -rf {} +
	rm -f db.sqlite3 db.sqlite3-shm db.sqlite3-wal

.PHONY: migrate
migrate: ## 运行aerich migrate命令生成迁移文件
	aerich migrate

.PHONY: upgrade
upgrade: ## 运行aerich upgrade命令应用迁移
	aerich upgrade