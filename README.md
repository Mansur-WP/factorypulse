# 🏭 FactoryPulse

## Manufacturing Fault Reporting & Maintenance Coordination

FactoryPulse is a lightweight manufacturing maintenance and fault-reporting platform designed for African factories. It enables shop-floor workers to report machine breakdowns and operational faults instantly without needing a smartphone or internet connection, while giving factory supervisors a centralized dashboard to track, assign, and resolve issues.

---

## 🚀 System Architecture

FactoryPulse uses a single, shared business logic layer across all interfaces:

```text
Shop-Floor Worker (USSD) ──┐
                           │
Developer / Tester (TG) ───┼──→ FactoryPulse Services (ussd/services.py) ──→ SQLite Database
                           │              │
Supervisor (Dashboard) ────┘              ↓
                              SMS Service (ussd/sms_service.py)
                                          ↓
                              Africa's Talking SMS API
                                          ↓
                              Technician Phone
```

---

## 📱 Features

### 1. 📞 Africa's Talking USSD Gateway (`POST /ussd/`)
- Interactive USSD menu (`*384*...#`).
- Fast, multi-step fault reporting (Machine → Problem → Severity → Confirmation).
- Session cancellation handling (`0` or `Cancel`).
- Cumulative session state parser with robust input validation.

### 2. 🤖 Telegram Development Bot (`run_telegram_bot`)
- Interactive Telegram interface mirroring the complete USSD flow with reply keyboards and numerical inputs.
- Custom problem descriptions ("Other" option).
- Machine status checking & isolated personal report history ("My Reports").

### 3. 🖥️ Supervisor Dashboard (`/dashboard/`)
- **Custom Login Portal**: Modern, responsive login page at `/dashboard/login/` (separate from Django Admin).
- **Protected Authentication**: Restricted to authenticated staff/admin accounts.
- **KPI Summary Cards**: Real-time counters for Total, Open, Critical, and Resolved faults.
- **Filterable Faults List**: Search by machine, problem, reporter, and filter by status, severity, and assigned technician.
- **Technician Assignment**: Assign faults to registered technicians with optional notes.
- **Fault Workflow Actions**: Strict state transitions (`OPEN` → `ASSIGNED` → `IN_PROGRESS` → `RESOLVED`).
- **Machine Management (`/dashboard/machines/`)**: View, add, and edit machines with operational statuses (`OPERATIONAL`, `MAINTENANCE`, `OFFLINE`) and fault histories.
- **Activity Feed**: Real-time log of recent reports and resolutions.

### 4. 👷 Technician Assignment & Two-Way SMS Workflow
- **Technician Model**: Registered technicians linked to Django users with phone numbers.
- **Assignment Workflow**: Supervisors assign faults to technicians via the dashboard (`OPEN` → `ASSIGNED`).
- **Outgoing SMS Notifications**: Automatic SMS sent to technician upon assignment.
- **Incoming SMS Responses** (`POST /sms/incoming/`): Technicians reply via SMS to progress assigned tasks:
  - `ACCEPT <id>`: `ASSIGNED` → `ACCEPTED`
  - `START <id>`: `ACCEPTED` → `IN_PROGRESS`
  - `RESOLVE <id>`: `IN_PROGRESS` → `RESOLVED`
- **SMS Security & Validation**: Phone matching prevents unauthorized modifications; invalid commands receive instructional replies.
- **SMS Delivery Callback** (`POST /sms/delivery/`): Webhook endpoint for Africa's Talking delivery status reports.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12+ (tested on 3.14), Django 5.2+
- **Database**: SQLite (Development / Production ready with PostgreSQL)
- **Interfaces**: Africa's Talking USSD API, Africa's Talking SMS API, Telegram Bot API (`python-telegram-bot`)
- **SMS**: Direct REST API integration via Python stdlib `http.client` (bypasses SDK SSL issues on Python 3.14)
- **Frontend**: Django Templates & Vanilla CSS (Responsive, no heavy frontend frameworks)
- **Environment**: `python-dotenv`

---

## 📂 Project Structure

```text
FactoryPulse/
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── ussd/
│   ├── migrations/
│   ├── static/ussd/
│   │   └── dashboard.css          # Dashboard styling
│   ├── templates/ussd/
│   │   ├── dashboard_base.html
│   │   ├── dashboard_home.html
│   │   ├── dashboard_faults.html
│   │   ├── dashboard_fault_detail.html
│   │   ├── dashboard_login.html
│   │   ├── dashboard_machines.html
│   │   └── dashboard_machine_form.html
│   ├── management/commands/
│   │   └── run_telegram_bot.py    # Management command for Telegram bot
│   ├── admin.py                   # Django Admin registration
│   ├── apps.py                    # App configuration & auto-seeding
│   ├── models.py                  # FaultReport, Machine & Technician models
│   ├── services.py                # Core shared business logic & state workflows
│   ├── sms_service.py             # Africa's Talking SMS service (http.client)
│   ├── views.py                   # USSD callback & SMS delivery webhook
│   ├── dashboard_views.py         # Supervisor Dashboard views
│   ├── urls.py                    # Dashboard, USSD & SMS route definitions
│   ├── tests.py                   # USSD integration tests
│   ├── test_services.py           # Business logic unit tests
│   ├── test_telegram.py           # Telegram bot handler tests
│   ├── test_dashboard.py          # Dashboard auth, filtering & workflow tests
│   └── test_sms.py                # SMS service, assignment integration & webhook tests
│
├── manage.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## ⚙️ Quickstart & Setup Guide

### 1. Clone the repository

```bash
git clone https://github.com/Mansur-WP/factorypulse.git
cd factorypulse
```

### 2. Create and activate a virtual environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the root directory:

```bash
cp .env.example .env
```

Ensure the following variables are present in `.env`:

```env
# Africa's Talking Credentials (USSD & SMS)
AFRICASTALKING_USERNAME=sandbox
AFRICASTALKING_API_KEY=your_africastalking_api_key

# Telegram Bot (Optional for local testing)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_from_botfather

# Django Settings
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=*
```

> **Note**: Never commit real `.env` files or API secrets to version control.

### 5. Run migrations

```bash
python manage.py migrate
```
*(This automatically migrates the database and seeds the default factory machines and sample technicians.)*

### 6. Create a Supervisor / Staff account

To log into the **Supervisor Dashboard**, you need a staff account:

```bash
python manage.py createsuperuser
```
Follow the prompts to enter your username, email, and password.

### 7. Run the test suite

```bash
python manage.py check
python manage.py test
```
*All 117 automated tests should pass.*

---

## 🚀 Running the Services

### 🖥️ 1. Start the Web Server & Supervisor Dashboard

```bash
python manage.py runserver
```

Once running, navigate in your browser:
- **Supervisor Dashboard**: [http://localhost:8000/dashboard/](http://localhost:8000/dashboard/) (or root `/` which redirects to dashboard)
- **Custom Login Page**: [http://localhost:8000/dashboard/login/](http://localhost:8000/dashboard/login/)
- **Faults Management**: [http://localhost:8000/dashboard/faults/](http://localhost:8000/dashboard/faults/)
- **Machine Management**: [http://localhost:8000/dashboard/machines/](http://localhost:8000/dashboard/machines/)
- **Django Admin**: [http://localhost:8000/admin/](http://localhost:8000/admin/)

*(You will be prompted to log in using the superuser account created in step 6).*

---

### 🤖 2. Start the Telegram Development Bot

In a separate terminal (with the virtual environment activated):

```bash
python manage.py run_telegram_bot
```

Open Telegram, search for your bot, and send `/start` to begin reporting faults or viewing machine statuses.

---

### 🌍 3. Africa's Talking USSD Gateway Testing

The USSD endpoint is located at:
```text
POST http://localhost:8000/ussd/
```

> **Note**: Opening `/ussd/` in a web browser sends a `GET` request and returns `405 Method Not Allowed`. This is expected because Africa's Talking communicates strictly via `POST`.

To connect to Africa's Talking Sandbox:
1. Expose your local port via ngrok:
   ```bash
   ngrok http 8000
   ```
2. Copy your forwarding URL (e.g. `https://your-domain.ngrok-free.app`).
3. Set your USSD Callback URL in the Africa's Talking Dashboard to:
   ```text
   https://your-domain.ngrok-free.app/ussd/
   ```

---

### 📲 4. SMS Delivery Callback (Optional)

Africa's Talking sends delivery status reports to:
```text
POST http://localhost:8000/sms/delivery/
```

To receive real-time delivery status updates, configure the SMS Delivery Report URL in your Africa's Talking Dashboard to point to your ngrok URL:
```text
https://your-domain.ngrok-free.app/sms/delivery/
```

Tracked delivery states: `Success`, `Sent`, `Failed`, `Rejected`.

> **Note**: `Success`/`Delivered` means the network accepted delivery — it does NOT confirm the technician read the SMS.

---

## 👷 Technician Assignment Workflow

When a supervisor assigns a fault via the dashboard:

1. The fault status transitions from `OPEN` → `ASSIGNED`.
2. An SMS is sent to the assigned technician's registered phone number:
   ```text
   FactoryPulse

   Fault #4 has been assigned to you.

   Machine: Packaging Machine
   Problem: Overheating
   Severity: HIGH

   Please review this task.
   ```
3. If SMS dispatch fails, the assignment is **never** rolled back — the technician remains assigned and the failure is logged.

### Status Workflow

```text
OPEN → ASSIGNED → IN_PROGRESS → RESOLVED
  ↑       │            │
  └───────┴────────────┘  (Reopen)
```

---

## 🧪 Testing Coverage

The automated test suite (`python manage.py test`) verifies:
- **USSD flows**: Initial menus, machine selection, problem selection, custom text descriptions, severity grading, confirmation, cancellation, and credential protection.
- **Service logic**: Input resolvers, status transition validations, user isolation, and stats calculation.
- **Telegram bot**: Handlers, session contexts, user isolation, button formatting, and polling configuration.
- **Supervisor dashboard**: Authorization barriers, staff permissions, status workflow enforcement, search/filter queries, machine CRUD, and technician assignment.
- **SMS service**: Outgoing SMS dispatch, phone masking, API failure handling, assignment-SMS integration, delivery webhook responses, and mock isolation.

---

## 🔧 Known Issues & Notes

### Python 3.14 SSL Compatibility
The `africastalking` Python SDK uses `requests`/`urllib3`, which has an SSL context incompatibility on **Python 3.14 + OpenSSL 3.0.18** (`WRONG_VERSION_NUMBER` error when connecting to `api.sandbox.africastalking.com`). FactoryPulse works around this by using Python's stdlib `http.client.HTTPSConnection` to call the Africa's Talking REST API directly, bypassing the SDK's HTTP layer. This is transparent and requires no user action.

---

## 🗺️ Roadmap

- [x] Django backend & SQLite persistence
- [x] Africa's Talking-compatible USSD endpoint (`POST /ussd/`)
- [x] Shared core business logic service layer
- [x] Telegram development bot interface
- [x] Protected Supervisor Dashboard with KPI metrics
- [x] Custom supervisor login portal
- [x] Machine management & operational tracking
- [x] Fault status workflow state machine
- [x] Technician model & assignment workflow
- [x] SMS notifications for technicians (Africa's Talking SMS)
- [x] SMS delivery status callback endpoint
- [ ] Inbound SMS commands (ACCEPT, START, RESOLVE)
- [ ] Maintenance resolution analytics & downtime reports
- [ ] Production cloud deployment

---

## 🏆 Vision

> **Report problems faster. Respond sooner. Keep production moving.**
