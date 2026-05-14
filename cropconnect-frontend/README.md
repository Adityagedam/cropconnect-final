# CropConnect — Frontend

Field-to-phone IoT platform for modern farming. Real sensors measure soil, water
and climate; a multilanguage app and web dashboard turn that data into decisions
farmers can act on instantly.

## Tech stack
- React 18 + Vite
- Tailwind CSS 3 + `tailwindcss-animate`
- Radix UI primitives (`@radix-ui/react-label`, `react-slot`, `react-tabs`)
- `lucide-react` icons, `sonner` toasts
- `axios` for API calls, `react-router-dom` for routing

## Run locally

```bash
# 1. Install dependencies
yarn install        # or: npm install

# 2. (Optional local backend URL; production must set this explicitly)
echo "VITE_BACKEND_URL=http://localhost:8001/api" > .env
echo "VITE_PUBLIC_TRANSLATION_ENABLED=false" >> .env

# 3. Start dev server
yarn start          # opens http://localhost:3000
```

## Build for production

```bash
yarn build          # Vite output in ./build
```

## Project layout

```
src/
├── App.jsx                # mounts app routes
├── App.css                # base wrapper styles
├── index.jsx              # Vite entry, renders <App />
├── index.css              # global tokens, fonts, tailwind layers
├── lib/
│   └── utils.js           # cn() classname helper
├── components/
│   ├── ui/                # shadcn-style primitives
│   │   ├── button.jsx
│   │   ├── input.jsx
│   │   ├── label.jsx
│   │   ├── tabs.jsx
│   │   └── textarea.jsx
│   └── landing/           # marketing page sections
│       ├── Header.jsx
│       ├── Hero.jsx
│       ├── LiveSensorCard.jsx
│       ├── ImpactStats.jsx
│       ├── PrototypeSection.jsx
│       ├── FeaturesSection.jsx
│       ├── MobileAppSection.jsx
│       ├── HowItWorks.jsx
│       ├── BenefitsSection.jsx
│       ├── GoalsSection.jsx
│       ├── EcosystemSection.jsx
│       ├── ContactSection.jsx
│       └── Footer.jsx
└── pages/
    └── LandingPage.jsx    # composes all sections in order
```

## Production setup
- Set `VITE_BACKEND_URL` to your deployed FastAPI backend URL before building.
- Set `VITE_PUBLIC_TRANSLATION_ENABLED=true` only when backend translation is enabled and rate limited. The auto-translator scans the whole app while skipping form inputs, code blocks, API keys, device IDs, email addresses, and marked private values.
- Optionally set `VITE_PUBLIC_TRANSLATION_FALLBACK_URL` to a second translator endpoint. The frontend first tries `/api/utils/translate`, then falls back to that URL using a CropConnect-compatible payload and a LibreTranslate-style payload.
- New signups open a sensor setup flow. The generated `sensorDeviceId` must be used by ESP32 nodes when posting telemetry.
- Contact enquiries post to `/api/enquiries`; if SMTP is not configured, the form opens a pre-filled email to `cropconnectco@gmail.com`.
- AI chat posts to `/api/ai/chat`; configure backend `AI_PROVIDER=openai` + `OPENAI_API_KEY`, or `AI_PROVIDER=gemini` + `GEMINI_API_KEY`, for AI answers. `GOOGLE_API_KEY` + `GOOGLE_CSE_ID` are only for Google search context.
- Live weather comes from `/api/weather/forecast`.
- Live market prices come from authenticated `/api/market/prices`; configure `DATA_GOV_API_KEY` on the backend so the dashboard can fetch mandi records for the user's saved profile location. AI market advice uses `/api/market/insights`, which requires `DATA_GOV_API_KEY` and the configured AI provider key.
- Fonts are pulled from Google Fonts (Fraunces / DM Sans / JetBrains Mono).
