# Jobs service on EC2

The full Compose file is `docker-compose.prod.yml`. IAM artifacts are
`ec2-trust-policy.json` and `jobs-dynamodb-policy.json`.
Postgres and auth-service are preserved exactly as supplied. No AWS account
commands were run; table existence, account ID, region and instance ID remain
unverified. Run AWS administration commands below from an authenticated admin
terminal, not using the restricted application role.

## Before deployment

- Replace the supplied auth image placeholder with the existing working server
  image. The current publish workflow resolves it to
  `ghcr.io/gauravdurge-2332/jobtracker/auth-service:latest`.
- The supplied auth database URL uses `postgresql://`, while requirements install
  `psycopg[binary]`. SQLAlchemy 2.0 defaults that URL to psycopg2; 2.1 changes the
  default to psycopg. If auth reports `No module named psycopg2`, explicitly use
  `postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/authentication`.
  This existing block was left unchanged as requested. See
  [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
  and [2.1](https://docs.sqlalchemy.org/en/21/dialects/postgresql.html).
- Set `AWS_REGION` in the server's existing protected `.env` to the actual target
  region (for example `ap-south-1`). Keep the existing secret values there.
  Do not add AWS access keys. Compose does not inject `.env` into containers
  wholesale: jobs receives only its three declared environment variables.
- Build and publish the changed jobs image through the existing main CI workflow
  before pulling on EC2. The old image still requires RabbitMQ and ListTables.
- Replace `<region>` and `<account-id>` in the permissions JSON before applying it.
  Do not apply the placeholder policy as-is.

## DynamoDB table

Set these non-secret administration variables to the actual values:

```bash
REGION='<region>'
INSTANCE_ID='<instance-id>'
```

Check the target account and table using admin credentials:

```bash
aws sts get-caller-identity
aws dynamodb describe-table --region "$REGION" --table-name jobs \
  --query 'Table.{Status:TableStatus,ARN:TableArn,Keys:KeySchema,Types:AttributeDefinitions,Billing:BillingModeSummary.BillingMode}'
```

Expected: the intended account, table status `ACTIVE`, `user_id` as `HASH` and
`id` as `RANGE`, both type `S`, billing `PAY_PER_REQUEST`. If it exists, do not
create it again. If and only if the second command returns
`ResourceNotFoundException`, create it with:

```bash
aws dynamodb create-table --region "$REGION" --table-name jobs \
  --attribute-definitions AttributeName=user_id,AttributeType=S AttributeName=id,AttributeType=S \
  --key-schema AttributeName=user_id,KeyType=HASH AttributeName=id,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST
aws dynamodb wait table-exists --region "$REGION" --table-name jobs
```

Creation returns table details; the waiter exits successfully without output.
AccessDenied or a connection error does not mean the table is missing. An
existing table with numeric keys needs a planned replacement/migration; do not
delete existing data or reinterpret the application's string keys.

Console: select the target region, open DynamoDB > Tables, look for `jobs`.
If missing, choose Create table; table name `jobs`, partition key `user_id`
(String), sort key `id` (String). Choose Customize settings and On-demand
capacity, then Create table. Wait for Active.
See [AWS table operations](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithTables.Basics.html).

## IAM role and instance profile

The permissions artifact grants only GetItem, PutItem, DeleteItem and Query on
the one table. Updates use PutItem; the code never uses UpdateItem or Scan.
Production startup no longer calls ListTables, CreateTable or DescribeTable.
No index access or wildcard resource is needed. See
[DynamoDB IAM actions](https://docs.aws.amazon.com/service-authorization/latest/reference/list_dynamodb.html).

Console:

1. IAM > Policies > Create policy > JSON: paste the permissions policy after
   replacing its region and account ID. Name it `jobtracker-jobs-dynamodb`.
2. IAM > Roles > Create role > AWS service > EC2. Attach that policy and name
   the role `jobtracker-ec2-role`. Verify the trust relationship matches the
   supplied EC2 trust policy. Console creation creates a same-name instance profile.
3. EC2 > Instances > select the running instance > Actions > Security > Modify
   IAM role > select `jobtracker-ec2-role` > Update IAM role.
   If another role is already attached, review its existing permissions before
   replacing it; replacing the role could break other workloads.

Equivalent CLI for a new role/profile (run where the JSON artifacts are stored):

```bash
aws iam create-role --role-name jobtracker-ec2-role \
  --assume-role-policy-document file://ec2-trust-policy.json
aws iam put-role-policy --role-name jobtracker-ec2-role \
  --policy-name jobs-dynamodb --policy-document file://jobs-dynamodb-policy.json
aws iam create-instance-profile --instance-profile-name jobtracker-ec2-role
aws iam add-role-to-instance-profile --instance-profile-name jobtracker-ec2-role \
  --role-name jobtracker-ec2-role
aws ec2 describe-iam-instance-profile-associations --region "$REGION" \
  --filters Name=instance-id,Values="$INSTANCE_ID"
# If there is no existing association:
aws ec2 associate-iam-instance-profile --region "$REGION" \
  --instance-id "$INSTANCE_ID" --iam-instance-profile Name=jobtracker-ec2-role
```

Expected: role/profile JSON, successful empty output from policy and membership
commands, then an association with state `associating` followed by `associated`.
IAM propagation can take time. If using the console path, skip the create CLI
commands. For an existing association, use the console replacement path above;
do not blindly attempt a second association.
See [instance profiles](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_switch-role-ec2_instance-profiles.html)
and [attaching roles](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/attach-iam-role.html).

## Verify on the server

From `~/jobtracker/`, after copying the Compose file, resolving the auth
placeholder and publishing the new jobs image:

1. Pull images:
   ```bash
   docker compose -f docker-compose.prod.yml pull
   ```
   Expected: all three images pulled or already up to date.
2. Start services:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```
   Expected: postgres, auth-service and jobs-service started/running.
3. Check state:
   ```bash
   docker compose -f docker-compose.prod.yml ps
   ```
   Expected: three services Up/running; postgres healthy. Jobs publishes 8001
   and auth publishes 8002; postgres has no host port.
4. Inspect jobs startup:
   ```bash
   docker compose -f docker-compose.prod.yml logs --tail=100 jobs-service
   curl -fsS http://localhost:8001/health
   ```
   Expected: application startup complete, Uvicorn listening on 8001, no stack
   traces; health returns `{"status":"ok"}`. Health alone does not check DynamoDB.
5. Check credentials and identity inside jobs:
   ```bash
   docker compose -f docker-compose.prod.yml exec -T jobs-service python -c 'import boto3, os; s=boto3.Session(); c=s.get_credentials(); assert c is not None, "No credentials"; assert c.method == "iam-role", c.method; print(s.client("sts", region_name=os.environ["AWS_REGION"]).get_caller_identity()["Arn"])'
   ```
   Expected: `arn:aws:sts::<account-id>:assumed-role/jobtracker-ec2-role/...`.
   No credentials or key material is printed. STS identity lookup needs no
   additional allow in this DynamoDB policy. If credentials cannot be found,
   confirm the role association and use this command in the admin terminal:
   ```bash
   aws ec2 modify-instance-metadata-options --region "$REGION" \
     --instance-id "$INSTANCE_ID" --http-endpoint enabled \
     --http-tokens required --http-put-response-hop-limit 2
   ```
   Expected: metadata options JSON, eventually state `applied`. Retry identity
   verification. Containers may need hop limit 2 for IMDSv2. See
   [AWS metadata guidance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instancedata-data-retrieval.html).
6. Sign up, log in, create and list a job. These are the real JSON routes; login
   is not an OAuth form. Choose a new email each time and enter a test password
   interactively; nothing is saved in a file:
   ```bash
   read -r -p 'New test email: ' TEST_EMAIL
   read -r -s -p 'Test password: ' TEST_PASSWORD
   printf '\n'
   AUTH_JSON=$(printf '%s\n%s' "$TEST_EMAIL" "$TEST_PASSWORD" | python3 -c 'import sys,json; email,password=sys.stdin.read().split("\n",1); print(json.dumps({"email":email,"password":password}))')
   printf '%s' "$AUTH_JSON" | curl -sS -w '\nHTTP %{http_code}\n' \
     -H 'Content-Type: application/json' --data-binary @- http://localhost:8002/auth/signup
   LOGIN_JSON=$(printf '%s' "$AUTH_JSON" | curl -fsS \
     -H 'Content-Type: application/json' --data-binary @- http://localhost:8002/auth/login)
   TOKEN=$(printf '%s' "$LOGIN_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
   unset TEST_PASSWORD AUTH_JSON LOGIN_JSON
   curl -sS -w '\nHTTP %{http_code}\n' -X POST http://localhost:8001/jobs \
     -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"company":"Example","role":"Backend Engineer","status":"Applied","note":"production smoke test"}'
   curl -sS -w '\nHTTP %{http_code}\n' http://localhost:8001/jobs \
     -H "Authorization: Bearer $TOKEN"
   ```
   Expected: signup HTTP 201 with user ID/email, login parsed successfully;
   create HTTP 201 with string UUID `id`; list HTTP 200 containing that job.
   Signup 409 means choose a different email, or log in with the existing account.
7. Negative tests, then restore auth:
   ```bash
   curl -sS -w '\nHTTP %{http_code}\n' http://localhost:8001/jobs \
     -H 'Authorization: Bearer not.a.jwt'
   docker compose -f docker-compose.prod.yml stop auth-service
   curl -sS -w '\nHTTP %{http_code}\n' http://localhost:8001/jobs \
     -H "Authorization: Bearer $TOKEN"
   docker compose -f docker-compose.prod.yml start auth-service
   curl --retry 5 --retry-connrefused --retry-delay 2 -fsS \
     -w '\nHTTP %{http_code}\n' http://localhost:8002/auth/verify \
     -H "Authorization: Bearer $TOKEN"
   unset TOKEN TEST_EMAIL
   ```
   Expected: bad token HTTP 401; stopped auth HTTP 503 with
   `Auth service unavailable`; auth starts again and verification returns the
   user's ID/email with HTTP 200.
   Test with a still-valid token (default lifetime is 30 minutes).

## Troubleshooting

| Failure | Check / fix |
|---|---|
| NoCredentialsError / Unable to locate credentials | Check the attached instance profile, IMDS endpoint enabled and hop limit 2. Remove static AWS credentials from the container; do not set AWS_EC2_METADATA_DISABLED. |
| AccessDeniedException | Match policy account/region/table ARN to the actual `jobs` table and `AWS_REGION`. Check the caller role, permission boundaries and organizational denies. A startup ListTables denial indicates an old image. |
| ResourceNotFoundException | Describe the table using admin credentials in the configured region. Create it only if missing and wait for Active. |
| ValidationException on keys | `user_id` and `id` must both be String (`S`). Existing numeric-key tables require migration/replacement; changing values alone does not change the schema. |
| Jobs cannot reach auth | Use `AUTH_SERVICE_URL=http://auth-service:8002`, with both containers on the Compose network. `localhost` points to the jobs container. Check auth logs. |
| No module named psycopg2 | Use an explicit `postgresql+psycopg://` auth URL for the installed psycopg3 driver. |
| Invalid auth image / failed pull | Resolve the provided placeholder to the actual GHCR image; verify that packages are public and the latest CI publish succeeded. |
| Out-of-memory kills | Run `sudo dmesg -T`, `free -h`, `docker stats --no-stream`, and `docker inspect "$(docker compose -f docker-compose.prod.yml ps -aq jobs-service)" --format '{{.State.OOMKilled}}'`. Verify swap, then adjust the affected service's mem_limit within instance capacity. |

## Environment and application changes

| Jobs variable | Production value | Source |
|---|---|---|
| AUTH_SERVICE_URL | `http://auth-service:8002` | `app/auth.py`: required environment lookup, then appends `/auth/verify`. |
| AWS_REGION | `${AWS_REGION}` from server `.env` | `app/dynamodb.py`: passed to boto3 `region_name`; default is ap-south-1. |
| JOBS_TABLE | `jobs` | `app/dynamodb.py`: table name lookup, default jobs. |
| DYNAMODB_ENDPOINT | Unset | `app/dynamodb.py`: optional endpoint; boto3 uses real AWS when absent. |
| RABBITMQ_URL | Unset for this stage | `app/events.py`: changed to optional lookup; local Compose still supplies it. |

No AWS keys, JWT secrets or database credentials are added to jobs. Auth secrets
remain referenced from the existing server `.env`.

Production blockers fixed with minimal changes:

- `app/main.py`: automatic table provisioning only when a local endpoint is set.
  Real AWS tables must be created separately. Close RabbitMQ only if connected.
- `app/events.py`: an unset/empty RabbitMQ URL disables its connection. A configured
  broker still must connect successfully; connection errors are not swallowed.
- `app/routes/jobs.py`: persist status updates without publishing when no broker
  is connected. Notifications for this stage are disabled and not queued for replay.

Both keys are strings: auth IDs are converted with `str(data["id"])` in
`app/auth.py`; job IDs are `str(uuid.uuid4())` in `app/routes/jobs.py`.

Assumptions: the Git remote is the repository whose workflow publishes these
images; GHCR packages are public as described; the supplied auth placeholders
will be resolved to the working server values. No region or account is inferred
for AWS actions. RabbitMQ, notification-service, security groups, CI deploy jobs,
the development Compose file and README are unchanged.
