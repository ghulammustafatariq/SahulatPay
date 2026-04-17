# SahulatPay — Backend Commands
## Project: FastAPI + PostgreSQL + Railway

---

## 1. First-Time Setup

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

---

## 2. Environment Variables

```bash
# Copy the example file and fill in your values
cp .env.example .env
```

Required values in `.env`:
```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
SECRET_KEY=your-secret-key-here
INFOBIP_API_KEY=your-infobip-key
INFOBIP_BASE_URL=https://xxxx.api.infobip.com
INFOBIP_SENDER_ID=SahulatPay
DEV_MODE=true
```

---

## 3. Database Migrations (Alembic)

```bash
# Create a new migration after changing models
alembic revision --autogenerate -m "description of change"

# Apply all pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1

# See current migration status
alembic current

# See migration history
alembic history
```

---

## 4. Run Development Server

```bash
# Run with auto-reload (development)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run without reload (production-like test)
uvicorn main:app --host 0.0.0.0 --port 8000
```

Access:
- API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 5. Test Auth Flow (Dev Mode)

```bash
# Get OTP without SMS (only works when DEV_MODE=true)
GET http://localhost:8000/auth/dev/otp/{phone_number}

# Register a test user
POST http://localhost:8000/api/v1/auth/register
{
  "phone_number": "03001234567",
  "email": "test@test.com",
  "full_name": "Test User",
  "password": "TestPass123",
  "country": "Pakistan",
  "account_type": "individual"
}

# Login
POST http://localhost:8000/api/v1/auth/login
{
  "phone_number": "03001234567",
  "password": "TestPass123"
}
```

---

## 6. Run Test Scripts

```bash
# Test auth flow end-to-end
python test_auth.py

# Verify complete user flow
python verify_flow.py

# Clean up test data
python cleanup_test.py
```

---

## 7. Railway Deployment

> ⚠️ **nixpacks fix**: `nixpacks.toml` uses `python3.11 -m pip install` instead of `pip install`.
> Bare `pip` is not on PATH in nix environment. Do NOT change it back to `pip`.



```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Deploy
railway up

# View logs
railway logs

# Open deployed URL
railway open
```

---

## 8. Useful pip Commands

```bash
# Freeze current packages to requirements.txt
pip freeze > requirements.txt

# Check for outdated packages
pip list --outdated

# Deactivate virtual environment
deactivate
```

---

## 9. Prompt Progress Tracker

| Prompt | Feature | Status |
|--------|---------|--------|
| PROMPT 01 | Project Setup | ✅ Done |
| PROMPT 02 | All DB Models (30 tables) | ✅ Done |
| PROMPT 03 | Auth Router + Service | ✅ Done |
| PROMPT 04 | Wallet Router | ✅ Done |
| PROMPT 05 | Cards Router | ✅ Done |
| PROMPT 05b | Card Subscriptions | ✅ Done |
| PROMPT 06 | Savings + Scheduler | ✅ Done |
| PROMPT 07 | Transactions Router | ✅ Done |
| PROMPT 08 | KYC Router | ✅ Done |
| PROMPT 09 | Finance Router | ✅ Done |
| PROMPT 10 | Splits + Trusted Circle | ✅ Done |
| PROMPT 11 | Rewards Router | ✅ Done |
| PROMPT 12 | AI / DeepSeek Router | ✅ Done |
| PROMPT 13 | Zakat + Notifications + FCM | ✅ Done |
| PROMPT 14 | Admin Router | ✅ Done |
| PROMPT 15 | Users Router (Profile, Devices, QR) | ✅ Done |
| PROMPT 16 | Banking Router | ✅ Done |
| PROMPT 17 | Security Hardening | ✅ Done |
| PROMPT 18 | Railway Deploy + Final | ✅ Done |

> Update status as you complete each prompt.
