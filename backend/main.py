import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from game.poker import PokerGame, Phase, PlayerStatus
from game.llm_player import get_llm_action, get_llm_name, reset_model_cache
from game.history_db import init_db, save_session, get_history, get_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Texas Hold'em Poker")
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# room_id -> PokerGame
games: dict[str, PokerGame] = {}
# room_id -> {player_id -> WebSocket}
connections: dict[str, dict[str, WebSocket]] = {}
# room_id -> host player_id
room_hosts: dict[str, str] = {}
# room_id -> ISO timestamp of when the room was created
room_created_at: dict[str, str] = {}

PERSONALITIES = [
    {"tag": "LAG",     "desc": "You are loose-aggressive: you play many hands, raise frequently, and put constant pressure on opponents. You bluff often."},
    {"tag": "TAG",     "desc": "You are tight-aggressive: you fold most hands, but when you play you raise and bet hard. Occasional well-timed bluffs only."},
    {"tag": "Bluffer", "desc": "You are an unpredictable bluffer: you frequently bet and raise with weak hands to steal pots, mixing in strong hands to keep opponents guessing."},
    {"tag": "Rock",    "desc": "You are a rock: extremely tight, only playing premium hands. When you bet, opponents should be afraid. You almost never bluff."},
    {"tag": "Station", "desc": "You are a calling station: loose and passive, you call most bets but rarely raise. You chase draws and see many showdowns."},
    {"tag": "Maniac",  "desc": "You are a maniac: you raise and re-raise relentlessly with almost any two cards. Your aggression is non-stop."},
    {"tag": "Shark",   "desc": "You are a calculated shark: you carefully observe opponents, adapt to their tendencies, and exploit weakness with well-timed aggression."},
    {"tag": "Nit",     "desc": "You are a nit: you fold almost everything, patiently waiting for absolute premium hands before committing chips."},
]


class CreateRoomRequest(BaseModel):
    num_humans: int = 2
    num_llms: int = 1
    small_blind: int = 10
    big_blind: int = 20
    starting_stack: int = 1000


class RoomInfo(BaseModel):
    room_id: str
    num_humans: int
    num_llms: int
    players_joined: int
    started: bool
    small_blind: int
    big_blind: int
    starting_stack: int


class ConfigUpdate(BaseModel):
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None


@app.get("/config")
async def get_config():
    return {"llm_base_url": settings.llm_base_url, "llm_model": settings.llm_model}


@app.patch("/config")
async def update_config(body: ConfigUpdate):
    if body.llm_base_url is not None:
        settings.llm_base_url = body.llm_base_url
        reset_model_cache()
    if body.llm_api_key is not None:
        settings.llm_api_key = body.llm_api_key
    if body.llm_model is not None:
        settings.llm_model = body.llm_model
        reset_model_cache()
    logger.info(f"LLM config updated: url={settings.llm_base_url!r} model={settings.llm_model!r}")
    return {"llm_base_url": settings.llm_base_url, "llm_model": settings.llm_model}


@app.get("/rooms")
async def list_rooms() -> list[RoomInfo]:
    result = []
    for rid, game in games.items():
        result.append(RoomInfo(
            room_id=rid,
            num_humans=game.num_human_slots,
            num_llms=game.num_llm_slots,
            players_joined=len([p for p in game.players if not p.is_llm]),
            started=game.phase != Phase.WAITING,
            small_blind=game.small_blind,
            big_blind=game.big_blind,
            starting_stack=game.starting_stack,
        ))
    return result


@app.post("/rooms")
async def create_room(req: CreateRoomRequest) -> dict:
    room_id = str(uuid.uuid4())[:8]
    game = PokerGame(
        room_id=room_id,
        small_blind=req.small_blind,
        big_blind=req.big_blind,
        starting_stack=req.starting_stack,
    )
    game.num_human_slots = req.num_humans
    game.num_llm_slots = req.num_llms
    games[room_id] = game
    connections[room_id] = {}
    room_created_at[room_id] = datetime.now(timezone.utc).isoformat()
    logger.info(f"Room {room_id} created: {req.num_humans} humans, {req.num_llms} LLMs")
    return {"room_id": room_id}


@app.delete("/rooms/{room_id}")
async def delete_room(room_id: str):
    if room_id not in games:
        raise HTTPException(status_code=404, detail="Room not found")
    game = games[room_id]
    # Persist history before removing
    if game.phase != Phase.WAITING:
        try:
            players_data = [
                {
                    "name": p.name,
                    "is_llm": p.is_llm,
                    "personality": p.personality,
                    "final_stack": p.stack,
                }
                for p in game.players
            ]
            save_session(
                room_id=room_id,
                created_at=room_created_at.get(room_id, ""),
                num_hands=len(game.hand_history),
                small_blind=game.small_blind,
                big_blind=game.big_blind,
                starting_stack=game.starting_stack,
                players=players_data,
                hand_history=game.hand_history,
            )
        except Exception as exc:
            logger.error(f"Failed to save history for room {room_id}: {exc}")
    for ws in list(connections.get(room_id, {}).values()):
        try:
            await ws.close(code=1001)
        except Exception:
            pass
    games.pop(room_id, None)
    connections.pop(room_id, None)
    room_hosts.pop(room_id, None)
    room_created_at.pop(room_id, None)
    return {"deleted": room_id}


@app.get("/history")
async def list_history():
    return get_history(limit=50)


@app.get("/history/{session_id}")
async def get_history_detail(session_id: int):
    detail = get_session(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return detail


@app.get("/rooms/{room_id}")
async def get_room(room_id: str) -> RoomInfo:
    game = games.get(room_id)
    if not game:
        raise HTTPException(status_code=404, detail="Room not found")
    return RoomInfo(
        room_id=room_id,
        num_humans=game.num_human_slots,
        num_llms=game.num_llm_slots,
        players_joined=len([p for p in game.players if not p.is_llm]),
        started=game.phase != Phase.WAITING,
        small_blind=game.small_blind,
        big_blind=game.big_blind,
        starting_stack=game.starting_stack,
    )


async def broadcast(room_id: str, message: dict, exclude: Optional[str] = None):
    game = games.get(room_id)
    if not game:
        return
    dead = []
    for pid, ws in list(connections.get(room_id, {}).items()):
        if pid == exclude:
            continue
        try:
            state = game.state_for_player(pid)
            state["type"] = "game_state"
            state.update({k: v for k, v in message.items()})
            await ws.send_json(state)
        except Exception:
            dead.append(pid)
    for pid in dead:
        connections[room_id].pop(pid, None)


async def send_to(room_id: str, player_id: str, message: dict):
    ws = connections.get(room_id, {}).get(player_id)
    if ws:
        try:
            await ws.send_json(message)
        except Exception:
            pass


async def run_llm_turns(room_id: str):
    game = games.get(room_id)
    if not game:
        return

    while game.phase not in (Phase.WAITING, Phase.SHOWDOWN):
        current = game.current_player()
        if current is None:
            logger.info(f"run_llm_turns: no current player in phase={game.phase.value}, stopping")
            break

        logger.info(f"run_llm_turns: phase={game.phase.value} turn={current.name} is_llm={current.is_llm}")

        if not current.is_llm:
            # Never auto-fold humans — always wait for their input.
            # When they reconnect and send an 'action' message, run_llm_turns is called again.
            connected = current.id in connections.get(room_id, {})
            logger.info(f"Waiting for human {current.name} (connected={connected})")
            break

        prompt = game.text_state_for_llm(current)
        logger.info(f"LLM {current.name} ({current.personality}) thinking...")

        await broadcast(room_id, {"llm_thinking": current.id})
        await asyncio.sleep(0.5)

        action, amount = await get_llm_action(prompt, personality=current.personality_prompt)
        msg = game.apply_action(current.id, action, amount)
        logger.info(f"LLM {current.name} action: {action} {amount} -> {msg!r}")

        await broadcast(room_id, {"last_action": msg})

        if game.phase == Phase.SHOWDOWN:
            asyncio.create_task(maybe_start_new_hand(room_id))
            return

        await asyncio.sleep(0.8)


async def maybe_start_new_hand(room_id: str):
    game = games.get(room_id)
    if not game:
        return
    logger.info(f"Showdown complete — starting new hand in 10s (room {room_id})")
    await asyncio.sleep(10)
    logger.info(f"Starting new hand (room {room_id})")
    game.advance_dealer()
    game.winners = []
    game.start_hand()
    await broadcast(room_id, {"event": "new_hand"})
    await run_llm_turns(room_id)


@app.websocket("/ws/{room_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str):
    game = games.get(room_id)
    if not game:
        await websocket.close(code=4004)
        return

    await websocket.accept()
    connections.setdefault(room_id, {})[player_id] = websocket
    logger.info(f"Player {player_id} connected to room {room_id}")

    # If the game is mid-hand and it's this player's turn, nudge run_llm_turns
    # (in case we were waiting for this human to reconnect)
    if game.phase not in (Phase.WAITING, Phase.SHOWDOWN):
        current = game.current_player()
        if current and current.id == player_id and not current.is_llm:
            logger.info(f"Reconnected human {current.name} is current player — sending state")
            try:
                state = game.state_for_player(player_id)
                state["type"] = "game_state"
                await websocket.send_json(state)
            except Exception:
                pass

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "join":
                name = data.get("name", f"Player{player_id[:4]}")
                existing = game.get_player(player_id)
                if not existing:
                    seat = data.get("seat", len(game.players))
                    taken_seats = {p.seat for p in game.players}
                    while seat in taken_seats:
                        seat += 1
                    game.add_player(player_id, name, seat, is_llm=False)
                    if not room_hosts.get(room_id):
                        room_hosts[room_id] = player_id
                await broadcast(room_id, {"event": "player_joined", "name": name})

            elif msg_type == "leave_room":
                # Player leaves voluntarily — keep their seat in game, just disconnect
                connections.get(room_id, {}).pop(player_id, None)
                p = game.get_player(player_id)
                if p:
                    await broadcast(room_id, {"event": "player_left", "name": p.name})
                # Send ack before closing so client can navigate away cleanly
                try:
                    await websocket.send_json({"type": "left"})
                except Exception:
                    pass
                return

            elif msg_type == "start_game":
                if game.phase != Phase.WAITING:
                    await send_to(room_id, player_id, {"type": "error", "msg": "Game already started"})
                    continue

                existing_llms = [p for p in game.players if p.is_llm]
                llms_to_add = game.num_llm_slots - len(existing_llms)
                taken_seats = {p.seat for p in game.players}
                taken_names = [p.name for p in game.players]
                used_personalities = set()
                for i in range(llms_to_add):
                    seat = 0
                    while seat in taken_seats:
                        seat += 1
                    taken_seats.add(seat)
                    llm_id = f"llm_{uuid.uuid4().hex[:6]}"
                    name = await get_llm_name(taken_names)
                    taken_names.append(name)
                    game.add_player(llm_id, name, seat, is_llm=True)
                    # Assign a personality (prefer unique ones first)
                    available = [p for p in PERSONALITIES if p["tag"] not in used_personalities]
                    if not available:
                        available = PERSONALITIES
                    pers = random.choice(available)
                    used_personalities.add(pers["tag"])
                    llm_player = game.get_player(llm_id)
                    llm_player.personality = pers["tag"]
                    llm_player.personality_prompt = pers["desc"]
                    logger.info(f"LLM {name} assigned personality: {pers['tag']}")

                game.start_hand()
                await broadcast(room_id, {"event": "game_started"})
                asyncio.create_task(run_llm_turns(room_id))

            elif msg_type == "action":
                if game.phase in (Phase.WAITING, Phase.SHOWDOWN):
                    continue
                current = game.current_player()
                if current is None or current.id != player_id:
                    await send_to(room_id, player_id, {"type": "error", "msg": "Not your turn"})
                    continue

                action = data.get("action", "fold")
                amount = int(data.get("amount", 0))
                logger.info(f"Human {current.name} action: {action} {amount}")
                result = game.apply_action(player_id, action, amount)
                await broadcast(room_id, {"last_action": result})

                if game.phase == Phase.SHOWDOWN:
                    asyncio.create_task(maybe_start_new_hand(room_id))
                else:
                    asyncio.create_task(run_llm_turns(room_id))

            elif msg_type == "new_round":
                if game.phase == Phase.SHOWDOWN:
                    game.advance_dealer()
                    game.winners = []
                    game.start_hand()
                    await broadcast(room_id, {"event": "new_hand"})
                    asyncio.create_task(run_llm_turns(room_id))

            elif msg_type == "ping":
                state = game.state_for_player(player_id)
                state["type"] = "game_state"
                await websocket.send_json(state)

    except WebSocketDisconnect:
        logger.info(f"Player {player_id} disconnected from room {room_id}")
        connections.get(room_id, {}).pop(player_id, None)
        p = game.get_player(player_id)
        if p and game.phase != Phase.WAITING:
            await broadcast(room_id, {"event": "player_left", "name": p.name})
