# RevTown API Policy
# Allows the API to read secrets for all rigs and services

# Read all revtown secrets
path "secret/data/revtown/*" {
  capabilities = ["read", "list"]
}

# Allow listing secret paths
path "secret/metadata/revtown/*" {
  capabilities = ["list"]
}

# Read Neurometric API credentials
path "secret/data/revtown/neurometric" {
  capabilities = ["read"]
}

# Read integration credentials
path "secret/data/revtown/integrations/*" {
  capabilities = ["read"]
}

# Read Stripe credentials (SaaS mode)
path "secret/data/revtown/stripe" {
  capabilities = ["read"]
}

# Read Twilio credentials (The Wire)
path "secret/data/revtown/twilio" {
  capabilities = ["read"]
}

# Read Vercel credentials (Landing Pad)
path "secret/data/revtown/vercel" {
  capabilities = ["read"]
}

# Read GitHub credentials (Repo Watch)
path "secret/data/revtown/github" {
  capabilities = ["read"]
}

# Read social media credentials
path "secret/data/revtown/social/*" {
  capabilities = ["read"]
}
