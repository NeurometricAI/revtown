# Vault Server Configuration for RevTown

# Storage backend
storage "file" {
  path = "/vault/data"
}

# Listener configuration
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1  # Enable TLS in production
}

# API address
api_addr = "http://127.0.0.1:8200"

# Enable UI
ui = true

# Disable mlock for containers
disable_mlock = true

# Telemetry
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname          = true
}
