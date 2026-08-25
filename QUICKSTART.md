# 🚀 Quick Start Guide

This guide will help you get the 8 Ball Pool game running in minutes.

## Prerequisites

Before you begin, make sure you have:

- **Python 3.8+** installed ([Download Python](https://www.python.org/downloads/))
- **Node.js 16+** installed ([Download Node.js](https://nodejs.org/))
- **Git** installed (optional, for cloning)

## Option 1: Automated Start (Recommended)

Use the included startup script that sets up everything automatically:

```bash
./start-dev.sh
```

This script will:
1. Create Python virtual environment
2. Install all backend dependencies
3. Install all frontend dependencies
4. Start both backend and frontend servers

## Option 2: Manual Start

### Step 1: Start the Backend

Open a terminal and run:

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: http://localhost:8000

### Step 2: Start the Frontend

Open a **new terminal** and run:

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start development server
npm run dev
```

Frontend will be available at: http://localhost:3000

## Option 3: Docker (All-in-One)

If you have Docker installed:

```bash
docker-compose up
```

This will start both backend and frontend in containers.

## 🎮 Playing the Game

1. Open your browser to http://localhost:3000
2. Click "Start New Game"
3. Click on the pool table to aim
4. Adjust power with the slider
5. Click "Shoot" to take your shot
6. The AI will automatically take its turn after you

## 📚 Additional Information

- **API Documentation**: http://localhost:8000/docs (when backend is running)
- **Health Check**: http://localhost:8000/health

## 🐛 Troubleshooting

### Port Already in Use

If port 8000 or 3000 is already in use:

**Backend**: Edit `backend/.env` and change the PORT
**Frontend**: Edit `frontend/vite.config.js` and change the port in server.port

### Dependencies Installation Issues

**Backend**:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Frontend**:
```bash
rm -rf node_modules package-lock.json
npm install
```

### Python Module Not Found

Make sure you're in the backend directory and the virtual environment is activated:
```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

## 🧪 Running Tests

**Backend Tests**:
```bash
cd backend
source venv/bin/activate
pytest
```

**Expected Output**: All 7 tests should pass

## 🎯 Next Steps

- Read the main [README.md](README.md) for architecture details
- Explore the code in `backend/src/` and `frontend/src/`
- Modify AI difficulty in `backend/src/ai/agent.py`
- Customize the UI in `frontend/src/components/`

## 💡 Tips

- Use `Ctrl+C` to stop the servers
- Backend auto-reloads when you modify Python files
- Frontend auto-reloads when you modify React files
- Check browser console for any frontend errors
- Check terminal for backend errors

Enjoy the game! 🎱
