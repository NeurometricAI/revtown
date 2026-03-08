# Polecat Policy
# Polecats have read-only access to specific credentials they need

# Read only the credentials for the specific rig
# Note: Polecats receive a token scoped to their rig
path "secret/data/revtown/rigs/+/credentials" {
  capabilities = ["read"]
}

# Read Neurometric credentials (all Polecats need this)
path "secret/data/revtown/neurometric" {
  capabilities = ["read"]
}

# Deny write access to all paths
path "secret/data/*" {
  capabilities = ["deny"]
}
