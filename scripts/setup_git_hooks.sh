#!/usr/bin/env bash

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

git config core.hooksPath .githooks

chmod +x .githooks/pre-commit
chmod +x .githooks/pre-push

echo "Configured git hooks path: .githooks"
echo "Enabled hooks:"
echo "- pre-commit"
echo "- pre-push"
echo
echo "If needed, install gitleaks:"
echo "  brew install gitleaks"
