# 🎱 8 Ball Pool - AI Game

Et fullstack 8-ball pool spill hvor du kan spille mot en AI-motstander.

## 📁 Prosjektstruktur

Prosjektet følger beste praksis for et moderne fullstack-prosjekt med klar separasjon mellom frontend og backend:

```
8ballpool/
├── frontend/                # React frontend applikasjon
│   ├── src/
│   │   ├── components/     # React komponenter (PoolTable, GameControls)
│   │   ├── utils/          # Hjelpefunksjoner og API-klient
│   │   ├── App.jsx         # Hoved-app komponent
│   │   ├── main.jsx        # Entry point
│   │   └── *.css           # Styling
│   ├── public/             # Statiske filer
│   ├── package.json        # NPM avhengigheter
│   ├── vite.config.js      # Vite konfigurasjon
│   └── README.md           # Frontend dokumentasjon
│
├── backend/                # Python backend server
│   ├── src/
│   │   ├── api/           # FastAPI REST endepunkter
│   │   ├── ai/            # AI-logikk for datamotstanderen
│   │   └── game/          # Spilltilstand og fysikk
│   ├── tests/             # Enhetstester
│   ├── requirements.txt   # Python avhengigheter
│   ├── setup.py          # Python pakke-oppsett
│   └── README.md         # Backend dokumentasjon
│
├── .gitignore            # Git ignore-fil
└── README.md             # Denne filen
```

## 🎮 Hvor skal fysikk-logikken være? Frontend eller Backend?

### ✅ Anbefalt: Backend (Server-Authoritative)

**Fysikk-logikken bør primært være i backend av følgende grunner:**

1. **Sikkerhet og Anti-Cheat**
   - Backend validerer alle trekk
   - Forhindrer juksetriks ved å beregne resultater på serveren
   - Klienten kan ikke manipulere spilltilstanden

2. **Konsistens**
   - Samme fysikk-motor for alle spillere
   - Ingen avvik mellom forskjellige nettlesere
   - Deterministiske resultater

3. **AI Integration**
   - AI trenger tilgang til fysikk-motoren for å simulere trekk
   - Backend kan kjøre simuleringer for å finne beste trekk
   - Enklere å implementere avansert AI-logikk

4. **Multiplayer-Ready**
   - Arkitekturen er klar for multiplayer uten store endringer
   - Én sannhetskilde for spilltilstand

### 🎨 Frontend's Rolle

Frontend har fortsatt viktige oppgaver:

1. **Visuell Feedback**
   - Glatt animasjon av ballbevegelser
   - Interpolering mellom tilstander for bedre UX
   - Prediktiv rendering for å redusere latency

2. **Brukerinteraksjon**
   - Fange siktelinje og kraft fra brukeren
   - Vise hvor ballen vil treffe (estimat)
   - Umiddelbar visuell respons

3. **Optimistisk Oppdatering**
   - Kan starte animasjon før server-respons
   - Synkroniserer med server-resultat når det ankommer

### 🏗️ Implementert Arkitektur

```
┌─────────────┐                  ┌─────────────┐
│   Frontend  │                  │   Backend   │
│   (React)   │                  │   (Python)  │
└──────┬──────┘                  └──────┬──────┘
       │                                │
       │  1. User shoots (angle, power) │
       ├───────────────────────────────>│
       │                                │
       │                         2. Physics Engine
       │                            calculates:
       │                            - Ball trajectories
       │                            - Collisions
       │                            - Pocketed balls
       │                                │
       │  3. Returns result state       │
       │<───────────────────────────────┤
       │                                │
       │  4. Animate result             │
       │                                │
       │  5. Request AI move            │
       ├───────────────────────────────>│
       │                                │
       │                         6. AI evaluates:
       │                            - Best target
       │                            - Optimal angle/power
       │                                │
       │  7. Returns AI move + result   │
       │<───────────────────────────────┤
       │                                │
       │  8. Animate AI result          │
       │                                │
```

## 🚀 Kom i Gang

### Forutsetninger

- **Python 3.8+** for backend
- **Node.js 16+** og npm for frontend

### Backend Oppsett

```bash
# Naviger til backend-mappen
cd backend

# Opprett virtuelt miljø
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Installer avhengigheter
pip install -r requirements.txt

# Start serveren
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Backend vil være tilgjengelig på http://localhost:8000

### Frontend Oppsett

```bash
# Naviger til frontend-mappen
cd frontend

# Installer avhengigheter
npm install

# Start utviklingsserveren
npm run dev
```

Frontend vil være tilgjengelig på http://localhost:3000

## 🎯 Funksjoner

- ✅ Interaktiv 8-ball pool bord med physics
- ✅ Spill mot AI-motstander
- ✅ Sanntids spilltilstand
- ✅ Visuell feedback for sikte og kraft
- ✅ RESTful API for kommunikasjon
- ✅ Modulær kodestruktur som følger beste praksis

## 🛠️ Teknologier

### Frontend
- **React 18** - UI framework
- **Vite** - Build tool og dev server
- **Axios** - HTTP-klient
- **Canvas API** - Rendering av spillbrettet

### Backend
- **FastAPI** - Moderne Python web framework
- **NumPy** - Numeriske beregninger for fysikk
- **Uvicorn** - ASGI server
- **Pydantic** - Data validering

## 📚 API Dokumentasjon

Når backend kjører, besøk http://localhost:8000/docs for interaktiv API-dokumentasjon.

### Endepunkter

- `GET /health` - Helsesjekk
- `POST /game/new` - Start nytt spill
- `GET /game/{game_id}` - Hent spilltilstand
- `POST /game/move` - Send spillertrekk
- `POST /ai/move/{game_id}` - Be AI om å gjøre et trekk

## 🔄 Utviklingsflyt

1. **Backend-utvikling**: Endre filer i `backend/src/`
2. **Frontend-utvikling**: Endre filer i `frontend/src/`
3. **Testing**: Bruk `pytest` for backend, React Testing Library for frontend
4. **Building**: 
   - Backend: Ingen build nødvendig (Python)
   - Frontend: `npm run build` for produksjon

## 🚢 Produksjonsdeploy

### Backend
- Bruk Docker container med Uvicorn
- Sett opp miljøvariabler (se `.env.example`)
- Vurder Gunicorn med Uvicorn workers for produksjon

### Frontend
- Build med `npm run build`
- Server de statiske filene via Nginx eller CDN
- Sett korrekt `VITE_API_URL` for produksjon

## 📈 Fremtidige Forbedringer

- [ ] Multiplayer-støtte (2 spillere)
- [ ] Forskjellige AI-vanskelighetsgrader
- [ ] Turneringer og poengssystem
- [ ] 3D-grafikk med Three.js
- [ ] Replay-funksjonalitet
- [ ] Mobile-optimalisering

## 🤝 Bidrag

Bidrag er velkomne! Vennligst opprett en pull request eller issue.

## 📄 Lisens

MIT License - se LICENSE fil for detaljer.
