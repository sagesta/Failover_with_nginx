# Start services
docker compose up -d

# Verify Blue is active
curl http://localhost:8080/version
# Should return X-App-Pool: blue

# Trigger chaos on Blue
curl -X POST http://localhost:8081/chaos/start?mode=error

# Verify automatic failover to Green
curl http://localhost:8080/version
# Should now return X-App-Pool: green with 200 status
