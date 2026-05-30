import json
import os

with open('tmp_keys/private_key.pem', 'r') as f:
    priv_key = f.read()

with open('tmp_keys/public_key.pem', 'r') as f:
    pub_key = f.read()

gcp_sa = {
    "type": "service_account",
    "project_id": "dummy-project",
    "private_key_id": "dummy",
    "private_key": priv_key,
    "client_email": "dummy@dummy-project.iam.gserviceaccount.com",
    "client_id": "123",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/dummy%40dummy-project.iam.gserviceaccount.com"
}

env_content = f"""POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=control_plane
POSTGRES_SSLMODE=disable

REDIS_URL=redis://localhost:6379/0

GCP_SERVICE_ACCOUNT_JSON={json.dumps(gcp_sa)}

JWT_PRIVATE_KEY="{priv_key.replace(chr(10), '\\n')}"
JWT_PUBLIC_KEY="{pub_key.replace(chr(10), '\\n')}"
JWT_ISSUER=control-plane
JWT_EXPIRATION_MINUTES=30

INTERNAL_API_KEY=your-internal-api-key

ENVIRONMENT=development
"""

with open('.env', 'w') as f:
    f.write(env_content)

print("Generated .env")
