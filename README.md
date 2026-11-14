# TrackMyHabits: A SMART Goal-Based Habit Monitoring System

An enterprise-grade, privacy-first habit and SMART goal monitoring application migrated from PHP to a modern **Python Flask + Supabase PostgreSQL + HTML5/CSS3/Vanilla JS** stack, configured for zero-configuration serverless deployment on **Vercel**.

---

## 🌟 Key Architectural Highlights

1. **Backend**: Python 3 (Flask), modular repository structure (`repos.py`), pure functional calculation engine (`habit_logic.py`).
2. **Database**: Supabase PostgreSQL 17 with relational integrity, foreign keys, constraints, and audit logging.
3. **Frontend**: Pure HTML5, CSS3, and JavaScript — responsive glassmorphism theme, interactive Chart.js visualizations, zero heavy frontend framework baggage.
4. **Security**: Werkzeug password hashing, HttpOnly SameSite cookies, CSRF tokens, strict server-side authorization boundaries, role-based controls (`user`, `guest`, `admin`).
5. **Full Admin Panel**: Database metrics, 14-day trend charts, user management (search, paginate, toggle status), complete audit trail.

---

## 🚀 Quick Setup & Local Execution

### 1. Prerequisites
- Python 3.10+
- A Supabase Project (already provisioned: `https://qyexezkaasrvprbakhtw.supabase.co`)

### 2. Installation
```bash
git clone https://github.com/your-username/trackmyhabits.git
cd trackmyhabits
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Environment Setup
Copy `.env.example` to `.env`:
```env
FLASK_SECRET_KEY=your_random_secret_key
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.qyexezkaasrvprbakhtw.supabase.co:5432/postgres?sslmode=require
```

### 4. Create First Administrator
```bash
python create_admin.py --email admin@example.com --name "Administrator" --password "YourStrongPassword123"
```

### 5. Run the Application
```bash
python app.py
```
Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## 🌐 Deploying to Vercel

### Step 1: Vercel CLI Deployment
```bash
npx vercel
```
Or connect your GitHub repository directly in the [Vercel Dashboard](https://vercel.com/new).

### Step 2: Environment Variables
Add the following in your Vercel Project Settings (`Environment Variables`):
- `DATABASE_URL`: Your Supabase connection string.
- `FLASK_SECRET_KEY`: A secure random 32+ character key.
- `VERCEL_ENV`: `production`

---

## 🧪 Automated Tests
Run the test suite using pytest:
```bash
python -m pytest tests/
```
