Absolutely. Here is the **final, clean README** you can copy and paste directly into `README.md`.


# 🏭 FactoryPulse

### Smarter Fault Reporting. Faster Maintenance.

FactoryPulse is a lightweight manufacturing maintenance coordination platform that connects **factory workers, supervisors, and technicians** through **USSD, SMS, and a real-time web dashboard**.

It is designed for factory environments where workers may not have smartphones or reliable mobile internet access.

---

## 🚀 Live Demo

**Live Application:**  
https://factorypulse-m9ov.onrender.com

**GitHub Repository:**  
https://github.com/Mansur-WP/factorypulse.git

**Docker Image:**  
`mpycraft/factorypulse:latest`

---

## 🎯 The Problem

Machine downtime can become expensive when faults are reported slowly or maintenance teams lack visibility.

In many factory environments:

- Workers may not have smartphones.
- Internet connectivity may be unreliable.
- Machine faults can be reported informally.
- Supervisors may lack a centralized view of faults.
- Technicians may not receive assignments quickly.
- Maintenance progress can be difficult to track.

FactoryPulse addresses these challenges with a communication-first maintenance workflow.

---

## 💡 Our Solution

FactoryPulse provides a simple workflow for reporting, assigning, and resolving machine faults.

A worker reports a machine problem through **USSD**, without requiring a smartphone or mobile internet.

The supervisor receives the fault through the FactoryPulse dashboard, reviews its severity, and assigns a technician.

The technician receives an **SMS notification** and can manage the assigned fault through the technician workflow.

The supervisor can then monitor the fault from report to resolution.

---

## 🔄 How It Works

```text
👷 WORKER
    │
    │ USSD
    ▼
📡 FACTORYPULSE
    │
    ▼
👨‍💼 SUPERVISOR
    │
    │ Assign Technician
    ▼
📱 SMS
    │
    ▼
🔧 TECHNICIAN
    │
    │ Accept → Start → Resolve
    ▼
✅ RESOLVED
````

### Fault Lifecycle

```text
OPEN
  ↓
ASSIGNED
  ↓
ACCEPTED
  ↓
IN_PROGRESS
  ↓
RESOLVED
```

Every fault receives a unique fault ID and moves through a defined maintenance lifecycle.

---

## 👥 User Roles

### 👷 Worker

Workers report machine faults through USSD.

They can:

* Select a machine
* Select a problem
* Select severity
* Confirm the report
* Receive a unique fault ID

No smartphone or mobile internet is required for the reporting workflow.

### 👨‍💼 Supervisor

Supervisors use the web dashboard to:

* View reported faults
* Review fault severity
* Assign technicians
* Manage machines
* Manage technicians
* Activate or deactivate technicians
* Monitor maintenance activity
* View technician performance
* Track fault status and downtime

### 🔧 Technician

Technicians receive assignments through SMS and can manage their assigned faults through the supported workflow:

```text
ACCEPT <fault_id>
START <fault_id>
RESOLVE <fault_id>
```

Technicians can only act on faults they are authorized to handle.

---

## ✨ Key Features

### 📱 USSD Fault Reporting

Workers can report machine problems through USSD without needing a smartphone or mobile internet.

### 📊 Supervisor Dashboard

A centralized dashboard provides visibility into:

* Fault reports
* Severity
* Machine status
* Technician assignments
* Fault lifecycle
* Downtime
* Maintenance activity

### 🔧 Technician Management

Supervisors can:

* Add technicians
* Edit technician information
* Activate/deactivate technicians
* View technician performance

### 📈 Technician Performance

Performance information is calculated from actual fault records.

The dashboard can show metrics such as:

* Assigned faults
* Resolved faults
* In-progress faults
* Other supported operational metrics

Resolved faults provide a clear view of how many reported maintenance issues a technician has successfully resolved.

### 📨 SMS Notifications

Technicians receive maintenance assignment notifications through SMS.

### 🔐 Role-Based Access

Supervisor and technician actions are protected by authorization and factory-level access controls.

### ⏱️ Downtime Visibility

FactoryPulse tracks fault downtime to provide operational visibility into machine issues.

### 🗄️ PostgreSQL Persistence

Production data is stored using PostgreSQL.

### 🐳 Dockerized Deployment

FactoryPulse is packaged as a Docker image for deployment.

---

# 📡 Africa's Talking Integration

Africa's Talking is a core part of the FactoryPulse communication workflow.

## USSD

Factory workers use the Africa's Talking USSD channel to report machine faults.

The USSD interaction allows workers to provide:

* Machine
* Problem
* Severity
* Confirmation

This makes the reporting workflow accessible even when a worker does not have a smartphone or mobile internet.

## SMS

Africa's Talking SMS is used to notify technicians when a fault has been assigned to them.

Technicians can then interact with their assigned faults through the supported SMS workflow.

## Webhooks

FactoryPulse exposes webhook endpoints for communication with Africa's Talking.

### USSD

```text
POST /ussd/
```

### SMS Delivery

```text
POST /sms/delivery/
```

### Incoming SMS

```text
POST /sms/incoming/
```

The incoming SMS endpoint supports technician commands such as:

```text
ACCEPT <fault_id>
START <fault_id>
RESOLVE <fault_id>
```

> API keys, webhook secrets, passwords, and other sensitive credentials are never stored in this README.

---

# 🏗️ System Architecture

```text
                    ┌──────────────────────┐
                    │   Africa's Talking   │
                    │                      │
                    │      USSD + SMS      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   FactoryPulse       │
                    │   Django Backend     │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
       │ PostgreSQL  │  │  Supervisor  │  │   Technician │
       │  Database   │  │  Dashboard   │  │ SMS Workflow │
       └─────────────┘  └──────────────┘  └──────────────┘
```

### Architecture Flow

```text
Worker
  │
  │ USSD
  ▼
Africa's Talking
  │
  ▼
Django Backend
  │
  ├── PostgreSQL
  │
  ├── Supervisor Dashboard
  │
  └── SMS → Technician
```

---

# 🛠️ Technology Stack

| Technology          | Purpose                          |
| ------------------- | -------------------------------- |
| Python              | Application programming language |
| Django              | Backend web framework            |
| PostgreSQL          | Production database              |
| HTML/CSS/JavaScript | Web interface                    |
| Africa's Talking    | USSD and SMS communication       |
| Gunicorn            | Production WSGI server           |
| WhiteNoise          | Static file serving              |
| Docker              | Application containerization     |
| Docker Hub          | Container image registry         |
| Render              | Production hosting               |

---

# 🗄️ Database

FactoryPulse uses PostgreSQL for persistent production data.

The application models the main operational entities involved in the maintenance workflow, including:

* Users
* Factories
* Supervisors
* Technicians
* Machines
* Fault Reports
* Fault history/status information

Technician performance metrics are derived from existing fault records rather than maintaining redundant counters wherever possible.

---

# 🔐 Security

FactoryPulse includes several production security measures, including:

* Production `DEBUG` disabled
* Production secret key requirements
* `ALLOWED_HOSTS` validation
* CSRF protection
* Secure cookies
* HSTS configuration
* `X-Frame-Options` protection
* Referrer policy
* Factory-scoped supervisor access
* Technician authorization
* Assigned-fault authorization
* Fault state-transition validation
* Machine input validation
* Optional incoming SMS webhook authentication
* Masked phone numbers in application logs

Supervisor access is restricted to authorized users and their associated factory.

---

# 🧪 Testing

FactoryPulse currently has:

**159 tests passing.**

The test suite covers major application workflows and security-related behavior implemented in the project.

Run the test suite locally with:

```bash
python manage.py test
```

---

# 💻 Local Development

## 1. Clone the repository

```bash
git clone https://github.com/Mansur-WP/factorypulse.git
cd factorypulse
```

## 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Check the Django project

```bash
python manage.py check
```

## 5. Run tests

```bash
python manage.py test
```

## 6. Start the development server

```bash
python manage.py runserver
```

The application will normally be available at:

```text
http://127.0.0.1:8000/
```

---

# 🐳 Docker

FactoryPulse is distributed as a Docker image.

### Build

```bash
docker build -t mpycraft/factorypulse:latest .
```

### Push

```bash
docker push mpycraft/factorypulse:latest
```

### Docker Image

```text
mpycraft/factorypulse:latest
```

---

# ⚙️ Environment Variables

FactoryPulse uses environment variables for configuration and sensitive credentials.

| Variable                      | Description                                             |
| ----------------------------- | ------------------------------------------------------- |
| `DEBUG`                       | Controls Django debug mode                              |
| `SECRET_KEY`                  | Django application secret                               |
| `ALLOWED_HOSTS`               | Allowed application hostnames                           |
| `CSRF_TRUSTED_ORIGINS`        | Trusted origins for CSRF protection                     |
| `DATABASE_URL`                | PostgreSQL database connection                          |
| `AFRICASTALKING_USERNAME`     | Africa's Talking account username                       |
| `AFRICASTALKING_API_KEY`      | Africa's Talking API authentication key                 |
| `AFRICASTALKING_SENDER_ID`    | SMS sender configuration where applicable               |
| `SMS_INCOMING_WEBHOOK_SECRET` | Optional authentication secret for incoming SMS webhook |

> Never commit actual environment variable values, API keys, passwords, or secrets to the repository.

---

# ☁️ Production Deployment

FactoryPulse is deployed using Docker and Render.

### Production Components

```text
Docker Image
     ↓
Docker Hub
     ↓
Render Web Service
     ↓
Django + Gunicorn
     ↓
PostgreSQL
```

### Live Application

[https://factorypulse-m9ov.onrender.com](https://factorypulse-m9ov.onrender.com)

### Container Image

```text
mpycraft/factorypulse:latest
```

---

# 📸 Product

FactoryPulse provides a public product landing page and an authenticated supervisor dashboard.

The landing page explains the product, workflow, manufacturing problem, and Africa's Talking integration.

The supervisor dashboard provides operational visibility into faults, machines, technicians, assignments, and maintenance activity.

---

# 🎯 Hackathon Alignment

FactoryPulse was developed for the **Africa's Talking Manufacturing Solutions Hackathon**.

## Innovation

FactoryPulse combines USSD, SMS, and a centralized maintenance workflow to address practical factory communication challenges.

## Manufacturing Relevance

The solution focuses on:

* Machine faults
* Maintenance coordination
* Technician assignments
* Downtime visibility
* Fault resolution

## Africa's Talking Integration

Africa's Talking USSD and SMS are central to the worker and technician workflows rather than being added as secondary features.

## Technical Implementation

The solution uses:

* Django
* PostgreSQL
* Africa's Talking APIs
* Docker
* Production deployment
* Role-based authorization
* Webhooks

## Usability

Different users interact through channels suited to their role:

```text
Worker       → USSD
Supervisor   → Web Dashboard
Technician   → SMS
```

## Real-World Impact

FactoryPulse aims to reduce communication gaps between factory workers, supervisors, and technicians and provide clearer visibility into maintenance operations.

---

# 📈 Scalability

The current implementation is an MVP designed to provide the core maintenance workflow.

Future scaling opportunities include:

* Supporting additional factories
* Larger technician teams
* Background task processing
* Improved notification delivery tracking
* Worker registration and identity management
* Advanced maintenance analytics
* IoT machine integrations
* Predictive maintenance
* Inventory management
* Mobile applications

These are future improvements and are not presented as existing MVP features.

---

# ⚠️ Current MVP Limitations

The current MVP has several intentional limitations.

### Worker Identity

USSD fault reporting is not currently tied to a registered worker account.

### Technician Identification

Technician SMS workflow relies on phone-number matching.

### Advanced Predictive Maintenance

IoT monitoring, machine-learning prediction, and predictive maintenance are outside the current MVP scope.

These limitations provide opportunities for future versions while keeping the current MVP focused on the core reporting and maintenance workflow.

---

# 🔮 Future Improvements

Potential future versions of FactoryPulse could include:

* Registered worker identities
* More advanced technician analytics
* Maintenance scheduling
* Automated escalation
* Delivery-report monitoring
* IoT sensor integration
* Predictive maintenance
* Inventory and spare-parts management
* Mobile applications
* Multi-factory management
* Advanced reporting and analytics

---

# 🌐 Project Links

| Resource         | Link                                                                                           |
| ---------------- | ---------------------------------------------------------------------------------------------- |
| Live Application | [https://factorypulse-m9ov.onrender.com](https://factorypulse-m9ov.onrender.com)               |
| GitHub           | [https://github.com/Mansur-WP/factorypulse.git](https://github.com/Mansur-WP/factorypulse.git) |
| Docker Image     | `mpycraft/factorypulse:latest`                                                                 |

---

# 📄 Documentation

The complete hackathon solution documentation is provided separately as the official submission document.

It contains the detailed architecture, database design, deployment information, security, scalability, impact, demonstration information, and other required submission details.

---

# 🏁 Project Status

**FactoryPulse MVP: Implemented and Deployed**

The current MVP includes:

```text
✅ Public Landing Page
✅ USSD Fault Reporting
✅ Supervisor Dashboard
✅ Technician Management
✅ Technician Performance Metrics
✅ Technician Assignment
✅ SMS Notifications
✅ Technician SMS Workflow
✅ Fault Lifecycle Tracking
✅ Machine Management
✅ Downtime Visibility
✅ Factory-Scoped Authorization
✅ PostgreSQL Persistence
✅ Docker Deployment
✅ Production Hosting
```

---

## 🏭 FactoryPulse

### Smarter Fault Reporting. Faster Maintenance.

Built for the **Africa's Talking Manufacturing Solutions Hackathon · Kano, Nigeria**

```


