#!/usr/bin/env bash
# Deploy lmbda.py to the Bedrock Agent action group Lambda.
# The function handler in AWS is dummy_lambda.lambda_handler — we zip lmbda.py under that name.
set -euo pipefail

FUNCTION_NAME="${1:-action_group_quick_start_38hbb-hwq2r}"
REGION="${AWS_REGION:-us-east-1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

cp "$ROOT/lmbda.py" "$TMPDIR/dummy_lambda.py"
(cd "$TMPDIR" && zip -j agent_action.zip dummy_lambda.py)

echo "Uploading to $FUNCTION_NAME ($REGION)..."
aws lambda update-function-code \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION" \
  --zip-file "fileb://$TMPDIR/agent_action.zip"

echo "Done. Test GetTime:"
echo '  aws lambda invoke --function-name '"$FUNCTION_NAME"' --region '"$REGION"' \'
echo '    --cli-binary-format raw-in-base64-out \'
echo '    --payload '"'"'{"actionGroup":"test","function":"GetTime","parameters":[]}'"'"' /tmp/out.json && cat /tmp/out.json'
