import { useState, useEffect } from 'react'
import PoolTable from './components/PoolTable'
import GameControls from './components/GameControls'
import { createGame, submitMove, requestAIMove } from './utils/api'
import './App.css'

function App() {
  const [gameState, setGameState] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const startNewGame = async () => {
    setLoading(true)
    setError(null)
    try {
      const game = await createGame()
      setGameState(game)
    } catch (err) {
      setError('Failed to start game: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const handlePlayerMove = async (moveData) => {
    if (!gameState || gameState.player_turn !== 'player') return
    
    setLoading(true)
    try {
      const result = await submitMove(gameState.game_id, moveData)
      setGameState(result.game_state)
      
      // Trigger AI move after player
      setTimeout(async () => {
        const aiResult = await requestAIMove(gameState.game_id)
        setGameState(aiResult.game_state)
      }, 1000)
    } catch (err) {
      setError('Move failed: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>🎱 8 Ball Pool</h1>
        <p>Play against AI</p>
      </header>
      
      <main className="app-main">
        {error && <div className="error">{error}</div>}
        
        {!gameState ? (
          <div className="start-screen">
            <button 
              onClick={startNewGame} 
              disabled={loading}
              className="start-button"
            >
              {loading ? 'Starting...' : 'Start New Game'}
            </button>
          </div>
        ) : (
          <>
            <GameControls 
              gameState={gameState}
              onNewGame={startNewGame}
            />
            <PoolTable 
              gameState={gameState}
              onMove={handlePlayerMove}
              disabled={loading || gameState.player_turn !== 'player'}
            />
          </>
        )}
      </main>
    </div>
  )
}

export default App
