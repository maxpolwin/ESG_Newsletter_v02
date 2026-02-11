#!/usr/bin/env bash
# Pre-commit secret scanning hook
# Scans staged files for potential secrets before allowing commits.
#
# Install as a git hook:
#   cp scripts/check_secrets.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# Or run manually:
#   bash scripts/check_secrets.sh

set -euo pipefail

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

FOUND_SECRETS=0

# Patterns that indicate hardcoded secrets
SECRET_PATTERNS=(
    # API keys with actual values (not env var references)
    'sk-[a-zA-Z0-9]{20,}'
    'pk-[a-zA-Z0-9]{20,}'
    'api[_-]?key\s*[:=]\s*["\x27][a-zA-Z0-9]{16,}'
    'secret[_-]?key\s*[:=]\s*["\x27][a-zA-Z0-9]{16,}'
    'access[_-]?token\s*[:=]\s*["\x27][a-zA-Z0-9]{16,}'
    'auth[_-]?token\s*[:=]\s*["\x27][a-zA-Z0-9]{16,}'
    # AWS
    'AKIA[0-9A-Z]{16}'
    # Password assignments with literal values
    'password\s*[:=]\s*["\x27][^"\x27]{8,}'
    # Bearer tokens
    'Bearer\s+[a-zA-Z0-9_\-\.]{20,}'
    # Private keys
    'BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY'
)

# File patterns to skip
SKIP_PATTERNS="\.env\.example|check_secrets\.sh|\.gitignore|\.md$"

# Get files to check - either staged files (git hook) or all tracked files (manual)
if git rev-parse --verify HEAD >/dev/null 2>&1; then
    FILES=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || git ls-files)
else
    FILES=$(git ls-files)
fi

if [ -z "$FILES" ]; then
    echo -e "${GREEN}No files to check.${NC}"
    exit 0
fi

echo "Scanning for potential secrets..."

for file in $FILES; do
    # Skip binary files and excluded patterns
    if echo "$file" | grep -qE "$SKIP_PATTERNS"; then
        continue
    fi

    # Skip if file doesn't exist
    [ -f "$file" ] || continue

    for pattern in "${SECRET_PATTERNS[@]}"; do
        matches=$(grep -nEi "$pattern" "$file" 2>/dev/null || true)
        if [ -n "$matches" ]; then
            # Filter out env var references (os.getenv, os.environ, get_required_env_var)
            filtered=$(echo "$matches" | grep -vE 'os\.(getenv|environ)|get_required_env_var|import|#.*TODO|your-.*-here|example\.com|placeholder' || true)
            if [ -n "$filtered" ]; then
                echo -e "${RED}POTENTIAL SECRET in $file:${NC}"
                echo "$filtered" | while IFS= read -r line; do
                    echo -e "  ${YELLOW}$line${NC}"
                done
                FOUND_SECRETS=1
            fi
        fi
    done
done

# Check for .env files being committed
ENV_FILES=$(echo "$FILES" | grep -E '\.env$|\.env\.' | grep -v '\.env\.example' || true)
if [ -n "$ENV_FILES" ]; then
    echo -e "${RED}WARNING: .env file(s) staged for commit:${NC}"
    echo "$ENV_FILES" | while IFS= read -r f; do
        echo -e "  ${YELLOW}$f${NC}"
    done
    FOUND_SECRETS=1
fi

if [ "$FOUND_SECRETS" -eq 1 ]; then
    echo ""
    echo -e "${RED}Potential secrets detected! Review the above findings.${NC}"
    echo -e "If these are false positives, you can bypass with: ${YELLOW}git commit --no-verify${NC}"
    exit 1
else
    echo -e "${GREEN}No secrets detected.${NC}"
    exit 0
fi
