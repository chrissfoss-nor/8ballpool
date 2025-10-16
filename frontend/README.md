# 8 Ball Pool - Frontend

React frontend for 8 Ball Pool game with AI opponent.

## Structure

```
frontend/
├── src/
│   ├── components/      # React components
│   ├── utils/          # Utility functions and API client
│   └── main.jsx        # Entry point
├── public/             # Static assets
├── package.json        # NPM dependencies
├── vite.config.js      # Vite configuration
└── README.md          # This file
```

## Installation

```bash
cd frontend
npm install
```

## Running the Development Server

```bash
cd frontend
npm run dev
```

The application will be available at http://localhost:3000

## Building for Production

```bash
cd frontend
npm run build
```

## Features

- Interactive pool table with physics visualization
- Play against AI opponent
- Real-time game state updates
- Responsive design

## Development

The frontend is responsible for:
- Rendering the game interface
- Capturing user input (aiming, power)
- Visualizing physics (ball movement, collisions)
- Communicating with backend API

Note: Physics calculations are performed on the backend for authoritative game state,
but the frontend provides smooth visual feedback.
