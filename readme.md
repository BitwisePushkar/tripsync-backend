 TripSync 🚀

A scalable, real-time collaborative trip planning platform built with **Django** and **Django REST Framework**.
Designed for seamless collaboration — users → trips → chat rooms → itineraries → expenses.

---

## Tech Stack

`Django : DRF : PostgreSQL : Redis : WebSockets : Django Channels : LangChain : AWS EC2 : Docker : Nginx : SMTP : SMS OTP`

---

## Core Functionality

### Auth

Register · Login · Email Verification (SMTP) · Phone Verification (SMS OTP) · Role-Based Access Control

### Users

Profile Management · Preferences · Role Assignment · Secure Account Access

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

### Media

Secure Media Uploads · Static & File Handling · S3 Storage Support

### Performance Optimization

Async WebSocket Consumers · Redis-backed Scaling · Optimized DB Queries
Reduced Message Latency from **500ms → 280ms**

---

## Structure

```
TripSync/
├── Dockerfile
├── docker-compose.yml
├── .gitignore
├── readme.md
│
├── auth/
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── build.sh
│   │
│   ├── auth/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   ├── wsgi.py
│   │   └── storage_backends.py
│   │
│   ├── account/
│   ├── chat/
│   ├── chatbot/
│   ├── community/
│   ├── expense/
│   ├── HomePage/
│   ├── Itinerary/
│   ├── personal/
│   ├── trending/
│   ├── tripmate/
│   ├── media/
│   ├── staticfiles/
│   └── images/
│
└── nginx/
    └── default.conf
```

---

## ▶ Setup (Local)

```bash
git clone <repo>
cd tripsync
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\Activate.ps1
pip install -r auth/requirements.txt
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

## Deployment

AWS EC2 (Ubuntu) · PostgreSQL (RDS) · Redis · Nginx · Docker · Render Deployment Support

---