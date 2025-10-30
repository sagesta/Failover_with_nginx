# Operator Runbook: Blue/Green Deployment Alerts

## Overview
This runbook provides guidance for responding to alerts from the Blue/Green deployment monitoring system. All alerts are sent to the configured Slack channel.

---

## Alert Types

### 1. 🔄 Failover Event

**Alert Title:** `Pool Failover: BLUE → GREEN` (or vice versa)

**What It Means:**
- The primary application pool has failed or become unhealthy
- Nginx has automatically switched traffic to the backup pool
- Users are now being served by the backup instance

**Immediate Actions:**

1. **Acknowledge the alert** in Slack to let the team know you're investigating

2. **Check the failed pool's status:**
   ```bash
   # SSH to the deployment server
   ssh user@your-server
   
   # Check container status
   docker compose ps
   
   # View logs of the failed pool (e.g., blue)
   docker compose logs --tail=100 app_blue
   ```

3. **Verify the backup pool is healthy:**
   ```bash
   # Test the backup endpoint directly
   curl -i http://localhost:8082/version
   
   # Check backup pool logs
   docker compose logs --tail=50 app_green
   ```

4. **Test the Nginx endpoint:**
   ```bash
   # Verify requests are being served
   curl -i http://localhost:8080/version
   
   # Check response headers
   # Should show X-App-Pool: green (backup pool)
   ```

**Investigation Steps:**

1. **Review failed pool logs for errors:**
   ```bash
   docker compose logs app_blue | grep -i error
   ```

2. **Check resource usage:**
   ```bash
   docker stats --no-stream
   ```

3. **Inspect Nginx error logs:**
   ```bash
   docker compose logs nginx | grep -i error
   ```

**Recovery Actions:**

**If primary pool crashed:**
```bash
# Restart the failed container
docker compose restart app_blue

# Wait 10 seconds for startup
sleep 10

# Verify it's healthy
curl -i http://localhost:8081/version
curl -i http://localhost:8081/healthz
```

**If primary pool is responding but degraded:**
```bash
# Stop chaos mode if it was triggered
curl -X POST http://localhost:8081/chaos/stop

# Monitor for recovery
watch -n 2 'curl -s http://localhost:8080/version | grep -o "X-App-Pool: [a-z]*"'
```

**Expected Recovery Time:** 5-30 seconds for automatic failback after primary recovers

---

### 2. ⚠️ High Error Rate

**Alert Title:** `High Error Rate: X.XX%`

**What It Means:**
- More than the configured threshold (default: 2%) of recent requests returned 5xx errors
- This is measured over a sliding window (default: last 200 requests)
- The application may be experiencing issues even without full failover

**Immediate Actions:**

1. **Check which pool is currently active:**
   ```bash
   curl -i http://localhost:8080/version | grep X-App-Pool
   ```

2. **Review recent Nginx logs:**
   ```bash
   docker compose logs nginx --tail=50
   ```

3. **Check application logs for the active pool:**
   ```bash
   # If blue is active
   docker compose logs app_blue --tail=100 | grep -i "error\|exception\|fail"
   
   # If green is active
   docker compose logs app_green --tail=100 | grep -i "error\|exception\|fail"
   ```

**Investigation Steps:**

1. **Identify error patterns:**
   ```bash
   # View Nginx access logs
   tail -100 /var/log/nginx/access.log | jq '.upstream_status' | sort | uniq -c
   ```

2. **Check for resource constraints:**
   ```bash
   # Memory and CPU usage
   docker stats --no-stream
   
   # Disk space
   df -h
   ```

3. **Test specific endpoints:**
   ```bash
   # Test the endpoint directly
   curl -v http://localhost:8081/version
   curl -v http://localhost:8082/version
   ```

**Recovery Actions:**

**If errors are transient (load spike):**
```bash
# Monitor for self-recovery
watch -n 5 'docker compose logs alert_watcher --tail=5'
```

**If errors persist:**
```bash
# Consider manual failover to the other pool
# Edit .env
nano .env
# Change ACTIVE_POOL to the other pool

# Restart to apply
docker compose up -d nginx
```

**If both pools are failing:**
```bash
# Check external dependencies (database, APIs, etc.)
# Review application environment variables
docker compose config

# Consider rollback to previous image version
# Edit .env
nano .env
# Change BLUE_IMAGE or GREEN_IMAGE to previous version

# Restart
docker compose up -d
```

**Expected Recovery Time:** Varies based on root cause (5 seconds to 5 minutes)

---

### 3. ✅ Recovery / Stabilization

**What It Means:**
- Error rate has dropped below threshold
- System has returned to normal operation
- No immediate action required

**Recommended Actions:**

1. **Verify sustained stability:**
   ```bash
   # Monitor for 5 minutes
   watch -n 10 'curl -s http://localhost:8080/version'
   ```

2. **Review incident timeline:**
   ```bash
   # Check logs around the incident time
   docker compose logs --since 30m
   ```

3. **Document the incident:**
   - What triggered the alert?
   - How long was the degradation?
   - What was the resolution?
   - Any follow-up actions needed?

---

## Maintenance Mode

### Suppress Alerts During Planned Maintenance

**Before starting maintenance:**
```bash
# Set high threshold to prevent false alerts
sed -i 's/ERROR_RATE_THRESHOLD=2/ERROR_RATE_THRESHOLD=99/' .env

# Restart watcher
docker compose up -d alert_watcher
```

**After maintenance:**
```bash
# Restore original threshold
git checkout .env

# Restart watcher
docker compose up -d alert_watcher
```

---

## Manual Failover (Planned Switch)

**To switch from Blue to Green:**
```bash
# Edit .env
nano .env
# Change: ACTIVE_POOL=blue to ACTIVE_POOL=green

# Reload Nginx config
docker compose up -d nginx

# Verify switch
curl -i http://localhost:8080/version | grep X-App-Pool
```

**To switch from Green to Blue:**
```bash
# Edit .env
nano .env
# Change: ACTIVE_POOL=green to ACTIVE_POOL=blue

# Reload Nginx config
docker compose up -d nginx

# Verify switch
curl -i http://localhost:8080/version | grep X-App-Pool
```

---

## Testing Failover

### Simulate Blue Failure

```bash
# Trigger chaos mode on Blue
curl -X POST http://localhost:8081/chaos/start?mode=error

# Make requests to observe failover
for i in {1..10}; do curl -i http://localhost:8080/version; done

# Check Slack for failover alert

# Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```

### Simulate High Error Rate

```bash
# Start chaos on active pool
curl -X POST http://localhost:8081/chaos/start?mode=error

# Generate traffic to trigger threshold
for i in {1..100}; do 
  curl -s http://localhost:8080/version > /dev/null
done

# Check Slack for error rate alert

# Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```

---

## Common Issues

### Alert Not Received in Slack

**Check webhook configuration:**
```bash
# Verify webhook URL is set
docker compose exec alert_watcher env | grep SLACK_WEBHOOK_URL

# Check watcher logs
docker compose logs alert_watcher --tail=50
```

**Test webhook manually:**
```bash
curl -X POST "$SLACK_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test alert from Blue/Green monitoring"}'
```

### Failover Not Detected

**Check Nginx logging:**
```bash
# Verify logs are being written
tail -f /var/log/nginx/access.log

# Check log format
docker compose exec nginx cat /etc/nginx/nginx.conf | grep log_format
```

**Verify watcher is running:**
```bash
docker compose ps alert_watcher
docker compose logs alert_watcher --tail=20
```

### False Positive Alerts

**Adjust thresholds:**
```bash
# Edit .env
nano .env

# Increase ERROR_RATE_THRESHOLD (e.g., from 2 to 5)
# Increase ALERT_COOLDOWN_SEC (e.g., from 300 to 600)

# Restart watcher
docker compose up -d alert_watcher
```

---

## Escalation

### When to Escalate

- Multiple failovers within 15 minutes
- Both pools showing high error rates
- Unable to restore service within 10 minutes
- Suspected security incident or DDoS

### Escalation Contacts

- **DevOps Team Lead:** [Name/Contact]
- **On-Call Engineer:** [Pager/Phone]
- **Infrastructure Team:** [Slack Channel]

---

## Useful Commands Cheat Sheet

```bash
# View all container status
docker compose ps

# View all logs
docker compose logs --follow

# Restart specific service
docker compose restart app_blue

# View Nginx access logs
tail -f /var/log/nginx/access.log | jq

# Test endpoint with headers
curl -i http://localhost:8080/version

# Check pool in use
curl -s http://localhost:8080/version | grep -o 'X-App-Pool: [a-z]*'

# Trigger chaos
curl -X POST http://localhost:8081/chaos/start?mode=error

# Stop chaos
curl -X POST http://localhost:8081/chaos/stop

# Manual failover (edit ACTIVE_POOL in .env, then)
docker compose up -d nginx

# Check error rate
docker compose logs alert_watcher | grep ERROR_RATE
```

---

## Monitoring Dashboard

Check these metrics regularly:
- **Request success rate:** Should be >99.5%
- **Active pool:** Blue or Green
- **Response time:** Should be <500ms p95
- **Container health:** All containers UP
- **Error rate:** <1%

---

## Post-Incident Review

After resolving an incident, document:
1. **Root cause:** What triggered the alert?
2. **Detection time:** How long to detect?
3. **Resolution time:** How long to resolve?
4. **Action items:** What can prevent recurrence?

Share findings in your team's incident review process.
