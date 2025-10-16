import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const createGame = async () => {
  const response = await api.post('/game/new')
  return response.data
}

export const getGame = async (gameId) => {
  const response = await api.get(`/game/${gameId}`)
  return response.data
}

export const submitMove = async (gameId, moveData) => {
  const response = await api.post('/game/move', {
    game_id: gameId,
    ...moveData,
  })
  return response.data
}

export const requestAIMove = async (gameId) => {
  const response = await api.post(`/ai/move/${gameId}`)
  return response.data
}

export default api
