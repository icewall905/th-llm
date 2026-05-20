<template>
  <div id="poker-app">

    <QuickStart v-if="showQuickStart" @close="showQuickStart = false" />

    <!-- ===== LOBBY ===== -->
    <div v-if="screen === 'lobby'" class="lobby-wrapper">
      <div class="lobby-title-row">
        <h1>🃏 Texas Hold'em</h1>
        <button class="btn-rules" @click="showQuickStart = true" title="How to play">? Rules</button>
      </div>
      <p class="subtitle">Multiplayer poker with AI opponents</p>

      <div class="lobby-layout">
      <div class="lobby-main">
      <div class="lobby-card">
        <div class="form-group">
          <label>Your Name</label>
          <input v-model="playerName" placeholder="Enter your name" maxlength="20" />
        </div>

        <hr class="divider" />
        <button class="settings-toggle" @click="llmSettingsOpen = !llmSettingsOpen">
          ⚙ LLM Settings {{ llmSettingsOpen ? '▲' : '▼' }}
        </button>
        <div v-if="llmSettingsOpen" class="settings-panel">
          <div class="form-group">
            <label>Endpoint URL</label>
            <input v-model="llmConfig.url" placeholder="http://10.0.10.23:8080/v1" />
          </div>
          <div class="form-group">
            <label>API Key (optional)</label>
            <input v-model="llmConfig.apiKey" type="password" placeholder="Leave blank if not needed" />
          </div>
          <div class="form-group">
            <label>Model Name (blank = auto-detect)</label>
            <input v-model="llmConfig.model" placeholder="" />
          </div>
          <button class="btn-secondary" style="width:100%;margin-top:4px" @click="saveLlmConfig">Save</button>
          <div v-if="llmConfigMsg" class="llm-config-msg">{{ llmConfigMsg }}</div>
        </div>

        <hr class="divider" />
        <h3>Create New Game</h3>

        <div class="form-row">
          <div class="form-group">
            <label>Human Players</label>
            <input type="number" v-model.number="newRoom.numHumans" min="0" max="5" />
            <span v-if="newRoom.numHumans === 0" class="spectator-hint">spectator mode</span>
          </div>
          <div class="form-group">
            <label>LLM Players</label>
            <input type="number" v-model.number="newRoom.numLlms" min="0" max="5" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Small Blind</label>
            <input type="number" v-model.number="newRoom.smallBlind" min="1" />
          </div>
          <div class="form-group">
            <label>Big Blind</label>
            <input type="number" v-model.number="newRoom.bigBlind" min="2" />
          </div>
          <div class="form-group">
            <label>Starting Stack</label>
            <input type="number" v-model.number="newRoom.startingStack" min="100" step="100" />
          </div>
        </div>
        <button class="btn-primary" @click="createRoom" :disabled="!playerName.trim()">
          Create Game
        </button>

        <hr class="divider" />
        <h3>Join Existing Game</h3>
        <div class="form-row">
          <div class="form-group flex-grow">
            <input v-model="joinRoomId" placeholder="Room ID" maxlength="8" style="text-transform:uppercase" @input="joinRoomId = joinRoomId.toLowerCase()" />
          </div>
          <button class="btn-secondary" @click="joinRoom" :disabled="!playerName.trim() || !joinRoomId.trim()" :title="!playerName.trim() ? 'Enter your name above first' : ''">
            Join
          </button>
        </div>
        <div v-if="joinRoomId.trim() && !playerName.trim()" class="join-hint">
          ↑ Enter your name above to join
        </div>

        <div v-if="openRooms.length" class="open-rooms">
          <div class="open-rooms-title">Open Rooms</div>
          <div
            v-for="r in openRooms"
            :key="r.room_id"
            class="room-row"
            @click="joinRoomId = r.room_id"
            :class="{ selected: joinRoomId === r.room_id }"
          >
            <span class="room-id">{{ r.room_id }}</span>
            <span class="room-info">
              {{ r.players_joined }}/{{ r.num_humans }} humans · {{ r.num_llms }} bots ·
              {{ r.small_blind }}/{{ r.big_blind }} blinds ·
              <span v-if="r.started" class="started">In progress</span>
              <span v-else class="waiting">Waiting</span>
            </span>
            <button class="btn-end" @click.stop="deleteRoom(r.room_id)" title="End session">✕</button>
          </div>
        </div>

        <div v-if="lobbyError" class="error">{{ lobbyError }}</div>
      </div>
      </div><!-- /lobby-main -->

      <HistoryExplorer :sessions="gameHistory" />

      </div><!-- /lobby-layout -->
    </div>

    <!-- ===== WAITING ROOM ===== -->
    <div v-else-if="screen === 'waiting'" class="waiting-room">
      <h2>Room: <span class="room-code">{{ roomId }}</span></h2>
      <p class="hint">Share this room code with other players</p>
      <div class="players-list">
        <div v-for="p in gameState.players" :key="p.id" class="player-row">
          <span>{{ p.name }}</span>
          <span v-if="p.is_llm" class="llm-tag">🤖 AI</span>
          <span v-if="p.id === myId" class="you-tag">You</span>
        </div>
        <div v-for="i in emptyHumanSlots" :key="'empty'+i" class="player-row empty">
          Waiting for player…
        </div>
        <div v-for="i in gameState.num_llm_slots" :key="'llm'+i" class="player-row llm-pending">
          🤖 AI Player (joins on start)
        </div>
      </div>
      <button
        class="btn-primary"
        @click="startGame"
        :disabled="!canStart"
      >
        Start Game
      </button>
      <p v-if="!canStart" class="hint">Need at least 2 players total (humans + AI)</p>
    </div>

    <!-- ===== IN GAME ===== -->
    <div v-else-if="screen === 'game'" class="game-screen">

      <!-- Desktop / Tablet -->
      <template v-if="!isMobile">
        <div class="game-header">
          <span class="room-label">Room: {{ roomId }}</span>
          <span class="phase-pill">{{ phaseLabel }}</span>
          <span v-if="connectionStatus !== 'connected'" class="conn-status">{{ connectionStatus }}</span>
          <span v-if="!myPlayer && gameState.phase !== 'waiting'" class="spectator-pill">spectator</span>
          <button class="btn-rules" @click="showQuickStart = true" title="How to play">? Rules</button>
          <button class="btn-exit" @click="leaveGame">Exit Game</button>
        </div>
        <div class="game-layout">
          <div class="table-col">
            <PokerTable :state="gameState" :llmThinking="llmThinkingId" />
            <ActionPanel
              :isMyTurn="isMyTurn"
              :va="gameState.valid_actions || {}"
              @action="sendAction"
            />
          </div>
          <div class="log-col">
            <GameLog :entries="gameState.hand_log || []" />
          </div>
        </div>
      </template>

      <!-- Mobile -->
      <div v-else class="mobile-game">

        <!-- Header -->
        <div class="mobile-header">
          <span class="room-label">{{ roomId }}</span>
          <span class="phase-pill">{{ phaseLabel }}</span>
          <span v-if="connectionStatus !== 'connected'" class="conn-status">{{ connectionStatus }}</span>
          <span v-if="!myPlayer && gameState.phase !== 'waiting'" class="spectator-pill">spectator</span>
          <button class="btn-rules" @click="showQuickStart = true" title="How to play">?</button>
          <button class="btn-exit" @click="leaveGame">Exit</button>
        </div>

        <!-- Opponent strip -->
        <div class="mobile-opponents">
          <div
            v-for="p in opponents"
            :key="p.id"
            class="opp-chip"
            :class="{
              'opp-current': p.id === gameState.current_player_id,
              'opp-folded': p.status === 'folded',
              'opp-out': p.status === 'out',
            }"
          >
            <div class="opp-name">{{ p.name }}<span v-if="p.is_llm"> 🤖</span></div>
            <div class="opp-stack">{{ p.stack }}</div>
            <div class="opp-cards">
              <CardSprite
                v-for="(c, i) in (p.hole_cards && p.hole_cards.length ? p.hole_cards : [null, null])"
                :key="i" :card="c" :small="true"
              />
            </div>
            <div v-if="p.bet_this_round > 0" class="opp-bet">+{{ p.bet_this_round }}</div>
            <div v-if="p.status === 'folded'" class="opp-status">FOLD</div>
            <div v-if="p.status === 'all_in'" class="opp-status opp-allin">ALL IN</div>
          </div>
        </div>

        <!-- Community + pot -->
        <div class="mobile-community">
          <div class="mobile-pot" v-if="gameState.pot > 0">Pot: {{ gameState.pot }}</div>
          <div class="mobile-cards-row">
            <CardSprite v-for="(c, i) in gameState.community_cards" :key="i" :card="c" />
            <CardSprite v-for="i in communityPlaceholders" :key="'ph'+i" :card="null" class="mob-placeholder" />
          </div>
          <div class="mobile-phase">{{ phaseLabel }}</div>
        </div>

        <!-- Winner banner -->
        <div v-if="gameState.phase === 'showdown' && gameState.winners && gameState.winners.length" class="mobile-winners">
          <div v-for="w in gameState.winners" :key="w.player ? w.player.id : w.name">
            🏆 {{ w.player ? w.player.name : w.name }}
            <span v-if="w.amount"> +{{ w.amount }}</span>
            <span v-if="w.hand"> — {{ w.hand }}</span>
          </div>
        </div>

        <!-- My cards -->
        <div class="mobile-my-cards" v-if="myPlayer">
          <div class="my-cards-label">Your Hand</div>
          <div class="my-cards-row">
            <template v-if="myPlayer.hole_cards && myPlayer.hole_cards.length">
              <CardSprite v-for="(c, i) in myPlayer.hole_cards" :key="i" :card="c" />
            </template>
            <template v-else-if="myPlayer.status !== 'folded' && gameState.phase !== 'waiting'">
              <CardSprite :card="null" />
              <CardSprite :card="null" />
            </template>
          </div>
          <div class="my-stack">
            💰 {{ myPlayer.stack }}
            <span v-if="myPlayer.bet_this_round > 0"> · Bet: {{ myPlayer.bet_this_round }}</span>
          </div>
        </div>

        <!-- Log toggle + drawer -->
        <div class="mobile-log-section">
          <button class="mobile-log-toggle" @click="logOpen = !logOpen">
            Game Log {{ logOpen ? '▲' : '▼' }}
          </button>
          <div class="mobile-log-drawer" :class="{ open: logOpen }">
            <GameLog :entries="gameState.hand_log || []" />
          </div>
        </div>

        <!-- Raise drawer (above action bar) -->
        <div class="mobile-raise-drawer" v-if="isMyTurn && gameState.valid_actions && gameState.valid_actions.raise && showRaiseDrawer">
          <div class="raise-stepper">
            <button class="step-btn" @click="stepRaise(-stepSize)">−</button>
            <div class="raise-display">Raise to {{ mobileRaiseAmount }}</div>
            <button class="step-btn" @click="stepRaise(stepSize)">+</button>
          </div>
          <input type="range"
            :min="gameState.valid_actions.min_raise"
            :max="gameState.valid_actions.max_raise"
            v-model.number="mobileRaiseAmount"
            class="mobile-slider"
          />
          <button class="mob-btn raise confirm-raise"
            @click="sendAction({ type: 'raise', amount: mobileRaiseAmount }); showRaiseDrawer = false">
            Confirm Raise {{ mobileRaiseAmount }}
          </button>
        </div>

        <!-- Sticky action bar -->
        <div class="mobile-actions" v-if="isMyTurn">
          <button class="mob-btn fold" @click="sendAction({ type: 'fold' })">Fold</button>
          <button v-if="gameState.valid_actions && gameState.valid_actions.check"
                  class="mob-btn check"
                  @click="sendAction({ type: 'check' })">Check</button>
          <button v-if="gameState.valid_actions && gameState.valid_actions.call"
                  class="mob-btn call"
                  @click="sendAction({ type: 'call' })">
            Call {{ gameState.valid_actions.call_amount }}
          </button>
          <button v-if="gameState.valid_actions && gameState.valid_actions.raise"
                  class="mob-btn raise"
                  :class="{ active: showRaiseDrawer }"
                  @click="showRaiseDrawer = !showRaiseDrawer">
            Raise {{ showRaiseDrawer ? '▲' : '▼' }}
          </button>
        </div>

      </div>

    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import PokerTable from './components/PokerTable.vue'
import ActionPanel from './components/ActionPanel.vue'
import GameLog from './components/GameLog.vue'
import CardSprite from './components/CardSprite.vue'
import QuickStart from './components/QuickStart.vue'
import HistoryExplorer from './components/HistoryExplorer.vue'

const API = '/api'
const WS_BASE = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`

// State
const screen = ref('lobby')
const showQuickStart = ref(false)
const playerName = ref('')
const roomId = ref('')
const myId = ref('')
const joinRoomId = ref('')
const openRooms = ref([])
const lobbyError = ref('')
const connectionStatus = ref('disconnected')
const llmThinkingId = ref(null)

const newRoom = ref({
  numHumans: 2,
  numLlms: 1,
  smallBlind: 10,
  bigBlind: 20,
  startingStack: 1000,
})

const gameState = ref({
  phase: 'waiting',
  players: [],
  community_cards: [],
  pot: 0,
  current_bet: 0,
  current_player_id: null,
  your_id: null,
  valid_actions: {},
  round_log: [],
  hand_log: [],
  winners: [],
  dealer_idx: 0,
  num_human_slots: 2,
  num_llm_slots: 1,
})

let ws = null
let pingInterval = null

// Mobile layout
const isMobile = ref(window.innerWidth < 600)
const logOpen = ref(false)
const showRaiseDrawer = ref(false)
const mobileRaiseAmount = ref(0)

// Computed
const isMyTurn = computed(() =>
  gameState.value.current_player_id === myId.value &&
  gameState.value.phase !== 'waiting' &&
  gameState.value.phase !== 'showdown'
)

const PHASE_LABELS = {
  waiting: 'Lobby',
  pre_flop: 'Pre-Flop',
  flop: 'Flop',
  turn: 'Turn',
  river: 'River',
  showdown: 'Showdown',
}
const phaseLabel = computed(() => PHASE_LABELS[gameState.value.phase] || '')

const emptyHumanSlots = computed(() => {
  const joined = gameState.value.players.filter(p => !p.is_llm).length
  return Math.max(0, (gameState.value.num_human_slots || 2) - joined)
})

const canStart = computed(() => {
  const humans = gameState.value.players.filter(p => !p.is_llm).length
  const llms = gameState.value.num_llm_slots || 0
  return humans + llms >= 2
})

const opponents = computed(() => gameState.value.players.filter(p => p.id !== myId.value))
const myPlayer = computed(() => gameState.value.players.find(p => p.id === myId.value))
const communityPlaceholders = computed(() => Math.max(0, 5 - (gameState.value.community_cards?.length || 0)))
const stepSize = computed(() => {
  const va = gameState.value.valid_actions
  if (!va?.min_raise || !va?.max_raise) return 10
  return Math.max(1, Math.round((va.max_raise - va.min_raise) / 20))
})

function stepRaise(delta) {
  const va = gameState.value.valid_actions
  if (!va) return
  mobileRaiseAmount.value = Math.max(va.min_raise, Math.min(va.max_raise, mobileRaiseAmount.value + delta))
}

// LLM settings
const llmSettingsOpen = ref(false)
const llmConfigMsg = ref('')
const llmConfig = ref({ url: '', apiKey: '', model: '' })

// Game history (fetched on mount, passed to HistoryExplorer)
const gameHistory = ref([])

async function fetchHistory() {
  try {
    const r = await fetch(`${API}/history`)
    if (r.ok) gameHistory.value = await r.json()
  } catch {}
}

async function fetchLlmConfig() {
  try {
    const r = await fetch(`${API}/config`)
    if (r.ok) {
      const d = await r.json()
      llmConfig.value.url   = d.llm_base_url || ''
      llmConfig.value.model = d.llm_model    || ''
    }
  } catch {}
}

async function saveLlmConfig() {
  llmConfigMsg.value = ''
  try {
    const body = {}
    if (llmConfig.value.url)    body.llm_base_url = llmConfig.value.url
    if (llmConfig.value.apiKey) body.llm_api_key  = llmConfig.value.apiKey
    if (llmConfig.value.model !== undefined) body.llm_model = llmConfig.value.model
    const r = await fetch(`${API}/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    llmConfigMsg.value = r.ok ? '✓ Saved' : '✗ Failed'
  } catch (e) {
    llmConfigMsg.value = `✗ ${e.message}`
  }
}

// API helpers
async function fetchRooms() {
  try {
    const r = await fetch(`${API}/rooms`)
    if (r.ok) openRooms.value = await r.json()
  } catch {}
}

async function createRoom() {
  lobbyError.value = ''
  try {
    const r = await fetch(`${API}/rooms`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        num_humans: newRoom.value.numHumans,
        num_llms: newRoom.value.numLlms,
        small_blind: newRoom.value.smallBlind,
        big_blind: newRoom.value.bigBlind,
        starting_stack: newRoom.value.startingStack,
      }),
    })
    if (!r.ok) throw new Error(await r.text())
    const data = await r.json()
    roomId.value = data.room_id
    connectWebSocket()
  } catch (e) {
    lobbyError.value = `Failed to create room: ${e.message}`
  }
}

async function deleteRoom(rid) {
  await fetch(`${API}/rooms/${rid}`, { method: 'DELETE' })
  await fetchRooms()
  if (joinRoomId.value === rid) joinRoomId.value = ''
  if (location.hash === `#${rid}`) location.hash = ''
  sessionStorage.removeItem(`pokerId_${rid}`)
}

async function joinRoom() {
  lobbyError.value = ''
  const rid = joinRoomId.value.trim().toLowerCase()
  if (!rid) return
  try {
    const r = await fetch(`${API}/rooms/${rid}`)
    if (!r.ok) throw new Error('Room not found')
    roomId.value = rid
    connectWebSocket()
  } catch (e) {
    lobbyError.value = `${e.message}`
  }
}

// WebSocket
function connectWebSocket() {
  if (playerName.value) sessionStorage.setItem('pokerName', playerName.value)
  location.hash = roomId.value
  // Reuse the same player ID for this room across reconnects/refreshes
  const idKey = `pokerId_${roomId.value}`
  let savedId = sessionStorage.getItem(idKey)
  if (!savedId) {
    savedId = Math.random().toString(36).slice(2, 10)
    sessionStorage.setItem(idKey, savedId)
  }
  myId.value = savedId
  connectionStatus.value = 'connecting'
  ws = new WebSocket(`${WS_BASE}/${roomId.value}/${myId.value}`)

  ws.onopen = () => {
    connectionStatus.value = 'connected'
    ws.send(JSON.stringify({ type: 'join', name: playerName.value }))
    pingInterval = setInterval(() => ws.send(JSON.stringify({ type: 'ping' })), 15000)
  }

  ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data)
    if (msg.type === 'error') return

    if (msg.llm_thinking !== undefined) {
      llmThinkingId.value = msg.llm_thinking || null
    }

    // Update game state (server always sends full state)
    Object.assign(gameState.value, msg)
    gameState.value.your_id = myId.value

    // Clear thinking indicator when it's a human's turn or showdown
    if (msg.current_player_id !== llmThinkingId.value) {
      llmThinkingId.value = null
    }

    // Transition screens
    if (msg.phase === 'waiting') {
      screen.value = 'waiting'
    } else {
      screen.value = 'game'
    }
  }

  ws.onclose = (evt) => {
    connectionStatus.value = 'disconnected'
    clearInterval(pingInterval)
    // Code 1001 = server closed the room deliberately — go back to lobby
    if (evt.code === 1001) {
      roomId.value = ''
      location.hash = ''
      screen.value = 'lobby'
    } else {
      setTimeout(reconnect, 3000)
    }
  }

  ws.onerror = () => {
    connectionStatus.value = 'error'
  }

  screen.value = 'waiting'
}

function reconnect() {
  if (roomId.value && connectionStatus.value !== 'connected') {
    connectWebSocket()
  }
}

function startGame() {
  ws?.send(JSON.stringify({ type: 'start_game' }))
}

function sendAction({ type, amount }) {
  ws?.send(JSON.stringify({ type: 'action', action: type, amount }))
}

function leaveGame() {
  ws?.send(JSON.stringify({ type: 'leave_room' }))
  clearInterval(pingInterval)
  ws?.close()
  ws = null
  connectionStatus.value = 'disconnected'
  // Keep pokerId in sessionStorage so they can rejoin the same seat via the hash URL
  screen.value = 'lobby'
  roomId.value = ''
  location.hash = ''
}

watch(isMyTurn, val => { if (!val) showRaiseDrawer.value = false })
watch(() => gameState.value.valid_actions?.min_raise, v => { if (v) mobileRaiseAmount.value = v }, { immediate: true })

function onResize() { isMobile.value = window.innerWidth < 600 }

onMounted(async () => {
  window.addEventListener('resize', onResize)
  fetchLlmConfig()
  fetchHistory()
  // Restore room from URL hash on load / refresh
  const hashRoom = location.hash.replace('#', '').trim().toLowerCase()
  if (hashRoom) {
    await fetchRooms()
    const exists = openRooms.value.some(r => r.room_id === hashRoom)
    if (exists) {
      joinRoomId.value = hashRoom
      // Auto-join only if a name is already remembered in sessionStorage
      const savedName = sessionStorage.getItem('pokerName')
      if (savedName) {
        playerName.value = savedName
        roomId.value = hashRoom
        connectWebSocket()
      }
      // Otherwise the lobby shows with the room ID pre-filled and a name prompt
    } else {
      location.hash = ''
    }
  }

  fetchRooms()
  const refresher = setInterval(fetchRooms, 5000)
  onUnmounted(() => clearInterval(refresher))
})

onUnmounted(() => {
  ws?.close()
  clearInterval(pingInterval)
  window.removeEventListener('resize', onResize)
})
</script>

<style>
:root {
  --green: #27ae60;
  --gold: #f1c40f;
  --red: #e74c3c;
  --blue: #2980b9;
}

body { background: #0f0f1e; }

#poker-app {
  min-height: 100vh;
  padding: 20px;
}

/* Lobby */
.lobby-wrapper {
  max-width: 1100px;
  margin: 40px auto;
}
.lobby-layout {
  display: grid;
  grid-template-columns: 520px 1fr;
  gap: 24px;
  max-width: 1100px;
  margin: 0 auto 40px;
  align-items: start;
}
.lobby-main { min-width: 0; }
@media (max-width: 900px) {
  .lobby-layout { grid-template-columns: 1fr; }
  .lobby-main { max-width: 520px; margin: 0 auto; width: 100%; }
}
.lobby-title-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 0;
}
.lobby-title-row h1 {
  text-align: center;
  font-size: 2.2em;
  color: var(--gold);
  margin-bottom: 6px;
}
.btn-rules {
  padding: 4px 12px;
  background: none;
  border: 1px solid #555;
  color: #aaa;
  border-radius: 6px;
  font-size: 0.82em;
  cursor: pointer;
  white-space: nowrap;
  transition: border-color 0.2s, color 0.2s;
  flex-shrink: 0;
}
.btn-rules:hover { border-color: var(--gold); color: var(--gold); }
.subtitle {
  text-align: center;
  color: #888;
  margin-bottom: 30px;
}
.lobby-card {
  background: rgba(255,255,255,0.04);
  border: 1px solid #333;
  border-radius: 14px;
  padding: 24px;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}
.form-group label {
  font-size: 0.8em;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.form-group input {
  background: rgba(255,255,255,0.07);
  border: 1px solid #444;
  border-radius: 6px;
  padding: 8px 10px;
  color: #eee;
  font-size: 0.95em;
  width: 100%;
}
.form-group input:focus {
  outline: none;
  border-color: var(--gold);
}
.form-row {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
  align-items: flex-end;
}
.flex-grow { flex-grow: 1; }
.divider {
  border: none;
  border-top: 1px solid #333;
  margin: 18px 0;
}
h3 { font-size: 0.95em; color: #bbb; margin-bottom: 14px; }
.settings-toggle {
  width: 100%; padding: 9px 12px;
  background: rgba(255,255,255,0.04); border: 1px solid #444;
  color: #aaa; border-radius: 6px; text-align: left;
  cursor: pointer; font-size: 0.88em;
}
.settings-toggle:hover { border-color: var(--gold); color: var(--gold); }
.settings-panel { display: flex; flex-direction: column; gap: 10px; padding: 12px 0; }
.llm-config-msg { font-size: 0.82em; color: var(--green); text-align: center; }
.btn-primary {
  width: 100%;
  padding: 12px;
  background: var(--gold);
  color: #000;
  border: none;
  border-radius: 8px;
  font-size: 1em;
  font-weight: bold;
  cursor: pointer;
  transition: opacity 0.2s;
  margin-top: 8px;
}
.btn-primary:hover { opacity: 0.88; }
.btn-primary:disabled { opacity: 0.35; cursor: not-allowed; }
.btn-secondary {
  padding: 8px 18px;
  background: var(--blue);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 0.95em;
  cursor: pointer;
  white-space: nowrap;
  align-self: flex-end;
}
.btn-secondary:disabled { opacity: 0.4; cursor: not-allowed; }
.open-rooms { margin-top: 14px; }
.open-rooms-title { font-size: 0.8em; color: #777; margin-bottom: 6px; }
.room-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(255,255,255,0.04);
  border: 1px solid #333;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 6px;
  font-size: 0.85em;
  transition: border-color 0.2s;
}
.room-row:hover, .room-row.selected { border-color: var(--gold); }
.room-id { font-weight: bold; color: var(--gold); font-family: monospace; }
.room-info { color: #888; flex: 1; }
.btn-end {
  background: none;
  border: 1px solid #555;
  color: #888;
  border-radius: 4px;
  padding: 2px 7px;
  cursor: pointer;
  font-size: 0.8em;
  line-height: 1.4;
  flex-shrink: 0;
}
.btn-end:hover { border-color: var(--red); color: var(--red); }
.started { color: var(--red); }
.waiting { color: var(--green); }
.error { color: var(--red); font-size: 0.85em; margin-top: 10px; text-align: center; }
.join-hint { color: var(--gold); font-size: 0.8em; margin-top: 6px; text-align: right; }

/* Waiting room */
.waiting-room {
  max-width: 480px;
  margin: 60px auto;
  text-align: center;
}
.waiting-room h2 { margin-bottom: 6px; }
.room-code {
  color: var(--gold);
  font-family: monospace;
  font-size: 1.1em;
  letter-spacing: 2px;
}
.hint { color: #777; font-size: 0.85em; margin-bottom: 20px; }
.players-list {
  background: rgba(255,255,255,0.04);
  border: 1px solid #333;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 20px;
  text-align: left;
}
.player-row {
  padding: 8px 0;
  border-bottom: 1px solid #222;
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 0.9em;
}
.player-row:last-child { border-bottom: none; }
.player-row.empty { color: #555; font-style: italic; }
.player-row.llm-pending { color: #aaa; }
.llm-tag { background: #333; padding: 1px 6px; border-radius: 4px; font-size: 0.8em; }
.you-tag { color: var(--green); font-weight: bold; font-size: 0.8em; }

/* Game screen */
.game-screen { max-width: 1100px; margin: 0 auto; }
.game-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
  padding: 8px 12px;
  background: rgba(0,0,0,0.4);
  border-radius: 8px;
}
.room-label { font-size: 0.8em; color: #777; font-family: monospace; }
.phase-pill {
  background: rgba(241,196,15,0.15);
  color: var(--gold);
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 0.82em;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.conn-status { color: var(--red); font-size: 0.8em; }
.btn-exit {
  margin-left: auto;
  padding: 4px 14px;
  background: none;
  border: 1px solid #555;
  color: #aaa;
  border-radius: 6px;
  font-size: 0.82em;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
}
.btn-exit:hover { border-color: var(--red); color: var(--red); }
.game-layout {
  display: grid;
  grid-template-columns: 1fr 240px;
  gap: 16px;
  align-items: start;
}
.table-col {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.log-col { position: sticky; top: 20px; }

/* ── Tablet (600–899px) ── */
@media (max-width: 899px) {
  #poker-app { padding: 12px; }
  .game-layout { grid-template-columns: 1fr; }
  .log-col { position: static; max-height: 180px; overflow: hidden; }
}

/* ── Lobby / Waiting mobile ── */
@media (max-width: 599px) {
  #poker-app { padding: 10px; }
  .lobby { margin: 10px auto; }
  .lobby-card { padding: 16px; }
  .form-row { flex-wrap: wrap; }
  .waiting-room { margin: 20px auto; }
  .room-info { display: none; }
}

/* ── Guard: hide desktop layout on mobile, hide mobile on desktop ── */
@media (max-width: 599px) { .game-layout { display: none !important; } }
@media (min-width: 600px) { .mobile-game { display: none !important; } }

/* ── Mobile game layout ── */
.mobile-game {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 20px);
  padding-bottom: 76px;
  gap: 6px;
}

.mobile-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: rgba(0,0,0,0.5);
  border-radius: 8px;
  flex-shrink: 0;
}
.mobile-header .room-label { font-size: 0.75em; }
.mobile-header .btn-exit { margin-left: auto; }

/* Opponent strip */
.mobile-opponents {
  display: flex;
  gap: 7px;
  overflow-x: auto;
  padding: 4px 2px;
  flex-shrink: 0;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.mobile-opponents::-webkit-scrollbar { display: none; }

.opp-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 68px;
  background: rgba(0,0,0,0.55);
  border: 2px solid #444;
  border-radius: 10px;
  padding: 5px 6px;
  flex-shrink: 0;
  text-align: center;
}
.opp-chip.opp-current { border-color: var(--gold); box-shadow: 0 0 10px rgba(241,196,15,0.5); }
.opp-chip.opp-folded { opacity: 0.4; }
.opp-chip.opp-out { opacity: 0.2; }
.opp-name { font-size: 0.7em; font-weight: bold; max-width: 60px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.opp-stack { font-size: 0.66em; color: var(--gold); }
.opp-cards { display: flex; gap: 2px; margin: 2px 0; }
.opp-bet { font-size: 0.6em; color: #e67e22; }
.opp-status { font-size: 0.58em; font-weight: bold; color: #aaa; margin-top: 2px; }
.opp-status.opp-allin { color: var(--red); }

/* Community area */
.mobile-community {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: radial-gradient(ellipse at center, #2d5a1b 0%, #1e3d0f 60%, #152d09 100%);
  border-radius: 16px;
  border: 4px solid #5d3a1a;
  padding: 10px;
  min-height: 110px;
  max-height: 170px;
}
.mobile-pot { font-size: 1em; font-weight: bold; color: var(--gold); margin-bottom: 6px; }
.mobile-cards-row { display: flex; gap: 4px; justify-content: center; flex-wrap: nowrap; }
.mob-placeholder { opacity: 0.15; }
.mobile-phase { font-size: 0.68em; color: rgba(255,255,255,0.45); margin-top: 5px; text-transform: uppercase; letter-spacing: 2px; }

/* Winner banner */
.mobile-winners {
  background: rgba(241,196,15,0.12);
  border: 1px solid var(--gold);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 0.88em;
  color: var(--gold);
  text-align: center;
  flex-shrink: 0;
}

/* My hole cards */
.mobile-my-cards {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  padding: 8px 0;
  flex-shrink: 0;
}
.my-cards-label { font-size: 0.7em; color: var(--green); text-transform: uppercase; letter-spacing: 1px; }
.my-cards-row { display: flex; gap: 8px; }
.my-stack { font-size: 0.78em; color: var(--gold); }

/* Log section */
.mobile-log-section { flex-shrink: 0; }
.mobile-log-toggle {
  width: 100%;
  background: rgba(255,255,255,0.05);
  border: 1px solid #444;
  border-radius: 8px;
  color: #aaa;
  font-size: 0.78em;
  padding: 7px 12px;
  cursor: pointer;
  text-align: left;
}
.mobile-log-drawer {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.25s ease;
}
.mobile-log-drawer.open { max-height: 180px; }

/* Sticky action bar */
.mobile-actions {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  gap: 6px;
  padding: 10px 10px env(safe-area-inset-bottom, 10px);
  background: rgba(10,10,20,0.97);
  border-top: 1px solid #333;
  z-index: 100;
}
.mob-btn {
  flex: 1;
  min-height: 50px;
  border: none;
  border-radius: 10px;
  font-size: 0.88em;
  font-weight: bold;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.15s;
}
.mob-btn:active { opacity: 0.75; }
.mob-btn.fold  { background: #c0392b; color: #fff; }
.mob-btn.check { background: #27ae60; color: #fff; }
.mob-btn.call  { background: #2980b9; color: #fff; }
.mob-btn.raise { background: #f39c12; color: #000; }
.mob-btn.raise.active { background: #f1c40f; }

/* Raise drawer */
.mobile-raise-drawer {
  position: fixed;
  bottom: 70px;
  left: 0;
  right: 0;
  background: rgba(10,10,20,0.97);
  border-top: 1px solid #f39c12;
  padding: 14px 14px;
  z-index: 99;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.raise-stepper {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.step-btn {
  width: 50px;
  height: 50px;
  background: rgba(243,156,18,0.2);
  border: 1px solid #f39c12;
  color: #f39c12;
  border-radius: 8px;
  font-size: 1.5em;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.raise-display { font-size: 1.1em; font-weight: bold; color: #f39c12; }
.mobile-slider { width: 100%; accent-color: #f39c12; height: 6px; }
.confirm-raise { flex: unset; width: 100%; min-height: 50px; }

/* Spectator mode */
.spectator-hint {
  font-size: 0.72em;
  color: #666;
  font-style: italic;
  margin-top: 2px;
}
.spectator-pill {
  font-size: 0.72em;
  color: #555;
  border: 1px solid #333;
  border-radius: 10px;
  padding: 2px 8px;
  letter-spacing: 0.5px;
  font-style: italic;
}
</style>
