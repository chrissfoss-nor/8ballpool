"""Main FastAPI application"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uuid

app = FastAPI(title="8 Ball Pool API", version="0.1.0")

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory game storage (use Redis/DB in production)
games = {}


class GameState(BaseModel):
    """Game state model"""
    game_id: str
    player_turn: str  # "player" or "ai"
    player_balls: List[int]
    ai_balls: List[int]
    status: str  # "active", "won", "lost"


class MoveRequest(BaseModel):
    """Move request model"""
    game_id: str
    cue_ball_position: dict
    target_position: dict
    power: float


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/game/new")
async def create_game():
    """Create a new game"""
    game_id = str(uuid.uuid4())
    game_state = GameState(
        game_id=game_id,
        player_turn="player",
        player_balls=[1, 2, 3, 4, 5, 6, 7],  # Solid balls
        ai_balls=[9, 10, 11, 12, 13, 14, 15],  # Striped balls
        status="active"
    )
    games[game_id] = game_state
    return game_state


@app.get("/game/{game_id}")
async def get_game(game_id: str):
    """Get game state"""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    return games[game_id]


@app.post("/game/move")
async def submit_move(move: MoveRequest):
    """Submit a player move"""
    if move.game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = games[move.game_id]
    
    # Process move (simplified)
    # In real implementation, this would use physics engine
    game.player_turn = "ai"
    
    return {"success": True, "game_state": game}


@app.post("/ai/move/{game_id}")
async def ai_move(game_id: str):
    """Request AI to make a move"""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = games[game_id]
    
    # AI logic (simplified)
    # In real implementation, this would use AI module
    game.player_turn = "player"
    
    return {"success": True, "move": {"power": 0.5, "angle": 45}, "game_state": game}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
