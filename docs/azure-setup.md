# One-time Azure setup

Everything here is done **once**, by hand, in my own *Azure for Students* subscription. After
that, nothing is changed by hand: every deploy is done by `.github/workflows/cd.yml`.

What this creates. Everything is in one resource group, and nothing else is in it:

```
resource group rg-<prefix>
 ├─ storage account <prefix without hyphens>ui    static website: the UI (the public URL)
 ├─ managed identity <prefix>-github              the pipeline signs in as it (OIDC)
 ├─ Container Apps environment <prefix>-env
 │     ├─ Container App <prefix>-scheduling
 │     └─ Container App <prefix>-bookings
 ├─ Log Analytics workspace                       the containers' logs (created with the environment)
 └─ SQL server <prefix>-sql-denmarkeast (see step 4 for why this name)
       ├─ database <prefix>-scheduling-db         serverless, 60-minute auto-pause
       └─ database <prefix>-bookings-db           serverless, 60-minute auto-pause
```

## 0. Where to run the commands

All commands are Bash, run in **Azure Cloud Shell**, which already has `az`, `sqlcmd` and
`curl` and is already signed in: go to <https://portal.azure.com>, click the `>_` icon in the
top bar, choose **Bash**, and when asked about storage choose **No storage account required**
(so Cloud Shell doesn't create a storage account outside my resource group).

Cloud Shell forgets variables when it times out. If that happens, run the block in step 1 again.

## 1. Subscription, names and region

```bash
az account list --output table      # find the Azure for Students subscription that is Enabled
az account set --subscription "<its SubscriptionId>"

PREFIX=jsmith-ieu2023               # my IE username, dots replaced by hyphens
RG=rg-$PREFIX
UI_STORAGE=$(echo $PREFIX | tr -d '-')ui
GH_REPO=<github-user>/<repo>        # e.g. megha368/Gym

# My subscription only allows five regions. List them, and pick one for everything:
az policy assignment list --query "[].{policy:displayName, regions:parameters.listOfAllowedLocations.value}" --output json
LOCATION=<one region from that list, e.g. westeurope>
```

## 2. Providers and resource group

```bash
for provider in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
  az provider register --namespace $provider
done
# Registering takes a few minutes. Repeat this until all five say "Registered":
for provider in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
  echo "$provider: $(az provider show --namespace $provider --query registrationState --output tsv)"
done

az group create --name $RG --location $LOCATION
```

## 3. The UI: a storage static website

```bash
az storage account create --name $UI_STORAGE --resource-group $RG --location $LOCATION \
  --kind StorageV2 --sku Standard_LRS
az storage blob service-properties update --account-name $UI_STORAGE \
  --static-website --index-document index.html
az storage account show --name $UI_STORAGE --resource-group $RG --query primaryEndpoints.web --output tsv
```

The last command prints the website's address (`https://<name>.z<N>.web.core.windows.net/`):
the system's public URL, and the only origin the services accept (CORS). If the storage name
is taken, add a digit to `UI_STORAGE` and repeat.

## 4. SQL server, two serverless databases, one user per database

Note: creating the server failed with `RegionDoesNotAllowProvisioning` in switzerlandnorth,
germanywestcentral, polandcentral and norwayeast ("not accepting creation of new ... SQL
Database servers at this time"), and each failed attempt left its name reserved in the region
that refused it. So each region was tried with its own name, `<prefix>-sql-<region>`, and the
server is `<prefix>-sql-denmarkeast`, in denmarkeast. The rest of the system is in
switzerlandnorth; the services reach the database by name, so the region makes no difference.

Choose three passwords (letters, digits and `_` only, since they go inside connection URLs; at
least 12 characters with upper case, lower case and digits) and keep them in a password manager.
The admin password is never stored anywhere else.

```bash
SQL_ADMIN=gymadmin
SQL_ADMIN_PASSWORD='...'
SCHEDULING_DB_PASSWORD='...'
BOOKINGS_DB_PASSWORD='...'
SQL_LOCATION=denmarkeast              # the only region of my list accepting new SQL servers
SQL_SERVER=$PREFIX-sql-$SQL_LOCATION  # see the note above

az sql server create --name $SQL_SERVER --resource-group $RG --location $SQL_LOCATION \
  --admin-user $SQL_ADMIN --admin-password "$SQL_ADMIN_PASSWORD"

# Allow Azure services (the Container Apps). 0.0.0.0 here is Azure's special rule, not "everyone".
az sql server firewall-rule create --resource-group $RG --server $SQL_SERVER \
  --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0

# denmarkeast doesn't support the free offer ("Provisioning of free limit database is not
# supported ... for region"), so: serverless without it, pausing after 60 minutes, 2 GB
# (15 minutes is refused for this size: "does not support auto pause delay value 15").
# It only charges while awake, plus storage; paid from the Azure for Students credit.
for service in scheduling bookings; do
  az sql db create --resource-group $RG --server $SQL_SERVER --name $PREFIX-$service-db \
    --edition GeneralPurpose --compute-model Serverless --family Gen5 \
    --min-capacity 0.5 --capacity 1 \
    --auto-pause-delay 60 --max-size 2GB \
    --backup-storage-redundancy Local
done
```

(Where the free offer is available, use `--use-free-limit true --free-limit-exhaustion-behavior
AutoPause` instead of `--auto-pause-delay` and `--max-size`, which the free offer fixes.)

One *contained* user per database: it exists only inside its own database, so it can't reach
the other one. Its roles let it read, write and run migrations (create and change tables).
For this, the firewall is opened to Cloud Shell's address, then closed again:

```bash
MY_IP=$(curl -s https://api.ipify.org)
az sql server firewall-rule create --resource-group $RG --server $SQL_SERVER \
  --name setup-temporary --start-ip-address $MY_IP --end-ip-address $MY_IP

sqlcmd -S tcp:$SQL_SERVER.database.windows.net,1433 -d $PREFIX-scheduling-db \
  -U $SQL_ADMIN -P "$SQL_ADMIN_PASSWORD" -l 60 -Q "
  CREATE USER scheduling_user WITH PASSWORD = '$SCHEDULING_DB_PASSWORD';
  ALTER ROLE db_ddladmin ADD MEMBER scheduling_user;
  ALTER ROLE db_datareader ADD MEMBER scheduling_user;
  ALTER ROLE db_datawriter ADD MEMBER scheduling_user;"

sqlcmd -S tcp:$SQL_SERVER.database.windows.net,1433 -d $PREFIX-bookings-db \
  -U $SQL_ADMIN -P "$SQL_ADMIN_PASSWORD" -l 60 -Q "
  CREATE USER bookings_user WITH PASSWORD = '$BOOKINGS_DB_PASSWORD';
  ALTER ROLE db_ddladmin ADD MEMBER bookings_user;
  ALTER ROLE db_datareader ADD MEMBER bookings_user;
  ALTER ROLE db_datawriter ADD MEMBER bookings_user;"

az sql server firewall-rule delete --resource-group $RG --server $SQL_SERVER --name setup-temporary
```

## 5. Container Apps

```bash
az extension add --name containerapp --upgrade
az containerapp env create --name $PREFIX-env --resource-group $RG --location $LOCATION

for service in scheduling bookings; do
  az containerapp create --name $PREFIX-$service --resource-group $RG --environment $PREFIX-env \
    --image mcr.microsoft.com/k8se/quickstart:latest \
    --ingress external --target-port 8000 \
    --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi
done
```

They start with Microsoft's placeholder image. The first deploy replaces it with mine and sets
their configuration: the database URL (and Bookings' token key) as Container Apps *secrets*
passed with `secretref:`, and Scheduling's URL, the UI's address for CORS and the timeouts as
plain environment variables (see `cd.yml`). CORS is done by my code, not by Container Apps'
ingress CORS setting, which stays off.

## 6. The pipeline's identity (OIDC, no password)

A user-assigned managed identity with Contributor on my resource group only. GitHub signs in
as it by proving which repository and branch is asking (a *federated credential*), so no Azure
password is stored anywhere.

```bash
az identity create --name $PREFIX-github --resource-group $RG --location $LOCATION
PRINCIPAL_ID=$(az identity show --name $PREFIX-github --resource-group $RG --query principalId --output tsv)
az role assignment create --assignee-object-id $PRINCIPAL_ID --assignee-principal-type ServicePrincipal \
  --role Contributor --scope $(az group show --name $RG --query id --output tsv)

# Who may sign in as it: pushes to main of my repository. GitHub may send the subject with
# names or with numeric ids, so both are registered.
OWNER_ID=$(curl -s https://api.github.com/repos/${GH_REPO} | jq .owner.id)
REPO_ID=$(curl -s https://api.github.com/repos/${GH_REPO} | jq .id)
az identity federated-credential create --name github-main --identity-name $PREFIX-github \
  --resource-group $RG --issuer https://token.actions.githubusercontent.com \
  --audiences api://AzureADTokenExchange --subject "repo:${GH_REPO}:ref:refs/heads/main"
az identity federated-credential create --name github-main-ids --identity-name $PREFIX-github \
  --resource-group $RG --issuer https://token.actions.githubusercontent.com \
  --audiences api://AzureADTokenExchange \
  --subject "repo:${GH_REPO%%/*}@${OWNER_ID}/${GH_REPO##*/}@${REPO_ID}:ref:refs/heads/main"

# The values for step 7:
echo "AZURE_CLIENT_ID=$(az identity show --name $PREFIX-github --resource-group $RG --query clientId --output tsv)"
echo "AZURE_TENANT_ID=$(az account show --query tenantId --output tsv)"
echo "AZURE_SUBSCRIPTION_ID=$(az account show --query id --output tsv)"
```

The `${GH_REPO}` braces matter: in zsh, `$GH_REPO:r` would silently lose characters.

## 7. GitHub secrets and variables

In the repository: **Settings** → **Secrets and variables** → **Actions**.

**Secrets** tab, **New repository secret**, six of them:

| Name | Value |
|---|---|
| `AZURE_CLIENT_ID` | printed at the end of step 6 |
| `AZURE_TENANT_ID` | printed at the end of step 6 |
| `AZURE_SUBSCRIPTION_ID` | printed at the end of step 6 |
| `SCHEDULING_DB_PASSWORD` | scheduling_user's password from step 4 |
| `BOOKINGS_DB_PASSWORD` | bookings_user's password from step 4 |
| `BOOKINGS_SECRET_KEY` | a long random string: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |

**Variables** tab, **New repository variable**, four of them (not secret):

| Name | Value |
|---|---|
| `PREFIX` | my prefix, e.g. `jsmith-ieu2023` |
| `RESOURCE_GROUP` | `rg-<prefix>` |
| `UI_STORAGE` | the storage account name from step 3 |
| `SQL_SERVER` | the SQL server's name from step 4, without `.database.windows.net` |

No password is ever written in a file in the repository: `cd.yml` builds each database URL
from these at deploy time.

## 8. First deploy, and making the images public

Merge a pull request into `main`. `cd.yml` runs CI, pushes the images to
`ghcr.io/<github-user>/gym-scheduling` and `gym-bookings`, and deploys.

**The first deploy fails on purpose:** new GitHub packages are private, so Azure can't pull
them ("Authentication failed when pulling container image"). On GitHub: my profile picture →
**Your profile** → **Packages** → `gym-scheduling` → **Package settings** → **Change
visibility** → **Public**. Same for `gym-bookings`. Then on the failed run, **Re-run failed jobs**.

## 9. Read access for the professors

```bash
RG_ID=$(az group show --name $RG --query id --output tsv)
az role assignment create --assignee amartini@faculty.ie.edu --role Reader --scope $RG_ID
az role assignment create --assignee bserra@faculty.ie.edu --role Reader --scope $RG_ID
```

## Reading the logs

```bash
az containerapp logs show --name $PREFIX-bookings --resource-group $RG --follow
az containerapp logs show --name $PREFIX-bookings --resource-group $RG --type system   # start-up and probes
```

## Cleaning up (only after grades are published)

```bash
az group delete --name $RG --yes
```
