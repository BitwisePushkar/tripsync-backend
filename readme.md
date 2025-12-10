# TripSync 

A scalable, real-time collaborative trip planning platform built with **Django** and **Django REST Framework**.

Designed for seamless collaboration — users → trips → chat rooms → itineraries → expenses.

---

## Tech Stack

`Django : DRF : PostgreSQL : Redis : WebSockets : Django Channels : Celery : Celery Beat : LangChain : Firebase : AWS S3 : AWS EC2 : Docker : Nginx : uv : GoogleOauth`

---

## Core Functionality

### Auth

Register · Login · Email Verification (SMTP) · Role-Based Access Control · GoogleOauth

### Users

Profile Management · Preferences · Secure Account Access

### Trips

Create Trips · Invite Participants · Role Management (Creator / Participant) · Trip Collaboration

### Chat

Real-Time Chat Rooms · WebSocket Messaging · Redis Channel Layers · Async Processing

### AI Itinerary

AI-Powered Itinerary Generator · Smart Recommendations · AI Chatbot (LangChain)

### Expenses

Shared Expense Tracking · Cost Distribution · Trip Budget Management

### Community

Community Interaction · Trending Trips · Public Content Discovery

### Notifications

Firebase Push Notifications · Background Scheduling (Celery Beat)

### Media

Secure Media Uploads · Static & File Handling · S3 Storage Support

### Performance Optimization

Async WebSocket Consumers · Redis-backed Scaling · Optimized DB Queries

Reduced Message Latency from **500ms → 280ms**

---
## Structure

```text
TripSync/
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── pyproject.toml
├── poetry.lock
├── uv.lock
├── README.md
│
├── main/
│   ├── manage.py
│   │
│   ├── main/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   ├── wsgi.py
│   │   └── celery.py
│   │
│   ├── account/
│   ├── chat/
│   ├── community/
│   ├── Itinerary/
│   ├── personal/
│   ├── tripmate/
│   │
│   └── templates/
│       └── emails/
│
└── nginx/
    └── nginx.conf
```

---

## ▶ Setup (Local)

```bash
git clone https://github.com/BitwisePushkar/tripsync-backend.git
cd tripsync

uv venv
source .venv/bin/activate

uv pip install -r auth/requirements.txt

python auth/manage.py migrate
python auth/manage.py runserver
```

App → `http://127.0.0.1:8000/`

---

## 🐳 Setup (Docker)

```bash
docker-compose up --build
```

App → `http://localhost:8000/`

---

## Environment Variables

Create `.env` file using `.env.example`

---


Built for scalable, real-time collaborative travel planning.