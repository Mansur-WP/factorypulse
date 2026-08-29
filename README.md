
# 🏭 FactoryPulse

## Manufacturing Fault Reporting & Maintenance Coordination

FactoryPulse is a simple manufacturing maintenance system that allows factory workers to report machine faults and helps supervisors manage those reports.

The project is designed to use **USSD and SMS**, making it possible to report faults without requiring a smartphone or internet connection.

For development and testing, Telegram is currently being used as a temporary interface.

---

## 🚀 How It Works

```text
Factory Worker
      ↓
USSD / Telegram
      ↓
FactoryPulse
      ↓
Django
      ↓
Database
      ↓
Supervisor
      ↓
Maintenance Action
````

A typical fault report:

```text
Report Fault
     ↓
Select Machine
     ↓
Select Problem
     ↓
Select Severity
     ↓
Confirm
     ↓
Fault Saved
```

---

## 🛠️ Tech Stack

* Python
* Django
* SQLite
* Africa's Talking USSD
* Telegram Bot API
* python-dotenv

---

## 📱 Current Features

* USSD callback endpoint
* Fault reporting through USSD
* Telegram development interface
* Machine selection
* Problem selection
* Severity selection
* Fault confirmation
* Fault cancellation
* Fault database storage
* Input validation
* Django Admin support
* Automated tests

### Fault Severity

* Low
* Medium
* High
* Critical

### Fault Status

* OPEN
* ASSIGNED
* IN_PROGRESS
* RESOLVED

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
│   ├── admin.py
│   ├── models.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
│
├── manage.py
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd FactoryPulse
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file:

```env
DJANGO_SECRET_KEY=your_secret_key
AFRICASTALKING_USERNAME=your_username
AFRICASTALKING_API_KEY=your_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

Never commit the real `.env` file or API keys.

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Check the project

```bash
python manage.py check
```

### 7. Run tests

```bash
python manage.py test
```

### 8. Start the server

```bash
python manage.py runserver
```

---

## 🌍 Africa's Talking USSD

The USSD callback endpoint is:

```text
POST /ussd/
```

For local development, you can expose Django using ngrok:

```bash
ngrok http 8000
```

Then configure the Africa's Talking callback URL as:

```text
https://your-ngrok-url/ussd/
```

---

## 👨‍💻 Contributing

Contributions are welcome.

If you want to work on FactoryPulse:

### 1. Fork the repository

Create your own fork on GitHub.

### 2. Clone your fork

```bash
git clone <your-fork-url>
cd FactoryPulse
```

### 3. Create a branch

```bash
git checkout -b feature/your-feature
```

### 4. Make your changes

Keep changes focused and avoid unnecessary dependencies or architectural changes.

### 5. Run tests

```bash
python manage.py check
python manage.py test
```

Make sure existing functionality still works.

### 6. Commit your changes

```bash
git add .
git commit -m "Add your change"
```

### 7. Push your branch

```bash
git push origin feature/your-feature
```

Then open a Pull Request.

---

## 🧑‍💻 For Developers

Before modifying the project:

1. Understand the existing Django structure.
2. Check the existing models and USSD flow.
3. Avoid creating duplicate models or business logic.
4. Keep secrets in `.env`.
5. Run tests before and after making changes.
6. Keep the project simple and focused.

The main goal is:

```text
Simple
   ↓
Reliable
   ↓
Useful
```

---

## 🗺️ Roadmap

* [x] Django backend
* [x] USSD foundation
* [x] Fault reporting
* [x] Database persistence
* [x] Telegram development interface
* [ ] Supervisor dashboard
* [ ] Machine management
* [ ] Technician assignment
* [ ] SMS notifications
* [ ] Analytics
* [ ] Production Africa's Talking integration

---

## 🏆 Vision

FactoryPulse aims to make machine fault reporting faster and more accessible for African manufacturing environments.

```text
Report problems faster.
Respond sooner.
Keep production moving.
```
