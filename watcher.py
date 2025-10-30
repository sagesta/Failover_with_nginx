#!/usr/bin/env python3


import os
import json
import time
import requests
from collections import deque
from datetime import datetime

# Configuration from environment
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')
ERROR_RATE_THRESHOLD = float(os.getenv('ERROR_RATE_THRESHOLD', '2'))
WINDOW_SIZE = int(os.getenv('WINDOW_SIZE', '200'))
ALERT_COOLDOWN_SEC = int(os.getenv('ALERT_COOLDOWN_SEC', '300'))
LOG_FILE = '/var/log/nginx/access.log'

# State tracking
last_pool = None
error_window = deque(maxlen=WINDOW_SIZE)
last_alert_time = {}


def send_slack_alert(title, message, color='danger'):
    """Post formatted alert to Slack via webhook."""
    if not SLACK_WEBHOOK_URL:
        print(f"[WARN] SLACK_WEBHOOK_URL not set. Alert: {title}")
        print(f"[WARN] Message: {message}")
        return
    
    payload = {
        "attachments": [
            {
                "color": color,
                "title": title,
                "text": message,
                "footer": "Blue/Green Monitoring",
                "ts": int(time.time())
            }
        ]
    }
    
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL, 
            json=payload,
            timeout=10
        )
        if response.status_code == 200:
            print(f"[ALERT] ✅ Slack notification sent: {title}")
        else:
            print(f"[ERROR] Slack webhook failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[ERROR] Failed to send Slack alert: {e}")


def is_cooldown_expired(alert_type):
    """Check if cooldown has expired for this alert type."""
    last_time = last_alert_time.get(alert_type, 0)
    return (time.time() - last_time) > ALERT_COOLDOWN_SEC


def update_cooldown(alert_type):
    """Update cooldown timestamp."""
    last_alert_time[alert_type] = time.time()


def parse_log_line(line):
    """Parse JSON log line from Nginx."""
    try:
        data = json.loads(line.strip())
        return data
    except json.JSONDecodeError:
        return None


def check_failover(pool):
    """Detect and alert on pool transitions."""
    global last_pool
    
    if not pool or pool == 'unknown':
        return
    
    if last_pool is None:
        last_pool = pool
        print(f"[INFO] Initial pool detected: {pool.upper()}")
        return
    
    if pool != last_pool:
        if is_cooldown_expired('failover'):
            old_pool = last_pool
            message = (
                f"🚨 *Failover Detected*\n"
                f"• From: *{old_pool.upper()}*\n"
                f"• To: *{pool.upper()}*\n"
                f"• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"*Action Required:*\n"
                f"Check {old_pool} app health and logs."
            )
            send_slack_alert(
                f"🔄 Pool Failover: {old_pool.upper()} → {pool.upper()}",
                message,
                color='warning'
            )
            update_cooldown('failover')
            print(f"[FAILOVER] {old_pool.upper()} → {pool.upper()}")
        
        last_pool = pool


def check_error_rate():
    """Detect and alert on elevated error rates."""
    if len(error_window) < WINDOW_SIZE:
        return
    
    error_count = sum(1 for status in error_window if status >= 500)
    error_rate = (error_count / WINDOW_SIZE) * 100
    
    if error_rate > ERROR_RATE_THRESHOLD:
        if is_cooldown_expired('error_rate'):
            message = (
                f"🔴 *High Error Rate Detected*\n"
                f"• Current Rate: *{error_rate:.2f}%*\n"
                f"• Threshold: {ERROR_RATE_THRESHOLD}%\n"
                f"• Window: Last {WINDOW_SIZE} requests\n"
                f"• 5xx Errors: {error_count}\n"
                f"• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"*Action Required:*\n"
                f"Investigate upstream application logs and consider rollback."
            )
            send_slack_alert(
                f"⚠️ High Error Rate: {error_rate:.2f}%",
                message,
                color='danger'
            )
            update_cooldown('error_rate')
            print(f"[ERROR_RATE] {error_rate:.2f}% (threshold: {ERROR_RATE_THRESHOLD}%)")


def tail_file(file_path):
    """Tail a file and yield new lines."""
    while True:
        try:
            with open(file_path, 'r') as f:
                # Go to end of file
                f.seek(0, 2)
                print(f"[INFO] Started tailing {file_path}")
                
                while True:
                    line = f.readline()
                    if line:
                        yield line
                    else:
                        time.sleep(0.1)
        except FileNotFoundError:
            print(f"[WARN] Log file not found: {file_path}. Waiting...")
            time.sleep(2)
        except Exception as e:
            print(f"[ERROR] Error reading log file: {e}. Retrying...")
            time.sleep(2)


def main():
    """Main log watcher loop."""
    print("=" * 60)
    print("🔍 Nginx Blue/Green Log Watcher Starting")
    print("=" * 60)
    print(f"Error Rate Threshold: {ERROR_RATE_THRESHOLD}%")
    print(f"Window Size: {WINDOW_SIZE} requests")
    print(f"Alert Cooldown: {ALERT_COOLDOWN_SEC} seconds")
    print(f"Slack Webhook: {'✅ Configured' if SLACK_WEBHOOK_URL else '❌ Not configured'}")
    print(f"Log File: {LOG_FILE}")
    print("=" * 60)
    
    request_count = 0
    
    for line in tail_file(LOG_FILE):
        log_entry = parse_log_line(line)
        
        if not log_entry:
            continue
        
        request_count += 1
        
        # Extract fields
        pool = log_entry.get('pool', 'unknown')
        upstream_status = log_entry.get('upstream_status', '')
        status = log_entry.get('status', 200)
        path = log_entry.get('path', '')
        
        # Parse upstream_status (may be empty, "-", or a number)
        try:
            if upstream_status and upstream_status != '-':
                status_code = int(upstream_status)
            else:
                status_code = int(status)
        except (ValueError, TypeError):
            status_code = 200
        
        # Track status in rolling window
        error_window.append(status_code)
        
        # Check for failover
        check_failover(pool)
        
        # Check for error rate spike
        check_error_rate()
        
        # Log periodic status
        if request_count % 50 == 0:
            error_count = sum(1 for s in error_window if s >= 500)
            error_rate = (error_count / len(error_window)) * 100 if error_window else 0
            print(f"[STATUS] Requests: {request_count} | Pool: {pool} | Error Rate: {error_rate:.2f}%")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Log watcher stopped by user")
    except Exception as e:
        print(f"[FATAL] Unexpected error: {e}")
        raise
