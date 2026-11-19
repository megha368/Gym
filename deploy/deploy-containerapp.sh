#!/usr/bin/env bash
# Create or update one Azure Container App. Run by the deploy job in
# .github/workflows/pipeline.yml, never by hand.
#
#   deploy-containerapp.sh <app-name> <image> <secret=value>... -- <ENV=value>...
#
# Secrets are stored in the Container App as secrets (encrypted, not shown in the portal)
# and handed to the program as environment variables with  ENV=secretref:<secret-name>.
# Expects RESOURCE_GROUP, PREFIX, REGISTRY_USER and GHCR_PULL_TOKEN in the environment.
# Prints the app's public address (FQDN) as its last line.
set -euo pipefail

APP=$1
IMAGE=$2
shift 2
SECRETS=()
while [ $# -gt 0 ] && [ "$1" != "--" ]; do SECRETS+=("$1"); shift; done
shift  # the --
ENV_VARS=("$@")

if az containerapp show --name "$APP" --resource-group "$RESOURCE_GROUP" --output none 2>/dev/null; then
  echo "Updating $APP to $IMAGE" >&2
  az containerapp registry set --name "$APP" --resource-group "$RESOURCE_GROUP" \
    --server ghcr.io --username "$REGISTRY_USER" --password "$GHCR_PULL_TOKEN" --output none
  az containerapp secret set --name "$APP" --resource-group "$RESOURCE_GROUP" \
    --secrets "${SECRETS[@]}" --output none
  # A new image means a new revision; it starts with the new secrets and settings
  az containerapp update --name "$APP" --resource-group "$RESOURCE_GROUP" --image "$IMAGE" \
    --min-replicas 0 --max-replicas 1 --set-env-vars "${ENV_VARS[@]}" --output none
else
  echo "Creating $APP with $IMAGE" >&2
  az containerapp create --name "$APP" --resource-group "$RESOURCE_GROUP" \
    --environment "$PREFIX-env" --image "$IMAGE" \
    --registry-server ghcr.io --registry-username "$REGISTRY_USER" --registry-password "$GHCR_PULL_TOKEN" \
    --ingress external --target-port 8000 \
    --min-replicas 0 --max-replicas 1 \
    --cpu 0.25 --memory 0.5Gi \
    --secrets "${SECRETS[@]}" --env-vars "${ENV_VARS[@]}" --output none
fi

az containerapp show --name "$APP" --resource-group "$RESOURCE_GROUP" \
  --query properties.configuration.ingress.fqdn --output tsv
