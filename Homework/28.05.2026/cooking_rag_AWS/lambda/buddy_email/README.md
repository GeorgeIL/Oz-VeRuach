# Buddy Email Lambda

Sends personalized recipe-share emails using Bedrock Nova Lite and Amazon SES.

## 1. Create IAM execution role (one-time)

Lambda needs a role with a **trust policy** allowing `lambda.amazonaws.com` to assume it.
If the role does not exist, `create-function` fails with *"The role defined for the function cannot be assumed by Lambda"*.

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws iam create-role \
  --role-name cooking-rag-lambda-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

aws iam put-role-policy \
  --role-name cooking-rag-lambda-role \
  --policy-name BuddyEmailPolicy \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [
      {
        \"Effect\": \"Allow\",
        \"Action\": [\"logs:CreateLogGroup\", \"logs:CreateLogStream\", \"logs:PutLogEvents\"],
        \"Resource\": \"arn:aws:logs:us-east-1:${ACCOUNT_ID}:*\"
      },
      {
        \"Effect\": \"Allow\",
        \"Action\": [\"bedrock:InvokeModel\", \"bedrock:Converse\"],
        \"Resource\": \"*\"
      },
      {
        \"Effect\": \"Allow\",
        \"Action\": [\"ses:SendEmail\", \"ses:SendRawEmail\"],
        \"Resource\": \"*\"
      }
    ]
  }"
```

Allow the EC2 app role to invoke this Lambda:

```bash
aws iam put-role-policy \
  --role-name cooking-rag-ec2-role \
  --policy-name InvokeBuddyEmailLambda \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:us-east-1:'"${ACCOUNT_ID}"':function:cooking-rag-buddy-email"
    }]
  }'
```

## 2. Build deployment package

```bash
cd lambda/buddy_email
pip install -r requirements.txt -t package/
cp handler.py package/
cd package && zip -r ../buddy_email.zip . && cd ..
```

## 3. Create the function

Do **not** set `AWS_REGION` in `--environment` — Lambda reserves that variable and sets it automatically from `--region`.

```bash
sleep 10   # brief wait after creating the IAM role

aws lambda create-function \
  --function-name cooking-rag-buddy-email \
  --runtime python3.11 \
  --handler handler.handler \
  --role arn:aws:iam::${ACCOUNT_ID}:role/cooking-rag-lambda-role \
  --zip-file fileb://buddy_email.zip \
  --environment "Variables={NOVA_MODEL_ID=amazon.nova-lite-v1:0,SES_FROM_EMAIL=glovatskyg@gmail.com}" \
  --timeout 60 \
  --region us-east-1
```

## 4. Test invoke

```bash
aws lambda invoke \
  --function-name cooking-rag-buddy-email \
  --payload '{"sender_name":"Giora","subject":"Test recipe","context":"Recipe: Apple Pie","buddies":[{"name":"Friend","email":"YOUR_VERIFIED_RECIPIENT@gmail.com"}]}' \
  --cli-binary-format raw-in-base64-out \
  response.json \
  --region us-east-1

cat response.json
```

## Flask configuration

Set in `.env` / `env.ec2`:

```
BUDDY_EMAIL_LAMBDA_NAME=cooking-rag-buddy-email
SES_FROM_EMAIL=glovatskyg@gmail.com
```

## SES setup

1. Verify sender email in Amazon SES.
2. In SES sandbox, also verify each recipient email used for testing.
