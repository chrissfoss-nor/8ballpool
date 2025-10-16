# 🏗️ Architecture Overview

This document provides a detailed overview of the 8 Ball Pool application architecture.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     8 Ball Pool System                       │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────┐           ┌──────────────────────┐
│   Frontend (React)   │           │  Backend (Python)    │
│   Port: 3000         │◄─────────►│  Port: 8000          │
└──────────────────────┘   HTTP    └──────────────────────┘
         │                REST API          │
         │                                  │
    ┌────┴────┐                      ┌─────┴─────┐
    │ Canvas  │                      │  FastAPI  │
    │ Render  │                      │  Router   │
    └─────────┘                      └─────┬─────┘
         │                                 │
    ┌────┴────┐                      ┌─────┴──────┐
    │  User   │                      │   Game     │
    │ Input   │                      │   Logic    │
    └─────────┘                      └─────┬──────┘
                                          │
                                    ┌─────┴─────┐
                                    │  Physics  │
                                    │  Engine   │
                                    └───────────┘
                                          │
                                    ┌─────┴─────┐
                                    │    AI     │
                                    │  Agent    │
                                    └───────────┘
```

## Component Breakdown

### Frontend Components

#### 1. App.jsx
- Main application container
- Manages global game state
- Handles API communication
- Coordinates between components

#### 2. PoolTable.jsx
- Renders pool table using HTML5 Canvas
- Displays balls, pockets, and table layout
- Captures user input (click to aim)
- Shows aiming guide and power indicator
- Animates ball movements

#### 3. GameControls.jsx
- Displays game status (whose turn, ball counts)
- Shows player's balls vs AI's balls
- Provides game reset functionality
- Real-time turn indicator

#### 4. API Client (utils/api.js)
- Axios-based HTTP client
- Abstracts backend API calls
- Handles request/response formatting
- Provides typed API methods

### Backend Components

#### 1. API Layer (api/main.py)
- **FastAPI application** with CORS middleware
- RESTful endpoints for game operations
- Request/response validation using Pydantic
- In-memory game state management (upgradeable to Redis/DB)

**Endpoints:**
- `POST /game/new` - Create new game
- `GET /game/{game_id}` - Get game state
- `POST /game/move` - Submit player move
- `POST /ai/move/{game_id}` - Request AI move

#### 2. Physics Engine (game/physics.py)
- **Ball class**: Represents individual balls with position, velocity
- **PhysicsEngine class**: Handles all physics calculations

**Responsibilities:**
- Ball-to-ball collision detection
- Collision resolution (momentum transfer)
- Wall collision detection and bounce
- Friction simulation
- Position updates

**Algorithm:**
```python
For each simulation step:
  1. Update ball positions based on velocity
  2. Apply friction to slow down balls
  3. Check and resolve wall collisions
  4. Check and resolve ball-to-ball collisions
  5. Check if balls are in pockets
```

#### 3. AI Agent (ai/agent.py)
- **PoolAI class**: Implements AI opponent logic
- Supports multiple difficulty levels (easy, medium, hard)

**AI Strategy:**
```python
For each AI turn:
  1. Identify target balls (AI's assigned balls)
  2. For each target ball:
     a. Find closest pocket
     b. Calculate shot angle and power
     c. Estimate shot difficulty
  3. Select best shot based on difficulty score
  4. Add randomness based on difficulty level
  5. Return shot parameters
```

**Difficulty Implementation:**
- **Easy (50% accuracy)**: Large angle randomness, power variation
- **Medium (75% accuracy)**: Moderate randomness
- **Hard (95% accuracy)**: Minimal randomness, near-perfect shots

## Data Flow

### Player Move Flow

```
1. User clicks on table to aim
   ↓
2. User adjusts power slider
   ↓
3. User clicks "Shoot"
   ↓
4. Frontend sends to backend:
   POST /game/move
   {
     game_id: "...",
     cue_ball_position: {x, y},
     target_position: {x, y},
     power: 0.75
   }
   ↓
5. Backend validates move
   ↓
6. Backend calculates:
   - Ball trajectory
   - Collisions
   - Final positions
   ↓
7. Backend returns result:
   {
     success: true,
     game_state: {...}
   }
   ↓
8. Frontend animates result
   ↓
9. Frontend requests AI move
   POST /ai/move/{game_id}
   ↓
10. Backend AI calculates best shot
    ↓
11. Backend executes AI move
    ↓
12. Backend returns AI result
    ↓
13. Frontend animates AI move
```

## Why Backend-Authoritative Physics?

### ✅ Advantages

1. **Security**
   - Server validates all moves
   - Prevents cheating and manipulation
   - Client cannot forge game results

2. **Consistency**
   - Single source of truth
   - Same physics across all clients
   - Deterministic results

3. **AI Integration**
   - AI needs physics engine to simulate shots
   - Centralized logic easier to maintain
   - AI can run complex simulations

4. **Multiplayer Ready**
   - Architecture supports multiple players
   - Central game state management
   - Easy to add spectator mode

5. **Future Scalability**
   - Can add replay functionality
   - Match history and statistics
   - Tournament support

### ⚠️ Trade-offs

1. **Latency**
   - Network round-trip for each move
   - Solution: Optimistic UI updates

2. **Server Load**
   - Physics calculations on server
   - Solution: Efficient algorithms, caching

## Performance Considerations

### Frontend
- Canvas rendering at 60 FPS
- Smooth animations with requestAnimationFrame
- Lazy loading of assets
- Debounced API calls

### Backend
- Async/await for concurrent requests
- Efficient collision detection algorithms
- In-memory state for fast access
- Prepared for horizontal scaling

## Security Considerations

### Input Validation
- All API inputs validated with Pydantic
- Move validation on server side
- Rate limiting (future enhancement)

### CORS Policy
- Restricted to known origins
- Configurable for production

### Game State Integrity
- State stored server-side only
- Client cannot modify game state
- All mutations go through API

## Testing Strategy

### Backend Tests
- Unit tests for physics calculations
- Unit tests for AI logic
- Integration tests for API endpoints
- Test coverage: ~90%

### Frontend Tests (Future)
- Component unit tests with React Testing Library
- Integration tests with Mock Service Worker
- E2E tests with Playwright

## Deployment Architecture (Production)

```
┌─────────────┐
│   Nginx     │  ← SSL Termination, Static Files
│   (Proxy)   │
└──────┬──────┘
       │
   ┌───┴────┐
   │        │
┌──┴──┐  ┌──┴──────┐
│React│  │ Gunicorn│  ← Multiple Uvicorn Workers
│Build│  │ +       │
└─────┘  │ Uvicorn │
         └────┬────┘
              │
         ┌────┴────┐
         │ Redis   │  ← Session Storage (future)
         └─────────┘
```

## Technology Choices Rationale

### Frontend: React + Vite
- **React**: Component-based, large ecosystem
- **Vite**: Fast dev server, excellent DX
- **Canvas API**: Best for 2D game rendering

### Backend: FastAPI + Python
- **FastAPI**: Modern, fast, auto-documentation
- **Python**: Excellent for AI/ML, NumPy for math
- **Uvicorn**: High-performance ASGI server

### No Database (Yet)
- In-memory storage sufficient for MVP
- Easy to add PostgreSQL/MongoDB later
- Redis for sessions in production

## Future Enhancements

### Short Term
- [ ] Add ball pocketing detection
- [ ] Implement proper 8-ball rules
- [ ] Add sound effects
- [ ] Mobile responsive design

### Medium Term
- [ ] Multiplayer support (WebSockets)
- [ ] User accounts and authentication
- [ ] Match history and statistics
- [ ] Multiple AI difficulty presets

### Long Term
- [ ] 3D graphics with Three.js
- [ ] Machine learning for adaptive AI
- [ ] Tournament system
- [ ] Social features (friends, leaderboards)

## Conclusion

This architecture provides a solid foundation for a scalable, secure, and maintainable 8 Ball Pool game. The separation of concerns between frontend and backend, combined with server-authoritative physics, ensures both a great user experience and robust game mechanics.
