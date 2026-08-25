#!/usr/bin/env bash
# One command to publish TRIGGER to GitHub.
#
#   bash deploy.sh <github-username> <github-token> [repo-name]
#
# Creates the repository via the GitHub API and pushes main. The token needs the
# "repo" scope; make one at:
#
#   https://github.com/settings/tokens/new?scopes=repo&description=trigger-deploy
#
# Nothing is written to disk: the token is used for this run only and the remote
# is stored without it.
set -euo pipefail

USER_NAME="${1:-}"
TOKEN="${2:-}"
REPO="${3:-trigger-heat-action-plan}"

if [[ -z "$USER_NAME" || -z "$TOKEN" ]]; then
  echo "usage: bash deploy.sh <github-username> <github-token> [repo-name]" >&2
  exit 2
fi

echo "==> pre-flight"
if git ls-files | grep -qiE '\.env$'; then
  echo "REFUSING: a .env file is tracked. Remove it before publishing." >&2
  exit 1
fi
BIG=$(git ls-files -z | xargs -0 ls -l 2>/dev/null | awk '$5 > 100000000 {print $9}')
if [[ -n "$BIG" ]]; then
  echo "REFUSING: files exceed GitHub's 100 MB limit:" >&2
  echo "$BIG" >&2
  exit 1
fi
echo "    no .env tracked, no oversized files"

echo "==> creating github.com/$USER_NAME/$REPO"

# The payload is written to a file rather than passed inline. Git Bash on
# Windows mangles non-ASCII bytes in an inline -d argument, which GitHub then
# rejects with "Problems parsing JSON" -- so the description is ASCII-only and
# the body is handed to curl as a file.
PAYLOAD=$(mktemp)
cat > "$PAYLOAD" <<JSON
{"name":"$REPO","description":"TRIGGER - compiles a published Heat Action Plan into executable rules and measures what citywide sensing misses. FortyGuard Hackathon 26.","private":false,"has_issues":true,"has_wiki":false}
JSON

RESP=$(mktemp)
CODE=$(curl -sS -o "$RESP" -w "%{http_code}"   -X POST https://api.github.com/user/repos   -H "Authorization: Bearer $TOKEN"   -H "Accept: application/vnd.github+json"   -H "Content-Type: application/json"   --data-binary @"$PAYLOAD")
rm -f "$PAYLOAD"

if [[ "$CODE" == "201" ]]; then
  echo "    created"
elif grep -q "already exists" "$RESP" 2>/dev/null; then
  echo "    already exists, reusing"
elif [[ "$CODE" == "401" ]]; then
  echo "FAILED: token rejected (401). Generate a new one with the 'repo' scope:" >&2
  echo "  https://github.com/settings/tokens/new?scopes=repo" >&2
  rm -f "$RESP"; exit 1
else
  echo "FAILED (HTTP $CODE):" >&2
  cat "$RESP" >&2
  rm -f "$RESP"; exit 1
fi
rm -f "$RESP"

echo "==> pushing"
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$USER_NAME/$REPO.git"
git branch -M main
git -c credential.helper= \
    -c "http.https://github.com/.extraheader=Authorization: Bearer $TOKEN" \
    push -u origin main

echo
echo "==> pushed:  https://github.com/$USER_NAME/$REPO"
echo
echo "NEXT — Streamlit Community Cloud (browser OAuth, cannot be automated):"
echo "  1. https://share.streamlit.io  ->  sign in with GitHub"
echo "  2. New app  ->  repo $USER_NAME/$REPO, branch main, file app.py"
echo "  3. Advanced settings -> Python 3.11"
echo "  4. LEAVE THE SECRETS BOX EMPTY. The app needs no keys."
echo "  5. Deploy. First build takes 3-5 minutes."
echo
echo "Then send the URL back and it can be verified."
