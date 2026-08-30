 
# FactoryPulse 🏭

### Report problems faster. Respond sooner. Keep production moving.

FactoryPulse is a manufacturing maintenance and communication platform that helps factory workers report machine faults quickly, enables supervisors to coordinate maintenance, and allows technicians to respond through SMS.

It is designed for manufacturing environments where workers may not have smartphones, reliable internet access, or access to complex software.

---

## 🚨 The Problem

Machine breakdowns can cause production delays when faults are reported manually or maintenance teams are not coordinated quickly.

Common challenges include:

- Slow fault reporting
- Poor communication between workers, supervisors, and technicians
- Limited visibility into active machine problems
- Difficulty tracking maintenance progress
- Lack of centralized fault and downtime records
- Limited access to smartphones or reliable internet for some workers

---

## 💡 The Solution

FactoryPulse provides a simple maintenance workflow using familiar communication channels.

A worker can report a machine problem using **USSD** without needing a smartphone or internet connection.

The supervisor receives the fault in the FactoryPulse dashboard and assigns a technician.

The technician receives an **SMS** and can respond using simple SMS commands.

### Core Workflow

```text
Worker
  │
  │ USSD
  ▼
Report Machine Fault
  │
  ▼
FactoryPulse
  │
  ▼
Supervisor Dashboard
  │
  │ Assign Technician
  ▼
Technician SMS
  │
  ├── ACCEPT <fault_id>
  │
  ├── START <fault_id>
  │
  └── RESOLVE <fault_id>
  │
  ▼
FactoryPulse
  │
  ▼
Updated Dashboard
````

---

## 👥 Target Users

### Factory Workers

Report machine faults through USSD without requiring a smartphone.

### Supervisors

Monitor machine faults, assign technicians, and track maintenance activity.

### Maintenance Technicians

Receive fault assignments through SMS and update the progress of their assigned faults.

### Factory Management

Use maintenance records and downtime information to understand operational problems.

---

## 📱 Africa's Talking Integration

FactoryPulse integrates **Africa's Talking APIs** for communication between the factory and the platform.

### USSD

Workers use USSD to:

* Report faults
* Select machines
* Select problems
* Select severity
* Confirm reports

### SMS

Technicians receive assignment notifications and can update faults using SMS.

Example:

```text
ACCEPT 13
START 13
RESOLVE 13
```

FactoryPulse processes these commands and updates the fault lifecycle.

---

## 🔄 Fault Lifecycle

Every fault follows a controlled workflow:

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

Invalid state transitions are rejected.

Technicians can only update faults assigned to them.

---

## 🖥️ Supervisor Dashboard

The FactoryPulse dashboard provides operational visibility including:

* Total breakdown reports
* Active incidents
* Critical faults
* Resolved faults
* Machine health
* Machine fault history
* Assigned technicians
* Downtime information
* Average resolution time
* Recent activity
* Fault details and status history

The dashboard is the main interface for factory supervisors.

---

## 🏭 Machine Management

Machines are stored in the database and managed through FactoryPulse.

The USSD machine menu is dynamically generated from the database.

This means a factory can add or modify machines without changing the application code.

Example:

```text
Django Admin / FactoryPulse Management
            ↓
        Machine Database
            ↓
       USSD Machine Menu
```

This makes the solution configurable for different factories.

---

## 📊 Operational Intelligence

FactoryPulse records maintenance activity to provide useful operational information such as:

* Fault frequency
* Machine failure history
* Critical fault statistics
* Average resolution time
* Downtime
* Maintenance history

This helps supervisors understand which machines require attention and where production downtime is occurring.

---

## 🔐 Security

FactoryPulse includes security controls such as:

* Environment-based secrets
* API credentials excluded from source control
* Authentication for the supervisor dashboard
* Role/permission checks
* Server-side input validation
* Technician ownership validation
* Controlled fault state transitions
* POST-based external callbacks
* CSRF protection for internal dashboard forms
* Error logging without exposing credentials
* Database-backed fault records

Production deployment is subject to an additional security and configuration review.

---

## 🧪 Testing

FactoryPulse includes automated tests covering:

* USSD fault reporting
* Machine selection
* Fault validation
* Fault cancellation
* Technician assignment
* Technician authorization
* Fault state transitions
* SMS notifications
* Incoming technician SMS commands
* Dashboard access
* Dashboard functionality
* Machine management
* Fault history
* Analytics

The project currently contains **137 automated tests** covering the implemented functionality.

Run the test suite with:

```bash
python manage.py test
```

Run Django's system checks with:

```bash
python manage.py check
```

---

## 🏗️ Technology Stack

### Backend

* Python
* Django

### Database

* SQLite for development
* PostgreSQL-ready for deployment

### Communication

* Africa's Talking USSD
* Africa's Talking SMS

### Additional Integration

* Telegram development interface

### Frontend

* Django Templates
* HTML
* CSS
* JavaScript

### Deployment

* Docker
* Gunicorn

---

## ⚙️ Configuration

FactoryPulse uses environment variables for sensitive configuration.

Create a `.env` file based on:

```text
.env.example
```

Example configuration:

```env
DJANGO_SECRET_KEY=your-secret-key
DEBUG=True

AFRICASTALKING_USERNAME=your-username
AFRICASTALKING_API_KEY=your-api-key

TELEGRAM_BOT_TOKEN=your-telegram-token
```

Never commit the real `.env` file to Git.

---

## 🚀 Running Locally

Clone the repository:

```bash
git clone <repository-url>
cd FactoryPulse
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Apply migrations:

```bash
python manage.py migrate
```

Run the development server:

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

---

## 📦 Docker

FactoryPulse is prepared for containerized deployment.

Build the image:

```bash
docker build -t factorypulse .
```

Run the container:

```bash
docker run --env-file .env -p 8000:8000 factorypulse
```

The container runs FactoryPulse using Gunicorn.

---

## 🌍 Hackathon Product Vision

FactoryPulse is designed around a simple principle:

> A factory worker should be able to report a machine problem without needing a smartphone or internet connection.

By combining:

```text
USSD
 +
SMS
 +
Django
 +
Database
 +
Supervisor Dashboard
```

FactoryPulse creates a practical maintenance communication workflow for manufacturing environments.

The solution is designed to be:

* **Reusable** across different factories
* **Configurable** with factory-specific machines and technicians
* **Deployable** as a web application
* **Integrated** with Africa's Talking communication APIs
* **Presentable** through a dedicated supervisor dashboard
* **Extendable** toward a commercial manufacturing SaaS platform

---

## 📈 Expected Impact

FactoryPulse aims to improve:

* Speed of machine fault reporting
* Maintenance team coordination
* Supervisor visibility
* Response time
* Maintenance tracking
* Downtime monitoring
* Centralized operational records

The system provides measurable information that can help factories understand maintenance performance and machine downtime.

---

## 💰 Business Potential

FactoryPulse can be developed as a SaaS solution for manufacturing organizations.

A factory could subscribe based on factors such as:

* Number of machines
* Number of technicians
* Number of fault reports
* Number of factory locations

The platform can be configured for different factories without rebuilding the core system.

---

## 🗺️ Future Development

Potential future improvements include:

* Production deployment
* Advanced downtime analytics
* Critical-fault escalation
* Preventive maintenance scheduling
* Technician performance analytics
* Multi-factory management
* Mobile technician interface
* Maintenance reports
* Enterprise integrations

---

## 👨‍💻 Development

FactoryPulse follows a modular Django structure separating:

```text
Models
   ↓
Services / Business Logic
   ↓
Views / API Callbacks
   ↓
Templates / Dashboard
   ↓
External Communication
```

Business logic is kept in service functions where possible so that it can be tested independently from the user interface.

---

## 🤝 Contributors

FactoryPulse is developed as a team project.

When contributing:

1. Create a feature branch.
2. Make focused changes.
3. Add or update tests for new functionality.
4. Run the test suite before submitting changes.
5. Do not commit `.env` or API credentials.
6. Keep business logic in the appropriate service layer.
7. Avoid changing unrelated functionality.
8. Use clear commit messages.

Example:

```bash
git checkout -b feature/your-feature
```

Run:

```bash
python manage.py check
python manage.py test
```

before pushing changes.

---

## 📄 License

This project was developed as a manufacturing technology hackathon project.

---

# FactoryPulse 🏭

### Report problems faster. Respond sooner. Keep production moving.

