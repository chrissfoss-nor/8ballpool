import './GameControls.css'

const GameControls = ({ gameState, onNewGame }) => {
  if (!gameState) return null

  return (
    <div className="game-controls">
      <div className="game-info">
        <div className="info-item">
          <span className="label">Current Turn:</span>
          <span className={`value ${gameState.player_turn === 'player' ? 'player' : 'ai'}`}>
            {gameState.player_turn === 'player' ? '👤 Your Turn' : '🤖 AI Turn'}
          </span>
        </div>
        <div className="info-item">
          <span className="label">Status:</span>
          <span className="value">{gameState.status}</span>
        </div>
      </div>
      
      <div className="ball-info">
        <div className="ball-group">
          <h3>Your Balls (Solid)</h3>
          <div className="balls">
            {gameState.player_balls?.map(num => (
              <span key={num} className="ball solid">{num}</span>
            ))}
          </div>
        </div>
        
        <div className="ball-group">
          <h3>AI Balls (Striped)</h3>
          <div className="balls">
            {gameState.ai_balls?.map(num => (
              <span key={num} className="ball striped">{num}</span>
            ))}
          </div>
        </div>
      </div>

      <button onClick={onNewGame} className="new-game-button">
        New Game
      </button>
    </div>
  )
}

export default GameControls
