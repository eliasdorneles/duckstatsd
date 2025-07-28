.DEFAULT_GOAL := help

format: ## Format code
	ruff format .
	uvx djlint --reformat duckstatsd/web/templates/

deploy: ## Build and push the Docker image to Docker Hub
	@git diff-index --quiet HEAD -- || (echo "There are uncommitted changes. Please commit or stash them before building." && exit 1)
	docker build -t eliasdorneles/duckstatsd .
	docker push eliasdorneles/duckstatsd

# Implements this pattern for autodocumenting Makefiles:
# https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
#
# Picks up all comments that start with a ## and are at the end of a target definition line.
.PHONY: help
help:  ## Display this help message
	@grep -E '^[0-9a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
