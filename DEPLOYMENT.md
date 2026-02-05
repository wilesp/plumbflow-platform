# PRODUCTION DEPLOYMENT GUIDE

## 🚀 Deploying to Production

This guide covers deploying the plumber matching platform to a production environment.

---

## Option 1: AWS Deployment (Recommended)

### Architecture

```
                                ┌─────────────────┐
                                │   Route 53      │
                                │    (DNS)        │
                                └────────┬────────┘
                                         │
                                ┌────────▼────────┐
                                │  CloudFront     │
                                │    (CDN)        │
                                └────────┬────────┘
                                         │
                ┌────────────────────────┴─────────────────────┐
                │                                              │
        ┌───────▼────────┐                            ┌───────▼────────┐
        │   S3 Bucket    │                            │  Load Balancer │
        │  (Dashboard)   │                            │    (ALB)       │
        └────────────────┘                            └───────┬────────┘
                                                              │
                                                    ┌─────────┴────────┐
                                                    │                  │
                                            ┌───────▼──────┐   ┌──────▼───────┐
                                            │   EC2        │   │   EC2        │
                                            │ (Scraper)    │   │  (API)       │
                                            └───────┬──────┘   └──────┬───────┘
                                                    │                  │
                                            ┌───────▼──────────────────▼───────┐
                                            │         RDS PostgreSQL           │
                                            │         (Database)               │
                                            └──────────────────────────────────┘
```

### Step 1: Database (RDS)

```bash
# Create PostgreSQL RDS instance
aws rds create-db-instance \
  --db-instance-identifier plumber-platform-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username admin \
  --master-user-password <strong-password> \
  --allocated-storage 20 \
  --vpc-security-group-ids sg-xxxxx

# Get connection string
aws rds describe-db-instances \
  --db-instance-identifier plumber-platform-db \
  --query 'DBInstances[0].Endpoint.Address'

# Set environment variable
export DATABASE_URL=postgresql://admin:password@endpoint.rds.amazonaws.com:5432/plumber_platform

# Import schema
psql $DATABASE_URL < database_schema.sql
```

### Step 2: Application Server (EC2)

```bash
# Launch EC2 instance (Ubuntu 22.04)
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.small \
  --key-name your-key-pair \
  --security-group-ids sg-xxxxx

# SSH into instance
ssh -i your-key.pem ubuntu@ec2-xxx.compute.amazonaws.com

# Install dependencies
sudo apt update
sudo apt install python3.10 python3-pip postgresql-client

# Clone your repository
git clone https://github.com/yourusername/plumber-platform.git
cd plumber-platform

# Install Python packages
pip3 install -r requirements.txt

# Set environment variables
sudo nano /etc/environment
# Add:
DATABASE_URL=postgresql://...
OPENAI_API_KEY=sk-...
STRIPE_SECRET_KEY=sk_...
TWILIO_ACCOUNT_SID=AC...
# etc.

# Create systemd service
sudo nano /etc/systemd/system/plumber-platform.service
```

**Service File:**
```ini
[Unit]
Description=Plumber Platform
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/plumber-platform
Environment="PATH=/home/ubuntu/.local/bin:/usr/bin"
EnvironmentFile=/etc/environment
ExecStart=/usr/bin/python3 main_orchestrator.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Start service
sudo systemctl daemon-reload
sudo systemctl start plumber-platform
sudo systemctl enable plumber-platform

# Check status
sudo systemctl status plumber-platform

# View logs
sudo journalctl -u plumber-platform -f
```

### Step 3: Dashboard (S3 + CloudFront)

```bash
# Create S3 bucket
aws s3 mb s3://plumber-dashboard

# Upload dashboard
aws s3 cp plumber_dashboard.html s3://plumber-dashboard/index.html \
  --content-type text/html

# Make bucket public (website hosting)
aws s3 website s3://plumber-dashboard/ \
  --index-document index.html

# Create CloudFront distribution
aws cloudfront create-distribution \
  --origin-domain-name plumber-dashboard.s3.amazonaws.com \
  --default-root-object index.html
```

### Step 4: Monitoring & Alerts

**CloudWatch Alarms:**
```bash
# CPU alarm
aws cloudwatch put-metric-alarm \
  --alarm-name plumber-platform-high-cpu \
  --alarm-description "Alert if CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/EC2 \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# Database connections
aws cloudwatch put-metric-alarm \
  --alarm-name plumber-db-connections \
  --alarm-description "Too many DB connections" \
  --metric-name DatabaseConnections \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold
```

---

## Option 2: DigitalOcean Deployment (Simpler)

### Step 1: Create Droplet

```bash
# Create Ubuntu droplet (2GB RAM minimum)
doctl compute droplet create plumber-platform \
  --size s-2vcpu-2gb \
  --image ubuntu-22-04-x64 \
  --region lon1

# Get IP address
doctl compute droplet list

# SSH in
ssh root@<droplet-ip>
```

### Step 2: Setup Application

```bash
# Install dependencies
apt update
apt install python3.10 python3-pip postgresql git nginx

# Setup database
sudo -u postgres psql
CREATE DATABASE plumber_platform;
CREATE USER plumber WITH PASSWORD 'strong-password';
GRANT ALL PRIVILEGES ON DATABASE plumber_platform TO plumber;
\q

# Import schema
psql -U plumber -d plumber_platform < database_schema.sql

# Clone repository
git clone https://github.com/yourusername/plumber-platform.git
cd plumber-platform

# Install packages
pip3 install -r requirements.txt

# Create .env file
nano .env
# Add environment variables

# Setup supervisor (process manager)
apt install supervisor

nano /etc/supervisor/conf.d/plumber-platform.conf
```

**Supervisor Config:**
```ini
[program:plumber-platform]
command=/usr/bin/python3 /root/plumber-platform/main_orchestrator.py
directory=/root/plumber-platform
autostart=true
autorestart=true
stderr_logfile=/var/log/plumber-platform.err.log
stdout_logfile=/var/log/plumber-platform.out.log
environment=PATH="/usr/bin"
```

```bash
# Start supervisor
supervisorctl reread
supervisorctl update
supervisorctl start plumber-platform

# Check status
supervisorctl status plumber-platform
```

### Step 3: Setup Nginx (Reverse Proxy)

```bash
nano /etc/nginx/sites-available/plumber-dashboard
```

**Nginx Config:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        root /root/plumber-platform;
        index plumber_dashboard.html;
    }

    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Enable site
ln -s /etc/nginx/sites-available/plumber-dashboard /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

### Step 4: SSL Certificate (Let's Encrypt)

```bash
apt install certbot python3-certbot-nginx

# Get certificate
certbot --nginx -d your-domain.com

# Auto-renewal
certbot renew --dry-run
```

---

## Option 3: Heroku Deployment (Easiest)

### Step 1: Prepare Application

```bash
# Create Procfile
echo "worker: python main_orchestrator.py" > Procfile

# Create runtime.txt
echo "python-3.10.0" > runtime.txt

# Ensure requirements.txt is up to date
pip freeze > requirements.txt
```

### Step 2: Deploy to Heroku

```bash
# Install Heroku CLI
curl https://cli-assets.heroku.com/install.sh | sh

# Login
heroku login

# Create app
heroku create plumber-platform

# Add PostgreSQL addon
heroku addons:create heroku-postgresql:mini

# Set environment variables
heroku config:set OPENAI_API_KEY=sk-...
heroku config:set STRIPE_SECRET_KEY=sk_...
heroku config:set TWILIO_ACCOUNT_SID=AC...
# etc.

# Deploy
git init
git add .
git commit -m "Initial deployment"
git push heroku main

# Scale workers
heroku ps:scale worker=1

# View logs
heroku logs --tail
```

---

## Database Backups

### Automated Backups (AWS RDS)
```bash
# Enable automated backups
aws rds modify-db-instance \
  --db-instance-identifier plumber-platform-db \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00"
```

### Manual Backups (PostgreSQL)
```bash
# Backup database
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Restore from backup
psql $DATABASE_URL < backup_20240203.sql

# Automate with cron
crontab -e
# Add: 0 3 * * * pg_dump $DATABASE_URL > /backups/backup_$(date +\%Y\%m\%d).sql
```

---

## Monitoring & Logging

### Application Logging

```python
# Add to main_orchestrator.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/plumber-platform.log'),
        logging.StreamHandler()
    ]
)
```

### Error Tracking (Sentry)

```bash
pip install sentry-sdk

# Add to main_orchestrator.py
import sentry_sdk

sentry_sdk.init(
    dsn="https://...@sentry.io/...",
    traces_sample_rate=1.0
)
```

### Uptime Monitoring

**Recommended Services:**
- UptimeRobot (free)
- Pingdom
- New Relic
- DataDog

---

## Security Checklist

- [ ] All API keys in environment variables (not in code)
- [ ] Database has firewall (only allow app servers)
- [ ] SSL/TLS enabled on all endpoints
- [ ] Regular security updates (`apt update && apt upgrade`)
- [ ] Separate production and development databases
- [ ] Rotate API keys every 90 days
- [ ] Enable database encryption at rest
- [ ] Set up VPN for SSH access
- [ ] Implement rate limiting on APIs
- [ ] Regular penetration testing

---

## Performance Optimization

### Database Indexing
```sql
-- Already in schema, but verify:
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_postcode ON jobs(postcode);
CREATE INDEX idx_plumbers_postcode ON plumbers(base_postcode);
```

### Caching (Redis)
```bash
# Install Redis
apt install redis-server

# Python integration
pip install redis

# Cache plumber data
import redis
r = redis.Redis(host='localhost', port=6379)
r.setex('plumber:1', 3600, json.dumps(plumber_data))
```

### Connection Pooling
```python
# In database service
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=0
)
```

---

## Scaling Guidelines

### When to Scale

**Scale Database:** If queries take >500ms
- Upgrade RDS instance size
- Add read replicas
- Implement caching layer

**Scale Application:** If CPU >80% consistently
- Add more EC2 instances
- Set up auto-scaling group
- Use load balancer

**Scale Scraping:** If missing leads
- Run multiple scraper instances
- Distribute by platform (one instance per platform)
- Use job queue (Celery + RabbitMQ)

---

## Cost Estimates

### Monthly Operating Costs (500 jobs/month)

**AWS:**
- RDS (db.t3.micro): £15
- EC2 (t3.small): £15
- S3 + CloudFront: £5
- Data transfer: £10
- **Total: ~£45/month**

**DigitalOcean:**
- Droplet (2GB): £12
- Database: £15
- Backups: £3
- **Total: ~£30/month**

**Heroku:**
- Dyno (Standard-1X): £20
- PostgreSQL (Mini): £7
- **Total: ~£27/month**

**Third-Party Services:**
- Twilio (SMS): £100-300 (usage-based)
- SendGrid (Email): £15
- OpenAI (API): £50-150 (usage-based)
- **Total: ~£165-465/month**

**Grand Total: £200-500/month** for 500 jobs

---

## Launch Checklist

Pre-Launch:
- [ ] Database schema deployed
- [ ] All environment variables set
- [ ] Payment processing tested (Stripe test mode)
- [ ] Notification delivery tested
- [ ] 10 plumbers onboarded
- [ ] Legal documents ready (Terms, Privacy Policy)
- [ ] Support email set up

Launch Day:
- [ ] Switch Stripe to live mode
- [ ] Enable monitoring alerts
- [ ] Announce to plumbers
- [ ] Start with manual lead posting (not scraping)
- [ ] Monitor first 10 jobs closely

Post-Launch (Week 1):
- [ ] Daily check error logs
- [ ] Survey first customers
- [ ] Survey first plumbers
- [ ] Fix any critical bugs
- [ ] Optimize based on feedback

---

## Disaster Recovery Plan

**Scenario 1: Database Failure**
- Restore from latest RDS snapshot (5-15 min)
- Or restore from manual backup
- Update DATABASE_URL
- Restart application

**Scenario 2: Application Crash**
- Systemd auto-restarts service
- If persistent: SSH in, check logs
- Roll back to previous version if needed
- Scale horizontally (add instance)

**Scenario 3: Payment Processing Down**
- Stripe status: status.stripe.com
- Queue credit purchases for retry
- Notify plumbers of delay
- Switch to manual processing if needed

---

## Support & Maintenance

**Daily:**
- Check error logs
- Monitor credit balances (ensure plumbers have funds)
- Verify scraping is running

**Weekly:**
- Review performance metrics
- Check plumber satisfaction
- Update pricing if needed

**Monthly:**
- Database backup verification
- Security updates
- Financial reconciliation
- Performance optimization

**Quarterly:**
- Rotate API keys
- Review and update terms
- Penetration testing
- Feature planning

---

Good luck with your deployment! 🚀
