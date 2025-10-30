## Overview
This project extends a failover system with monitoring feature
## Features
- ✅ Custom Nginx logging with structured JSON output
- ✅ Real-time log monitoring for failover detection
- ✅ Error rate tracking over sliding windows
- ✅ Automated Slack alerts for operational events
- ✅ Zero-downtime failover between Blue and Green pools
- ✅ Comprehensive operator runbook

---

## Prerequisites
- Docker & Docker Compose installed
- Slack workspace with webhook access
- Basic understanding of Nginx reverse proxy
- The pre-built app images from docker hub
---

## Quick Start

### 1. Clone and Setup

```bash
# Create project directory
mkdir failover_with_nginx monitoring
cd failover_with_nginx monitoring
# Copy all provided files into this directory:
# - docker-compose.yml
# - nginx.conf.template
# - watcher.py
# - Dockerfile.watcher
# - requirements.txt
# - .env.example
# - runbook.md
```

### 2. Create Slack Webhook

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Create a new app or use existing
3. Enable **Incoming Webhooks**
4. Add webhook to your channel (e.g., `#alerts`)
5. Copy the webhook URL

### 3. Configure Environment

```bash
# Copy example env file
cp .env.example .env

<<<<<<< HEAD
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
=======
# Edit .env with your values
nano .env
```

Update these values in `.env`:
```env
BLUE_IMAGE=yimikaade/wonderful:blue
GREEN_IMAGE=yimikaade/wonderful:green
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### 4. Create Nginx Config Directory

```bash
# Create directory for Nginx template
mkdir -p nginx

# Move nginx.conf.template into nginx/ directory
mv nginx.conf.template nginx/
```

### 5. Start Services

```bash
# Start all containers
docker compose up -d

# Verify all containers are running
docker compose ps
```

Expected output:
```
NAME                    STATUS
app_blue               Up
app_green              Up
nginx                  Up
alert_watcher          Up
```

### 6. Verify Setup

```bash
# Test Nginx endpoint
curl -i http://localhost:8080/version

# You should see:
# HTTP/1.1 200 OK
# X-App-Pool: blue
# X-Release-Id: v1.0.0

# Check logs are being generated
docker compose logs nginx --tail=5

# Check watcher is monitoring
docker compose logs alert_watcher --tail=10
```

---

## Testing Failover

### Test 1: Manual Failover Detection

```bash
# 1. Start monitoring logs in one terminal
docker compose logs -f alert_watcher

# 2. In another terminal, trigger chaos on Blue
curl -X POST http://localhost:8081/chaos/start?mode=error

# 3. Make requests to trigger failover
for i in {1..10}; do 
  curl -i http://localhost:8080/version
  sleep 1
done

# 4. Check Slack for failover alert
# Expected: "🔄 Pool Failover: BLUE → GREEN"

# 5. Stop chaos
curl -X POST http://localhost:8081/chaos/stop

# 6. Make more requests to observe recovery
for i in {1..10}; do 
  curl -i http://localhost:8080/version
  sleep 1
done

# Expected: Failover back to BLUE
```

### Test 2: High Error Rate Alert

```bash
# 1. Trigger chaos
curl -X POST http://localhost:8081/chaos/start?mode=error

# 2. Generate many requests to accumulate errors
for i in {1..150}; do 
  curl -s http://localhost:8080/version > /dev/null
done

# 3. Check Slack for error rate alert
# Expected: "⚠️ High Error Rate: X.XX%"

# 4. Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```

---

## Viewing Logs

### Nginx Access Logs (Structured JSON)

```bash
# View raw logs
docker compose exec nginx tail -f /var/log/nginx/access.log

# Pretty-print with jq
docker compose exec nginx tail -f /var/log/nginx/access.log | jq
```

Example log entry:
```json
{
  "timestamp": "2025-10-30T15:30:45+00:00",
  "pool": "blue",
  "release": "v1.0.0",
  "upstream_status": "200",
  "upstream_addr": "172.18.0.3:8081",
  "request_time": "0.012",
  "upstream_response_time": "0.010",
  "status": "200",
  "method": "GET",
  "path": "/version",
  "remote_addr": "172.18.0.1"
}
```

### Alert Watcher Logs

```bash
# Follow watcher logs
docker compose logs -f alert_watcher

# View recent status
docker compose logs alert_watcher --tail=50
```

### App Container Logs

```bash
# Blue app logs
docker compose logs app_blue --tail=50

# Green app logs
docker compose logs app_green --tail=50

# Follow both
docker compose logs -f app_blue app_green
```

---
### Adjusting Thresholds

For more sensitive monitoring:
```bash
# Edit .env
ERROR_RATE_THRESHOLD=1  # Lower threshold
WINDOW_SIZE=100         # Smaller window
ALERT_COOLDOWN_SEC=180  # More frequent alerts
```

For less noisy monitoring:
```bash
ERROR_RATE_THRESHOLD=5  # Higher threshold
WINDOW_SIZE=500         # Larger window
ALERT_COOLDOWN_SEC=600  # Longer cooldown
```

---

## Troubleshooting

### No Slack Alerts Received

**Check webhook URL:**
```bash
docker compose exec alert_watcher env | grep SLACK_WEBHOOK_URL
```

**Test webhook manually:**
```bash
curl -X POST "YOUR_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test from Blue/Green monitoring"}'
```

**Check watcher logs:**
```bash
docker compose logs alert_watcher | grep -i slack
```

### Logs Not Being Written

**Check Nginx container:**
```bash
docker compose exec nginx ls -la /var/log/nginx/
```

**Check volume mount:**
```bash
docker volume inspect bluegreen-monitoring_nginx_logs
```

**Restart services:**
```bash
docker compose restart nginx alert_watcher
```

### Watcher Not Detecting Failovers

**Verify log format:**
```bash
docker compose exec nginx tail -1 /var/log/nginx/access.log | jq .pool
```

**Check watcher state:**
```bash
docker compose logs alert_watcher --tail=20
```

**Restart watcher:**
```bash
docker compose restart alert_watcher
```

### Containers Not Starting

**Check images:**
```bash
docker compose config
docker images | grep wonderful
```

**View startup logs:**
```bash
docker compose logs app_blue
docker compose logs app_green
```

**Rebuild watcher:**
```bash
docker compose build alert_watcher
docker compose up -d
```

---

## Manual Operations

### Restart All Services

```bash
docker compose restart
```

### Restart Specific Service

```bash
docker compose restart app_blue
docker compose restart nginx
docker compose restart alert_watcher
```

### View Real-Time Metrics

```bash
# Container resource usage
docker stats

# Request monitoring
watch -n 2 'curl -s http://localhost:8080/version | grep -o "X-App-Pool: [a-z]*"'
```

### Manual Pool Switch

```bash
# Edit .env
nano .env
# Change ACTIVE_POOL=blue to ACTIVE_POOL=green

# Apply changes
docker compose up -d nginx

# Verify
curl -i http://localhost:8080/version | grep X-App-Pool
```

### Stop All Services

```bash
docker compose down
```

### Clean Up Everything

```bash
# Stop and remove containers, volumes
docker compose down -v

# Remove images (if needed)
docker rmi yimikaade/wonderful:blue yimikaade/wonderful:green
```

---

## Project Structure

```
bluegreen-monitoring/
├── docker-compose.yml          # Service orchestration
├── nginx/
│   └── nginx.conf.template     # Nginx config with custom logging
├── watcher.py                  # Python log monitoring script
├── Dockerfile.watcher          # Watcher container definition
├── requirements.txt            # Python dependencies
├── .env.example                # Example environment variables
├── .env                        # Your environment variables (git-ignored)
├── runbook.md                  # Operator response guide
└── README.md                   # This file
```

---

## Operator Runbook

See [runbook.md](runbook.md) for detailed operational procedures including:
- How to respond to each alert type
- Investigation steps
- Recovery procedures
- Escalation guidelines
- Common issues and solutions

---
Example commands to generate these:
```bash
# Generate failover alert
curl -X POST http://localhost:8081/chaos/start?mode=error
for i in {1..10}; do curl http://localhost:8080/version; sleep 1; done
# Screenshot Slack message

# Generate error rate alert  
for i in {1..150}; do curl -s http://localhost:8080/version > /dev/null; done
# Screenshot Slack message

# View structured log
docker compose exec nginx tail -1 /var/log/nginx/access.log | jq
# Screenshot terminal output
```

---

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Nginx (8080)   │◄─────────┐
│  Reverse Proxy  │          │
└────────┬────────┘          │
         │                   │
    ┌────┴────┐         ┌────┴─────┐
    ▼         ▼         ▼          │
┌────────┐ ┌────────┐ ┌──────────┐│
│  Blue  │ │ Green  │ │  Log     ││
│  8081  │ │  8082  │ │  Watcher ││
└────────┘ └────────┘ └──────┬───┘│
                             │    │
                             ▼    │
                      ┌───────────┴┐
                      │   Slack    │
                      │   Alerts   │
                      └────────────┘
```

---

## FAQ

**Q: How long does failover take?**  
A: Typically 2-5 seconds after Nginx detects upstream failure.

**Q: Will I get an alert for every failover?**  
A: No, alerts respect the cooldown period (default 300 seconds).

**Q: Can I test without Slack?**  
A: Yes, leave `SLACK_WEBHOOK_URL` empty. Alerts will print to watcher logs.

**Q: How do I change the active pool manually?**  
A: Edit `ACTIVE_POOL` in `.env` and run `docker compose up -d nginx`.

**Q: Can I run this on Azure/AWS?**  
A: Yes, just ensure ports 8080, 8081, 8082 are accessible via NSG.

---

## Support

For issues:
- Check logs: `docker compose logs`
- Review runbook: `runbook.md`
- Verify configuration: `docker compose config`


>>>>>>> 9f5f473 (added script for monitoring and nginx build to overwrite default log storage location)
