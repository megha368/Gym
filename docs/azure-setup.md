# One-time Azure setup

Everything here is done **once**, by hand, with my IE account. After that, nothing is created
or changed by hand: every deploy is done by the `deploy` job in
`.github/workflows/pipeline.yml` (it creates the two Container Apps on its first run and
updates them on every run after).

What this creates, all in the class resource group, all named with my prefix:

| Resource | Name | Why |
|---|---|---|
| Azure SQL logical server | `<prefix>-sql` | holds the two databases |
| Serverless SQL database | `<prefix>-scheduling-db` | Scheduling's data |
| Serverless SQL database | `<prefix>-bookings-db` | Bookings' data |
| Container Apps environment (Consumption) | `<prefix>-env` | where the two Container Apps run |
| Static Web App (Free) | `<prefix>-ui` | serves the UI; its URL is the public URL |

The two Container Apps (`<prefix>-scheduling`, `<prefix>-bookings`) are created by the pipeline.

## 0. Before starting

- **Prefix:** my IE username (the part of my IE email before `@`) with dots replaced by
  hyphens. Example: `jsmith.ieu2023@student.ie.edu` becomes `jsmith-ieu2023`.
- **Resource group:** my class's, already created: `rg-sdd-3a` or `rg-sdd-3b`. Never create
  a resource group.
- Choose three passwords now (only letters, digits and `_`, at least 12 characters, with upper
  case, lower case and digits, since they also go inside connection URLs):
  the **SQL admin** password, the **scheduling_user** password and the **bookings_user** password.
  Keep them in a password manager. The admin password is never stored anywhere else.

## 1. Open Azure Cloud Shell

Go to <https://portal.azure.com>, sign in with the IE account, click the **Cloud Shell** icon
(`>_`) in the top bar and choose **Bash**. It already has the Azure CLI (`az`) and `sqlcmd`.

Set the names once (change the first lines to my own values):

```bash
PREFIX=jsmith-ieu2023
RG=rg-sdd-3a
SQL_ADMIN=gymadmin
SQL_ADMIN_PASSWORD='ChooseAStrongOne_2026'
LOCATION=$(az group show --name $RG --query location --output tsv)
echo "Creating everything in $LOCATION"
```

## 2. SQL server and the two serverless databases

```bash
az sql server create --name $PREFIX-sql --resource-group $RG --location $LOCATION \
  --admin-user $SQL_ADMIN --admin-password "$SQL_ADMIN_PASSWORD"

# Firewall: allow Azure services (Container Apps, Cloud Shell) to connect.
# 0.0.0.0 - 0.0.0.0 is Azure's special rule meaning "Azure services", not "everyone".
az sql server firewall-rule create --resource-group $RG --server $PREFIX-sql \
  --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0

for service in scheduling bookings; do
  az sql db create --resource-group $RG --server $PREFIX-sql --name $PREFIX-$service-db \
    --edition GeneralPurpose --compute-model Serverless --family Gen5 \
    --min-capacity 0.5 --capacity 1 \
    --auto-pause-delay 15 \
    --max-size 2GB \
    --backup-storage-redundancy Local
done
```

`--auto-pause-delay 15` is the shortest delay Azure allows (in minutes). `--capacity 1` is
the maximum of 1 vCore and `--min-capacity 0.5` the minimum.

## 3. One login per service, each with access to its own database only

These are *contained database users*: the user exists only inside its own database, so
`scheduling_user` cannot even sign in to the bookings database. It is `db_owner` of its own
database because its migrations create and change tables.

```bash
SCHED_PASSWORD='ChooseAnother_2026'
BOOK_PASSWORD='AndAThird_2026'

sqlcmd -S $PREFIX-sql.database.windows.net -d $PREFIX-scheduling-db \
  -U $SQL_ADMIN -P "$SQL_ADMIN_PASSWORD" \
  -Q "CREATE USER scheduling_user WITH PASSWORD = '$SCHED_PASSWORD'; ALTER ROLE db_owner ADD MEMBER scheduling_user;"

sqlcmd -S $PREFIX-sql.database.windows.net -d $PREFIX-bookings-db \
  -U $SQL_ADMIN -P "$SQL_ADMIN_PASSWORD" \
  -Q "CREATE USER bookings_user WITH PASSWORD = '$BOOK_PASSWORD'; ALTER ROLE db_owner ADD MEMBER bookings_user;"
```

If `sqlcmd` is refused by the firewall, use the portal instead: open each database, click
**Query editor**, sign in as the SQL admin (accept the offer to add my IP to the firewall),
run the same two statements, then delete that IP rule again under the server's **Networking**
page, since my own IP is only allowed while I need it.

The first connection may take up to a minute: the database resumes from pause.

## 4. Container Apps environment (Consumption plan)

```bash
az extension add --name containerapp --upgrade
az containerapp env create --name $PREFIX-env --resource-group $RG --location $LOCATION \
  --logs-destination none
```

`--logs-destination none` stops Azure from creating a Log Analytics workspace, which would
not carry my prefix. The containers' output can still be streamed live with
`az containerapp logs show --name $PREFIX-bookings --resource-group $RG --follow`.

## 5. Static Web App for the UI

```bash
az staticwebapp create --name $PREFIX-ui --resource-group $RG --location westeurope --sku Free
az staticwebapp show --name $PREFIX-ui --resource-group $RG --query defaultHostname --output tsv
az staticwebapp secrets list --name $PREFIX-ui --resource-group $RG --query properties.apiKey --output tsv
```

The second command prints the UI's address (the system's public URL). The third prints its
**deployment token**, needed in step 7. (Static Web Apps only exists in a few regions, so it
uses `westeurope` even if the resource group is elsewhere; it only serves files.)

## 6. A token so Azure can pull the images from GitHub Container Registry

The images are pushed to `ghcr.io/<github-user>/gym-scheduling` and `gym-bookings`, which are
private. Azure needs a read-only token to pull them:

GitHub → my profile picture → **Settings** → **Developer settings** → **Personal access
tokens** → **Tokens (classic)** → **Generate new token (classic)**. Name `azure-ghcr-pull`,
expiration after grades are published, scope **only `read:packages`**. Copy the token.

## 7. GitHub Actions secrets

In the repository: **Settings** → **Secrets and variables** → **Actions** → **New repository
secret**. Create these six:

| Name | Value |
|---|---|
| `AZURE_CREDENTIALS` | the class service principal, as JSON: `{"clientId": "...", "clientSecret": "...", "subscriptionId": "...", "tenantId": "..."}` |
| `SCHEDULING_DATABASE_URL` | `mssql://scheduling_user:<SCHED_PASSWORD>@<prefix>-sql.database.windows.net:1433/<prefix>-scheduling-db` |
| `BOOKINGS_DATABASE_URL` | `mssql://bookings_user:<BOOK_PASSWORD>@<prefix>-sql.database.windows.net:1433/<prefix>-bookings-db` |
| `BOOKINGS_SECRET_KEY` | a long random string: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `SWA_DEPLOYMENT_TOKEN` | the deployment token from step 5 |
| `GHCR_PULL_TOKEN` | the token from step 6 |

Secrets are only readable by the workflow, never shown again, and the pipeline passes the
database URLs and the secret key to Container Apps as secrets, not as plain settings.

## 8. Fill in the names and deploy

In `.github/workflows/pipeline.yml`, set `PREFIX` and `RESOURCE_GROUP` at the top. Commit on
a branch, open a pull request, wait for CI, and merge. The merge to `main` runs the `deploy`
job: on this first run it creates both Container Apps, then checks their `/health` and
deploys the UI. The run's summary shows the URLs.

## Cleaning up (only after grades are published)

```bash
for app in scheduling bookings; do az containerapp delete --name $PREFIX-$app --resource-group $RG --yes; done
az containerapp env delete --name $PREFIX-env --resource-group $RG --yes
az staticwebapp delete --name $PREFIX-ui --resource-group $RG --yes
az sql server delete --name $PREFIX-sql --resource-group $RG --yes   # also deletes both databases
```
