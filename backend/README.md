# 8 Ball Pool - Backend

Python backend server with AI opponent for 8 Ball Pool game.

## Structure

```
backend/
├── src/
│   ├── ai/              # AI logic for computer opponent
│   ├── api/             # FastAPI REST endpoints
│   └── game/            # Game state management and validation
├── tests/               # Unit and integration tests
├── requirements.txt     # Python dependencies
├── setup.py            # Package setup
└── README.md           # This file
```

## Installation

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running the Server

```bash
cd backend
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

- `GET /health` - Health check
- `POST /game/new` - Start new game
- `POST /game/move` - Submit player move
- `GET /game/{game_id}` - Get game state
- `POST /ai/move` - Request AI move

## Development

The backend is responsible for:
- Game state management and validation
- AI opponent logic
- Move validation
- Physics calculations (server-authoritative)
