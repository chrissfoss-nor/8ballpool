import { useRef, useEffect, useState } from 'react'
import './PoolTable.css'

const PoolTable = ({ gameState, onMove, disabled }) => {
  const canvasRef = useRef(null)
  const [aimAngle, setAimAngle] = useState(0)
  const [power, setPower] = useState(0.5)
  const [cueBallPos, setCueBallPos] = useState({ x: 250, y: 150 })

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    drawTable(ctx, canvas.width, canvas.height)
  }, [gameState, aimAngle, power, cueBallPos])

  const drawTable = (ctx, width, height) => {
    // Clear canvas
    ctx.clearRect(0, 0, width, height)

    // Draw table
    ctx.fillStyle = '#0a5f0a'
    ctx.fillRect(0, 0, width, height)

    // Draw border
    ctx.strokeStyle = '#8B4513'
    ctx.lineWidth = 20
    ctx.strokeRect(0, 0, width, height)

    // Draw pockets
    const pockets = [
      { x: 10, y: 10 },
      { x: width / 2, y: 10 },
      { x: width - 10, y: 10 },
      { x: 10, y: height - 10 },
      { x: width / 2, y: height - 10 },
      { x: width - 10, y: height - 10 },
    ]
    
    pockets.forEach(pocket => {
      ctx.fillStyle = '#000'
      ctx.beginPath()
      ctx.arc(pocket.x, pocket.y, 15, 0, Math.PI * 2)
      ctx.fill()
    })

    // Draw cue ball (white)
    ctx.fillStyle = '#fff'
    ctx.beginPath()
    ctx.arc(cueBallPos.x, cueBallPos.y, 10, 0, Math.PI * 2)
    ctx.fill()
    ctx.strokeStyle = '#000'
    ctx.lineWidth = 1
    ctx.stroke()

    // Draw player balls (solid)
    if (gameState?.player_balls) {
      gameState.player_balls.forEach((ballNum, idx) => {
        const x = 100 + idx * 25
        const y = 100
        drawBall(ctx, x, y, ballNum, false)
      })
    }

    // Draw AI balls (striped)
    if (gameState?.ai_balls) {
      gameState.ai_balls.forEach((ballNum, idx) => {
        const x = 100 + idx * 25
        const y = 200
        drawBall(ctx, x, y, ballNum, true)
      })
    }

    // Draw aiming line if it's player's turn
    if (!disabled && gameState?.player_turn === 'player') {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)'
      ctx.lineWidth = 2
      ctx.setLineDash([5, 5])
      ctx.beginPath()
      ctx.moveTo(cueBallPos.x, cueBallPos.y)
      const aimLength = 100 * power
      const endX = cueBallPos.x + Math.cos(aimAngle * Math.PI / 180) * aimLength
      const endY = cueBallPos.y + Math.sin(aimAngle * Math.PI / 180) * aimLength
      ctx.lineTo(endX, endY)
      ctx.stroke()
      ctx.setLineDash([])
    }
  }

  const drawBall = (ctx, x, y, number, striped) => {
    const colors = {
      1: '#FFD700', 2: '#0000FF', 3: '#FF0000', 4: '#800080',
      5: '#FFA500', 6: '#006400', 7: '#8B0000', 8: '#000000',
      9: '#FFD700', 10: '#0000FF', 11: '#FF0000', 12: '#800080',
      13: '#FFA500', 14: '#006400', 15: '#8B0000'
    }

    ctx.fillStyle = colors[number] || '#888'
    ctx.beginPath()
    ctx.arc(x, y, 10, 0, Math.PI * 2)
    ctx.fill()
    
    if (striped) {
      ctx.fillStyle = '#fff'
      ctx.fillRect(x - 10, y - 3, 20, 6)
    }

    ctx.strokeStyle = '#000'
    ctx.lineWidth = 1
    ctx.stroke()

    // Draw number
    ctx.fillStyle = number === 8 ? '#fff' : '#000'
    ctx.font = 'bold 8px Arial'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(number.toString(), x, y)
  }

  const handleCanvasClick = (e) => {
    if (disabled) return

    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    // Calculate angle from cue ball to click point
    const dx = x - cueBallPos.x
    const dy = y - cueBallPos.y
    const angle = Math.atan2(dy, dx) * 180 / Math.PI
    setAimAngle(angle)
  }

  const handleShoot = () => {
    if (disabled) return

    onMove({
      cue_ball_position: cueBallPos,
      target_position: {
        x: cueBallPos.x + Math.cos(aimAngle * Math.PI / 180) * 100,
        y: cueBallPos.y + Math.sin(aimAngle * Math.PI / 180) * 100,
      },
      power: power,
    })
  }

  return (
    <div className="pool-table-container">
      <canvas
        ref={canvasRef}
        width={800}
        height={400}
        onClick={handleCanvasClick}
        className="pool-canvas"
      />
      <div className="controls">
        <div className="control-group">
          <label>Power: {(power * 100).toFixed(0)}%</label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={power}
            onChange={(e) => setPower(parseFloat(e.target.value))}
            disabled={disabled}
          />
        </div>
        <button
          onClick={handleShoot}
          disabled={disabled}
          className="shoot-button"
        >
          Shoot
        </button>
      </div>
    </div>
  )
}

export default PoolTable
