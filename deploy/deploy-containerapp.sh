#!/usr/bin/env bash
# Update one Azure Container App to a new image, with its secrets and settings. Run by the
# deploy job in .github/workflows/cd.yml, never by hand. (The two Container Apps are created
# once, during the initial setup in docs/azure-setup.md.)
#
#   deploy-containerapp.sh <app-name> <image> <secret=value>... -- <ENV=value>...
#
# Secrets are stored in the Container App as secrets (encrypted, not shown in the portal)
# and handed to the program as environment variables with  ENV=secretref:<secret-name>.
# Expects RESOURCE_GROUP in the environment. Prints the app's public address (FQDN) last.
set -euo pipefail

APP=$1
IMAGE=$2
shift 2
SECRETS=()
while [ $# -gt 0 ] && [ "$1" != "--" ]; do SECRETS+=("$1"); shift; done
shift  # the --
ENV_VARS=("$@")

echo "Updating $APP to $IMAGE" >&2
az containerapp secret set --name "$APP" --resource-group "$RESOURCE_GROUP" \
  --secrets "${SECRETS[@]}" --output none
# A new image means a new revision; it starts with the new secrets and settings
az containerapp update --name "$APP" --resource-group "$RESOURCE_GROUP" --image "$IMAGE" \
  --min-replicas 0 --max-replicas 1 --set-env-vars "${ENV_VARS[@]}" --output none

az containerapp show --name "$APP" --resource-group "$RESOURCE_GROUP" \
  --query properties.configuration.ingress.fqdn --output tsv
