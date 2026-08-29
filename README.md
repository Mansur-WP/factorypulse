# 🏭 FactoryPulse

## Manufacturing Fault Reporting & Maintenance Coordination

FactoryPulse is a lightweight manufacturing maintenance and fault-reporting platform designed for African factories. It enables shop-floor workers to report machine breakdowns and operational faults instantly without needing a smartphone or internet connection, while giving factory supervisors a centralized dashboard to track and resolve issues.

---

## 🚀 System Architecture

FactoryPulse uses a single, shared business logic layer across all interfaces:

```text
Shop-Floor Worker (USSD) ──┐
                           │
Developer / Tester (TG) ───┼──→ FactoryPulse Services (ussd/services.py) ──→ SQLite Database
                           │
Supervisor (Dashboard) ────┘
```

---

## 📱 Features

### 1. 📞 Africa's Talking USSD Gateway (`POST /ussd/`)
- Interactive USSD menu (`*384*...#`).
- Fast, multi-step fault reporting (Machine $\rightarrow$ Problem $\rightarrow$ Severity $\rightarrow$ Confirmation).
- Session cancellation handling (`0` or `Cancel`).
- Cumulative session state parser with robust input validation.

### 2. 🤖 Telegram Development Bot (`run_telegram_bot`)
- Interactive Telegram interface mirroring the complete USSD flow with reply keyboards and numerical inputs.
- Custom problem descriptions ("Other" option).
- Machine status checking & isolated personal report history ("My Reports").

### 3. 🖥️ Supervisor Dashboard (`/dashboard/`)
- **Protected Authentication**: Restricted to authenticated staff/admin accounts.
- **KPI Summary Cards**: Real-time counters for Total, Open, Critical, and Resolved faults.
- **Filterable Faults List**: Search by machine, problem, reporter, and filter by status and severity.
- **Fault Workflow Actions**: Strict state transitions (`OPEN` $\rightarrow$ `ASSIGNED` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `RESOLVED`).
- **Machine Management (`/dashboard/machines/`)**: View, add, and edit machines with operational statuses (`OPERATIONAL`, `MAINTENANCE`, `OFFLINE`) and fault histories.
- **Activity Feed**: Real-time log of recent reports and resolutions.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12+, Django 5.2+
- **Database**: SQLite (Development / Production ready with PostgreSQL)
- **Interfaces**: Africa's Talking USSD API, Telegram Bot API (`python-telegram-bot`)
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
│   │   ├── dashboard_machines.html
│   │   └── dashboard_machine_form.html
│   ├── management/commands/
│   │   └── run_telegram_bot.py    # Management command for Telegram bot
│   ├── admin.py                   # Django Admin registration
│   ├── apps.py                    # App configuration & machine auto-seeding
│   ├── models.py                  # FaultReport and Machine models
│   ├── services.py                # Core shared business logic & state workflows
│   ├── views.py                   # USSD callback endpoint
│   ├── dashboard_views.py         # Supervisor Dashboard views
│   ├── urls.py                    # Dashboard & USSD route definitions
│   ├── tests.py                   # USSD integration tests
│   ├── test_services.py           # Business logic unit tests
│   ├── test_telegram.py           # Telegram bot handler tests
│   └── test_dashboard.py          # Dashboard auth, filtering & workflow tests
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
# Africa's Talking Credentials
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
*(This automatically migrates the database and seeds the default factory machines: Generator, Packaging Machine, and Milling Machine).*

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
*All 87 automated tests should pass.*

---

## 🚀 Running the Services

### 🖥️ 1. Start the Web Server & Supervisor Dashboard

```bash
python manage.py runserver
```

Once running, navigate in your browser:
- **Supervisor Dashboard**: [http://localhost:8000/dashboard/](http://localhost:8000/dashboard/) (or root `/` which redirects to dashboard)
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

## 🧪 Testing Coverage

The automated test suite (`python manage.py test`) verifies:
- **USSD flows**: Initial menus, machine selection, problem selection, custom text descriptions, severity grading, confirmation, cancellation, and credential protection.
- **Service logic**: Input resolvers, status transition validations, user isolation, and stats calculation.
- **Telegram bot**: Handlers, session contexts, user isolation, button formatting, and polling configuration.
- **Supervisor dashboard**: Authorization barriers, staff permissions, status workflow enforcement, search/filter queries, and machine CRUD.

---

## 🗺️ Roadmap

- [x] Django backend & SQLite persistence
- [x] Africa's Talking-compatible USSD endpoint (`POST /ussd/`)
- [x] Shared core business logic service layer
- [x] Telegram development bot interface
- [x] Protected Supervisor Dashboard with KPI metrics
- [x] Machine management & operational tracking
- [x] Fault status workflow state machine
- [ ] SMS notifications for supervisors & technicians (Africa's Talking SMS)
- [ ] Technician assignment module
- [ ] Maintenance resolution analytics & downtime reports
- [ ] Production cloud deployment

---

## 🏆 Vision

> **Report problems faster. Respond sooner. Keep production moving.**
