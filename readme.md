# TripSync 🚀  
Real-Time Collaborative Trip Planning Platform

TripSync is a scalable, real-time trip planning platform that enables users to collaborate through chat rooms, generate AI-powered itineraries, manage expenses, and interact securely in role-based environments.

---

## ✨ Key Features

- 👥 Supports **500+ active users** across real-time collaborative chat rooms
- 💬 **Real-time messaging** using WebSockets (Django Channels)
- ⚡ Backend optimization reduced average message latency from **500ms → 280ms**
- 🔐 Secure authentication with:
  - Email verification via **SMTP**
  - Phone verification via **SMS**
- 🧠 **AI-powered itinerary generator and also a Chatbot** using **LangChain**
- 🛂 **Role-based access control** for trip creators and participants
- ☁️ Deployed on **AWS EC2 (Ubuntu) and also on Render** with **S3** and **RDS**
- 🚀 Async processing using **Redis** and **Websocket** for chat feature

---

## 🛠️ Tech Stack

- **Backend**: Django, Django REST Framework  
- **Real-Time**: Django Channels, WebSockets, Redis  
- **Database**: PostgreSQL (RDS), SQLite (local)  
- **AI**: LangChain  
- **Deployment**: Docker, Docker Compose, AWS EC2  
- **Web Server**: Nginx  
- **Auth**: SMTP, SMS OTP  
- **OS**: Linux (Ubuntu)

---

## 📂 Project Structure
```text
TripSync/
├── Dockerfile
├── docker-compose.yml
├── .gitignore
├── readme.md
│
├── auth/                      # Django project root
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── build.sh
│   │
│   ├── auth/                  # Core Django configuration
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   ├── wsgi.py
│   │   └── storage_backends.py
│   │
│   ├── account/               # Authentication & user management
│   ├── chat/                  # WebSocket-based real-time chat
│   ├── chatbot/               # AI chatbot features
│   ├── community/             # Community interactions
│   ├── expense/               # Trip expense tracking
│   ├── HomePage/              # Homepage with weather APIs
│   ├── Itinerary/             # AI-powered trip planning
│   ├── personal/              # User profile & preferences
│   ├── trending/              # Trending trips & content
│   ├── tripmate/              # Trip roles & collaboration
│   ├── media/                 # Uploaded media files
│   ├── staticfiles/           # Collected static files
│   └── images/                # App images
│
└── nginx/
    └── default.conf            # Nginx configuration
```
---

## 🚀 Running the Project (Without Docker)

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/your-username/tripsync.git
cd tripsync
```

### 2️⃣ Create & Activate Virtual Environment

```bash
python -m venv venv
source venv/bin/activate      # Linux / macOS
venv\Scripts\Activate.ps1         # Windows
```

### 3️⃣ Install Dependencies & Setup Project

```bash
pip install -r auth/requirements.txt \
&& python auth/manage.py collectstatic --noinput \
&& python auth/manage.py migrate \
&& python auth/manage.py createsuperuser --no-input 
```

### 4️⃣ Run the Server

```bash
python auth/manage.py runserver
```

App will be available at:
👉 `http://127.0.0.1:8000/`

---

## 🐳 Running the Project (Using Docker)

### 1️⃣ Build & Start Containers

```bash
docker-compose up --build
```

### 2️⃣ Apply Migrations

```bash
docker-compose exec web python manage.py migrate
```

### 3️⃣ Create Superuser

```bash
docker-compose exec web python manage.py createsuperuser
```

### 4️⃣ Collect Static Files

```bash
docker-compose exec web python manage.py collectstatic --noinput
```

App will be available at:
👉 `http://localhost:8000/`

---

## 🔐 Environment Variables

Create a `.env` file using `.env.example`:

```env
SECRET_KEY=your-secret-key
DEBUG=True

DATABASE_URL=postgresql://user:password@host:port/dbname
REDIS_URL=redis://redis:6379

EMAIL_HOST_USER=your-email
EMAIL_HOST_PASSWORD=your-email-password

DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=admin123
```

---

## 📈 Performance Improvements

* Optimized async WebSocket consumers
* Redis-backed channel layers
* Reduced message delivery latency by **44%**
* Efficient DB queries and indexing

---

## 🧩 Future Enhancements

* AI itinerary refinement
* Push notifications
* Analytics dashboard

---

## 🤝 Contributing

Contributions are welcome.
Please open an issue before submitting major changes.

---

## 📄 License

This project is licensed under the **MIT License**.

---

**Built with ❤️ using Django, WebSockets, Redis, and AI**