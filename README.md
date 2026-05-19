# Texas Hold'em — LLM Poker

A browser-based Texas Hold'em poker game where humans play against LLM-controlled opponents. Built with a Vue 3 frontend and a Python FastAPI backend, connected to any OpenAI-compatible LLM API.

![Poker table screenshot](https://raw.githubusercontent.com/icewall905/th-llm/main/docs/screenshot.png)

---

## Features

- **Multiplayer** — multiple human players join the same room via a shareable link
- **LLM opponents** — bots powered by any OpenAI-compatible API (llama.cpp, Ollama, vLLM, OpenAI, etc.)
- **Bot personalities** — each LLM bot is assigned a random play style (LAG, TAG, Rock, Maniac, Shark, Bluffer, etc.) that shapes its system prompt
- **Rich LLM context** — bots receive pot odds, player tendency stats (VPIP%, raise frequency), and recent hand history so they play with memory
- **Configurable LLM endpoint** — change the API URL, key, and model from within the game's lobby settings without restarting
- **Mobile-friendly** — responsive layout for phones and tablets; action bar with tap-friendly buttons
- **Room persistence** — room ID is part of the URL hash; refreshing or reopening the link rejoins the same seat
- **Human-first** — the game waits indefinitely for a human player to act; disconnected humans are never auto-folded

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- An OpenAI-compatible LLM API endpoint (local or remote)

### 1. Clone

```bash
git clone https://github.com/icewall905/th-llm.git
cd th-llm
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```env
LLM_BASE_URL=http://localhost:8080/v1   # your LLM endpoint
LLM_MODEL=                              # blank = auto-detect
LLM_API_KEY=none                        # set if your API requires auth
```

### 3. Run

```bash
docker compose up --build
```

Open **http://localhost:3700** in your browser.

> The LLM endpoint can also be changed at runtime via the **⚙ LLM Settings** button in the lobby — no restart needed.

---

## Architecture

```
th-llm/
├── docker-compose.yml
├── .env                    # your config (not committed)
├── .env.example            # template
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py             # FastAPI app — WebSocket hub, REST API, LLM turn orchestration
│   ├── config.py           # pydantic-settings config (reads .env)
│   └── game/
│       ├── poker.py        # full Texas Hold'em state machine, hand evaluator, LLM prompt builder
│       └── llm_player.py   # LLM API client, action parser, name generator
└── frontend/
    ├── Dockerfile
    ├── nginx.conf          # proxies /api/ and /ws/ to backend
    ├── index.html
    └── src/
        ├── App.vue                      # lobby, waiting room, game screens
        └── components/
            ├── PokerTable.vue           # felt table, seats, community cards
            ├── PlayerSeat.vue           # player badge with cards, chips, role badges
            ├── CardSprite.vue           # card renderer (face-up and face-down)
            ├── ActionPanel.vue          # fold/call/raise controls (desktop)
            ├── GameLog.vue              # scrolling action history
            └── QuickStart.vue           # rules overlay
```

**Ports (default):**

| Service | Host port | Container port |
|---------|-----------|----------------|
| Frontend (Nginx) | 3700 | 80 |
| Backend (FastAPI) | 8700 | 8000 |

Change the host ports in `docker-compose.yml` if those are taken.

---

## How It Works

### Rooms & Players

- Create a room from the lobby — choose how many human and LLM seats
- Share the URL (the room ID is appended as a `#hash`) — others paste the URL to join
- Game starts when the host clicks **Start Game**; LLM players are added automatically at that point

### LLM Integration

Each LLM player gets a randomly assigned personality (e.g. "Maniac", "Rock", "Shark") injected into their system prompt. On every turn they receive a structured text prompt including:

- Hole cards and community cards
- Pot size, stack sizes, and pot odds
- Position and valid actions
- Action history for the current betting round
- Per-player tendency stats (VPIP%, raise count, showdown hands) across all previous hands
- Recent hand results (last 4 hands)

The model responds with `FOLD`, `CHECK`, `CALL`, or `RAISE <amount>`. Thinking/reasoning output (e.g. Qwen3's `<think>` blocks) is parsed before the action line.

### WebSocket Protocol

All real-time communication uses a single WebSocket per player at `/ws/{room_id}/{player_id}`. The server always sends the full game state on every update, sanitized for the receiving player (hole cards are hidden for opponents except at showdown).

---

## Configuration

All settings are in `.env` and can also be patched at runtime via `PATCH /api/config`:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_BASE_URL` | `http://localhost:8080/v1` | OpenAI-compatible API base URL |
| `LLM_MODEL` | *(blank)* | Model name; blank = auto-detect from `/v1/models` |
| `LLM_API_KEY` | `none` | API key; use `none` for local servers |
| `SMALL_BLIND` | `10` | Default small blind (overridable per room) |
| `BIG_BLIND` | `20` | Default big blind |
| `STARTING_STACK` | `1000` | Starting chip stack per player |

---

## Bot Personalities

Bots are randomly assigned one of eight play styles at game start:

| Tag | Style |
|-----|-------|
| **LAG** | Loose-aggressive — plays many hands, raises often, bluffs frequently |
| **TAG** | Tight-aggressive — folds most hands, bets hard when in |
| **Bluffer** | Raises with weak hands to steal pots |
| **Rock** | Ultra-tight, only plays premium hands |
| **Station** | Loose-passive — calls most bets, rarely raises |
| **Maniac** | Raises and re-raises relentlessly |
| **Shark** | Adapts to opponents, exploits weakness |
| **Nit** | Folds almost everything |

The personality tag is shown as a small badge on each bot's seat.

---

## License

MIT
