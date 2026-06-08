# Smart Cookbook - RAG-Based Culinary Assistant

## Why This Project

Me and my girlfriend always found ourselves opening ChatGPT and asking things
like "what can we make with chicken, rice and onions?" or looking for new
recipes based on whatever we had at home. So when prompted to make a RAG web app
I thought - why not make the topic specifically for help in the kitchen?

So I built a RAG-based cooking assistant where users can upload or save recipe
sources, manage their own recipe collections, and ask natural questions about
meals they can make with the ingredients they already have or about recipes they
have saved / new ones. The app retrieves relevant recipes and cooking
information from its knowledge base and uses an LLM to generate personalized
recipes, suggestions and answers.

---

## Architecture

```
┌─────────────┐   JWT cookie    ┌───────────────────────────────────────────┐
│   Browser   │ ◄─────────────► │   Flask 3 (app.py)                        │
│ (HTML/CSS/  │                 │   Blueprints: /auth /recipes /chat /pantry│
│    JS)      │                 └──────────────────┬────────────────────────┘
└─────────────┘                                    │
                    ┌──────────────────────────────┼──────────────────────────┐
                    │                              │                          │
       ┌────────────▼────────────┐    ┌────────────▼──────────┐  ┌────────────▼──────────┐
       │  Aurora PostgreSQL 17   │    │   RAG Engine          │  │  Amazon Bedrock       │
       │  (AWS RDS)              │    │   (rag/engine.py)     │  │                       │
       │                         │    │                       │  │  Nova Lite 1.0 (LLM)  │
       │  users, recipes         │    │  1. retrieve_chunks() │  │  - Chat / RAG answers │
       │  conversations, messages│    │     via Bedrock KB    │  │  - Recipe parsing     │
       │  pantry, favorites      │    │  2. ask_chef()        │  │    from uploads       │
       │                         │    │     Converse API      │  └───────────────────────┘
       │  IAM token auth         │    │  3. sync_knowledge    │
       │  ThreadedConnectionPool │    │     _base() on upload │  ┌───────────────────────┐
       │  14-min token cache     │    └───────────────────────┘  │  Amazon S3            │
       └─────────────────────────┘                                                                                                │  recipes/catalog/*.md │
                                                                 │  recipes/<slug>.md    │
                                                                 │  (KB data source)     │
                                                                 └───────────────────────┘

Deployment: Docker container on EC2 Ubuntu 24.04 (t3.micro, 20 GB)
            IAM instance role → no credentials stored on the server
```

### Key Components

| Layer         | Technology                                 | Role                                                         |
| ------------- | ------------------------------------------ | ------------------------------------------------------------ |
| Web framework | Flask 3 + Blueprints                       | Routing, auth, template rendering                            |
| Database      | Aurora PostgreSQL 17 (AWS RDS)             | Users, recipes, conversations, messages, pantry, favorites   |
| DB auth       | IAM token (boto3 `generate_db_auth_token`) | No static passwords - tokens expire in 15 min, cached 14 min |
| Auth          | PyJWT + bcrypt                             | Stateless JWT tokens in httponly cookies                     |
| RAG retrieval | Amazon Bedrock Knowledge Base              | Semantic search over S3-stored recipe `.md` files            |
| LLM           | Amazon Nova Lite 1.0 (Bedrock)             | Chat answers, recipe generation, PDF parsing                 |
| File storage  | Amazon S3                                  | User-uploaded recipe markdown files                          |
| Frontend      | Jinja2 + vanilla JS + marked.js            | Chat UI, recipe CRUD, pantry management, dark mode           |
| Container     | Docker (python:3.11-slim)                  | Reproducible deployment                                      |
| Hosting       | EC2 Ubuntu 24.04 t3.micro                  | IAM instance role provides all AWS credentials               |

### Request Flow (Chat)

1. User sends a question → `/chat/ask`
2. `retrieve_chunks()` queries the Bedrock Knowledge Base with the question text
3. Relevant recipe chunks are returned as grounding context
4. `ask_chef()` calls `bedrock-runtime.converse()` with system prompt + history
   - chunks + pantry contents
5. Nova Lite generates a response; if it proposes a new recipe, a hidden
   `recipe-json` block is appended
6. The JS frontend detects the block, hides it, and shows an "Add to My
   Cookbook" button
7. Both messages are written to Aurora with `clock_timestamp()` to preserve
   order

---

## AWS Setup (one-time, before first deployment)

### 1 - Aurora PostgreSQL

1. Create an **Aurora PostgreSQL** cluster in RDS (Express Create is fine).
   Internet Access Gateway will be enabled automatically, which forces IAM
   database authentication - this is expected.
2. Note your **cluster writer endpoint** - looks like
   `database-1.cluster-<id>.us-east-1.rds.amazonaws.com`. **Use the cluster
   endpoint, not the instance endpoint** - IAM token auth from an EC2 role only
   validates against the cluster endpoint.
3. Apply the schema from your local machine (IAM admin credentials work):

```bash
cd cooking_rag
export AWS_ACCESS_KEY_ID=...   AWS_SECRET_ACCESS_KEY=...   AWS_REGION=us-east-1

python3 -c "
import boto3, psycopg2, pathlib
HOST = '<your-cluster-endpoint>'
token = boto3.client('rds', region_name='us-east-1').generate_db_auth_token(
    DBHostname=HOST, Port=5432, DBUsername='postgres')
conn = psycopg2.connect(host=HOST, port=5432, dbname='postgres',
    user='postgres', password=token, sslmode='require')
conn.cursor().execute(pathlib.Path('migrations/schema.sql').read_text())
conn.commit(); conn.close()
print('Schema applied!')
"
```

4. Grant the `rds_iam` role to the `postgres` user (connect as above and run
   `GRANT rds_iam TO postgres;`).

### 2 - Amazon S3

1. Create a bucket (e.g. `my-cooking-rag-bucket`).
2. Place your catalog CSV at `data/recipes.csv`.
3. Upload one Markdown file per recipe (recommended for RAG):

```bash
python3 scripts/csv_to_catalog_md.py --wipe-catalog
```

Use `--half --wipe-all-catalog` to rebuild with every other CSV row (~545 recipes) and
save `data/recipes_half.csv`. Recipe cards show a uniform thumbnail from the CSV
`img_src` column via `manifest.json`.

User-created recipes (manual entry, PDF upload, Chef AI save) get an AI-generated
photo in the background via **Google Gemini** (see [Recipe images](#recipe-images-gemini--s3) below).
You can override or remove images for any recipe from the recipe detail page.

This writes `recipes/catalog/{slug}.md` for every CSV row (~1100 files) using the
**recipe name** from the CSV (not the row index), plus `recipes/catalog/manifest.json`
for fast title/tag lookup in the app. Tags come from the CSV `cuisine_path` column.

All recipes — catalog CSV rows and user-created recipes (manual entry, PDF upload,
Chef AI save) — are stored under **`recipes/catalog/{slug}.md`**.

If you previously uploaded catalog files with numeric slugs (`0.md`, `1089.md`), run
with `--wipe-catalog` to remove those legacy files before re-uploading.

To move older user recipes from `recipes/{slug}.md` to the catalog prefix:

```bash
python3 scripts/migrate_recipes_to_catalog.py
```

4. Optional: `python3 scripts/generate_csv_summary.py` uploads a single
   `recipes/recipes-catalog-summary.md` with aggregate stats only. That file is
   **not** a substitute for per-recipe files when you want semantic search.

#### Public read for generated/uploaded images

Generated and uploaded recipe photos are stored at `recipes/catalog/images/{slug}.png`
(or `.jpg` / `.webp`). Add a bucket policy so browsers can load them directly:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadRecipeImages",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/recipes/catalog/images/*"
    }
  ]
}
```

Replace `YOUR_BUCKET_NAME` with your bucket (e.g. `us-bucket-giora`). If the bucket
uses **BucketOwnerEnforced** (ACLs disabled), the policy alone is enough — the app
falls back without `ACL=public-read` on upload.

### Recipe images (Gemini + S3)

When a user saves a new recipe (manual form, PDF upload, or Chef AI), the app:

1. Saves the recipe immediately and redirects
2. Spawns a background thread that calls Gemini to generate a food photo
3. Uploads the PNG to S3 and stores the public URL in Aurora (`recipe_images` table)

Catalog CSV recipes keep their manifest `img_src` URLs unless you override them.

**Environment variables** (add to `.env` locally and `env.ec2` on EC2 — do not commit
the API key):

```
GEMINI_API_KEY=<your_google_ai_studio_key>
GEMINI_MODEL=gemini-3.1-flash-image
```

If `GEMINI_API_KEY` is missing, recipes still save; no image is generated.

**Managing images:** On any recipe detail page, click **Manage image** to set an external
URL, upload a replacement, or remove the photo (with confirmation). Overrides are stored
in RDS and take precedence over catalog manifest URLs.

Apply the `recipe_images` table from `migrations/schema.sql` if upgrading an existing
database (the `CREATE TABLE IF NOT EXISTS` block is safe to re-run).

### 3 - Amazon Bedrock Knowledge Base

1. In the Bedrock console, **enable model access** for **Amazon Nova Lite 1.0**
   (`amazon.nova-lite-v1:0`).
2. Create a **Knowledge Base** with **one S3 data source** on the `recipes/`
   prefix (covers all `recipes/catalog/*.md` files).
3. Note the **Knowledge Base ID** and **Data Source ID** (short alphanumeric
   strings in the Bedrock console - not the S3 URL).
4. Sync the data source at least once before launching the app.
5. Set `BEDROCK_KB_SYNC_ALL=true` in `.env` / `env.ec2` so the app syncs every
   data source attached to the knowledge base (recommended if `BEDROCK_KB_DS_ID`
   is stale or you have multiple data sources). After rebuilding the catalog with
   `python3 scripts/csv_to_catalog_md.py --half --wipe-all-catalog` (or
   `--wipe-catalog`), trigger one ingestion job — upload any recipe or restart
   the app with sync enabled so Chef AI retrieval stays aligned with S3.

#### Knowledge base sync troubleshooting

| Symptom | Likely cause | Fix |
| ------- | ------------ | --- |
| `Failed to start knowledge base sync` with an AWS error in the alert | Wrong `BEDROCK_KB_ID` / `BEDROCK_KB_DS_ID` in `env.ec2` | Match IDs from the Bedrock console, or set `BEDROCK_KB_SYNC_ALL=true`; rebuild the Docker image after editing `env.ec2` |
| Sync says **already in progress** | A previous ingestion job is still running | Wait 1–3 minutes; the app retries on the next recipe upload or delete |
| Sidebar shows `0 catalog` recipes | Catalog `.md` files not uploaded yet | Run `python3 scripts/csv_to_catalog_md.py --wipe-catalog`, then wait for KB sync |
| Recipe titles show as numbers (`0`, `1089`) | Old upload used CSV row index as title | Re-run `csv_to_catalog_md.py --wipe-catalog` to rebuild with recipe names |
| Sidebar count looks like user recipes only | Old UI showed RDS count as “chunks” | After this update, the sidebar shows `catalog + yours` from S3 and RDS |
| Retrieval works but sync fails | IAM missing `bedrock-agent:StartIngestionJob` | Ensure the EC2 role includes Bedrock agent permissions |

### 4 - IAM role for EC2

```bash
# Create role
aws iam create-role --role-name cooking-rag-ec2-role \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]
  }'

# Attach managed policies
aws iam attach-role-policy --role-name cooking-rag-ec2-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
aws iam attach-role-policy --role-name cooking-rag-ec2-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
aws iam attach-role-policy --role-name cooking-rag-ec2-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonRDSFullAccess

# Inline policy for IAM DB auth - AmazonRDSFullAccess covers the management
# plane but rds-db:connect is required separately for token-based DB login
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws iam put-role-policy --role-name cooking-rag-ec2-role \
  --policy-name RdsIamConnect \
  --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"rds-db:connect\",\"Resource\":\"arn:aws:rds-db:us-east-1:${ACCOUNT_ID}:dbuser:*/postgres\"}]}"

# Create instance profile
aws iam create-instance-profile --instance-profile-name cooking-rag-ec2-profile
aws iam add-role-to-instance-profile \
  --instance-profile-name cooking-rag-ec2-profile \
  --role-name cooking-rag-ec2-role
```

### 5 - EC2 Security Group

```bash
SG_ID=$(aws ec2 create-security-group \
  --group-name cooking-rag-sg --description "Cooking RAG app" \
  --region us-east-1 --query 'GroupId' --output text)

aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 22   --cidr 0.0.0.0/0 --region us-east-1
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 5001 --cidr 0.0.0.0/0 --region us-east-1
echo "Security group: $SG_ID"
```

### 6 - Cooking Buddies email (optional)

Cooking buddies (name, email, picture URL) are stored in **Aurora PostgreSQL** only.
Profile pictures are external URLs — no S3 upload.

#### Prerequisites

1. Upload the catalog to S3: `python3 scripts/csv_to_catalog_md.py --wipe-catalog`
2. Verify a sender address in **Amazon SES** (`SES_FROM_EMAIL`)
3. Deploy the Lambda in [`lambda/buddy_email/`](lambda/buddy_email/) (see its README)
4. Grant the EC2 role `lambda:InvokeFunction` on the Lambda ARN
5. Add to `env.ec2`:

```
BUDDY_EMAIL_LAMBDA_NAME=cooking-rag-buddy-email
SES_FROM_EMAIL=you@your-verified-domain.com
```

6. Rebuild and redeploy the Docker image

#### Using Share a recipe

1. Add buddies at **/buddies/** (top nav)
2. In the **Share a recipe** section, click **Browse recipes** to pick from the full catalog (search by name or tag)
3. Choose buddies, add an optional personal note, and click **Send recipe email**
4. Bedrock Nova Lite composes the email body; SES delivers it

Recipe detail pages link to `/buddies/?recipe=<slug>` to pre-select a recipe.

#### Troubleshooting

| Issue | Fix |
| ----- | --- |
| Recipe list empty | Run `csv_to_catalog_md.py`; check `S3_BUCKET_NAME` and `recipes/` prefix |
| First search is slow | Normal — the app builds an S3 recipe index once, then caches it for 10 minutes |
| Email fails | Verify recipient in SES sandbox; check Lambda CloudWatch logs at `/aws/lambda/cooking-rag-buddy-email` |
| Email service not configured | Set `BUDDY_EMAIL_LAMBDA_NAME` and `SES_FROM_EMAIL` in `.env` / `env.ec2` and redeploy |

---

## Deploying to EC2 (Ubuntu)

### Step 1 - Create `env.ec2`

Create `env.ec2` in the project root. This is baked into the Docker image and
contains **no AWS credentials** - the EC2 instance role provides those via the
metadata service.

```
SECRET_KEY=<any_long_random_string>
AWS_REGION=us-east-1
BEDROCK_KB_ID=<your_kb_id>
BEDROCK_KB_DS_ID=<your_ds_id>
BEDROCK_KB_SYNC_ALL=true
# Optional: cooking buddies email via Lambda + SES
# BUDDY_EMAIL_LAMBDA_NAME=cooking-rag-buddy-email
# SES_FROM_EMAIL=you@verified-domain.com
# Optional: AI-generated recipe photos (do not commit the key)
# GEMINI_API_KEY=
# GEMINI_MODEL=gemini-3.1-flash-image
S3_BUCKET_NAME=<your_bucket_name>
S3_RECIPES_PREFIX=recipes/
RDS_HOST=<your_cluster_writer_endpoint>
RDS_PORT=5432
RDS_DB=postgres
RDS_USER=postgres
```

> Use the **cluster writer endpoint** (e.g.
> `database-1.cluster-<id>.us-east-1.rds.amazonaws.com`).

### Step 2 - Build and push the Docker image

Mac uses Apple Silicon (arm64) but EC2 runs amd64 - cross-compile with buildx:

```bash
docker buildx build \
  --platform linux/amd64 \
  -t <your-dockerhub-username>/cooking-rag:latest \
  --push .
```

You must be logged in (`docker login`) beforehand.

### Step 3 - Launch an Ubuntu EC2 instance

```bash
# Get latest Ubuntu 24.04 LTS AMI (Canonical account: 099720109477)
AMI_ID=$(aws ec2 describe-images \
  --owners 099720109477 \
  --filters \
    "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
    "Name=state,Values=available" \
  --query 'sort_by(Images,&CreationDate)[-1].ImageId' \
  --output text --region us-east-1)

INSTANCE_ID=$(aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type t3.micro \
  --key-name <your-key-pair-name> \
  --security-group-ids <your-sg-id> \
  --iam-instance-profile Name=cooking-rag-ec2-profile \
  --region us-east-1 \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":20,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=cooking-rag}]' \
  --query 'Instances[0].InstanceId' --output text)

echo "Instance: $INSTANCE_ID"
sleep 20
PUBLIC_IP=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "IP: $PUBLIC_IP"
```

### Step 4 - Install Docker on the instance

SSH in (Ubuntu default user is `ubuntu`, not `ec2-user`):

```bash
ssh -i ~/Downloads/<your-key>.pem ubuntu@<public-ip>
```

Then run:

```bash
# 1. Install prerequisites
sudo apt-get update
sudo apt-get install -y ca-certificates curl

# 2. Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# 3. Add Docker apt repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# 4. Install Docker
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

# 5. Verify Docker is running
sudo systemctl status docker
# If not running: sudo systemctl start docker

# 6. (Optional) Log in to Docker Hub to push images from this machine
docker login -u <your-dockerhub-username>
```

### Step 5 - Pull and run the container

```bash
sudo docker pull <your-dockerhub-username>/cooking-rag:latest
sudo docker run -d \
  --restart=always \
  -p 5001:5001 \
  --name cooking-rag \
  <your-dockerhub-username>/cooking-rag:latest
```

> No `--env-file` needed - config is baked into the image via `env.ec2`, and AWS
> credentials come from the instance IAM role automatically.

Wait ~10 seconds then check logs:

```bash
sudo docker logs cooking-rag --tail 20
```

App is live at **http://\<public-ip\>:5001**

### Step 6 - Updating after code changes

```bash
# On your local machine - rebuild and push
docker buildx build --platform linux/amd64 \
  -t <your-dockerhub-username>/cooking-rag:latest --push .

# On EC2 - pull and restart
ssh -i ~/Downloads/<your-key>.pem ubuntu@<public-ip> \
  "sudo docker pull <your-dockerhub-username>/cooking-rag:latest && \
   sudo docker stop cooking-rag && sudo docker rm cooking-rag && \
   sudo docker run -d --restart=always -p 5001:5001 --name cooking-rag \
     <your-dockerhub-username>/cooking-rag:latest"
```

---

## Local Development

### 1. Clone and configure

```bash
git clone <repository-url>
cd cooking_rag
```

Create `.env` (gitignored - never commit it):

```
SECRET_KEY=any_long_random_string
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=<your_iam_user_access_key>
AWS_SECRET_ACCESS_KEY=<your_iam_user_secret_key>
BEDROCK_KB_ID=<your_kb_id>
BEDROCK_KB_DS_ID=<your_ds_id>
BEDROCK_KB_SYNC_ALL=true
S3_BUCKET_NAME=<your_bucket_name>
S3_RECIPES_PREFIX=recipes/
RDS_HOST=<your_cluster_writer_endpoint>
RDS_PORT=5432
RDS_DB=postgres
RDS_USER=postgres
GEMINI_API_KEY=<your_google_ai_studio_key>
GEMINI_MODEL=gemini-3.1-flash-image
```

Upload the CSV catalog to S3 before testing RAG search:

```bash
python3 scripts/csv_to_catalog_md.py --wipe-catalog
```

The recipes page supports search by **recipe name or tag** (20 recipes per page).

### 2. Run locally via Docker

```bash
docker build -t cooking-rag .
docker run -p 5001:5001 --env-file .env cooking-rag
```

Open **http://localhost:5001**

### 3. Run without Docker

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

---

## Project Structure

```
cooking_rag_AWS/
├── app.py                  # Flask app factory, blueprints, error handlers
├── config.py               # All config loaded from .env
├── db.py                   # Aurora connection pool + IAM token cache
├── auth_utils.py           # JWT helpers
├── env.ec2                 # Non-secret config baked into EC2 Docker image
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── migrations/
│   └── schema.sql          # CREATE TABLE IF NOT EXISTS for all tables
├── rag/
│   ├── __init__.py
│   └── engine.py           # retrieve_chunks(), ask_chef(), sync_knowledge_base(), get_index_status()
├── routes/
│   ├── __init__.py
│   ├── auth.py
│   ├── chat.py
│   ├── recipes.py
│   ├── pantry.py
│   └── buddies.py
├── services/
│   ├── s3_recipes.py         # S3 recipe index + image URL resolution
│   └── recipe_images.py      # Gemini generation, S3 upload, image overrides
├── lambda/
│   └── buddy_email/        # Bedrock + SES email Lambda
├── scripts/
│   ├── csv_to_catalog_md.py      # One .md per CSV row → recipes/catalog/ + manifest
│   ├── migrate_recipes_to_catalog.py  # Move legacy user recipes into catalog/
│   └── generate_csv_summary.py   # Optional aggregate catalog summary only
├── static/                 # CSS + JS
├── templates/              # Jinja2 HTML
└── Pictures/               # Screenshots for documentation
```

---

## Reflection

### What Went Well

- **Full AWS stack migration** - successfully replaced MongoDB, Gemini,
  HuggingFace, and FAISS with Aurora PostgreSQL, Bedrock Nova Lite, Bedrock
  Knowledge Base, and S3 while keeping all app features intact.
- **IAM-based security** - no static credentials anywhere on the server; the EC2
  instance role provides AWS credentials automatically via the metadata service,
  and Aurora uses short-lived IAM tokens (14-min cache) instead of passwords.
- **Cross-platform Docker builds** - identified and solved the Apple Silicon
  arm64 vs EC2 amd64 mismatch using `docker buildx --platform linux/amd64`,
  which is now documented in the deployment guide.
- **Knowledge Base auto-sync** - every recipe upload or deletion triggers a
  Bedrock KB sync (`BEDROCK_KB_SYNC_ALL=true` syncs all data sources). Chef AI
  uses hybrid RAG: full S3 markdown for named recipes plus KB chunks for open
  questions, with expanded retrieval queries and full chat history.

### Challenges Encountered During the AWS Refactor

- **Docker platform mismatch** - the container started fine locally (arm64 Mac)
  but crashed silently on EC2 (amd64). The error only appeared in `docker logs`,
  not at pull time. Required rebuilding with
  `docker buildx build --platform linux/amd64`.
- **IAM auth routing - cluster vs instance endpoint** - Aurora's IAM token
  authentication from an EC2 role only validates against the **cluster writer
  endpoint**, not the individual instance endpoint. Using the instance endpoint
  returned "PAM authentication failed" with no further detail, which took
  considerable debugging to trace back to endpoint routing.
- **Missing `rds-db:connect` permission** - `AmazonRDSFullAccess` covers the AWS
  management plane (creating/modifying clusters) but does not grant
  database-level IAM login. A separate inline policy was required. The error
  message from psycopg2 looked identical to a wrong-password error, making it
  non-obvious that the problem was IAM policy, not credentials.

---

## Example Queries and Outputs

- Refer to the pictures provided via email.
