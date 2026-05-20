<template>
  <div class="history-widget">
    <div class="hw-header">📜 Game History</div>

    <div v-if="sessions.length === 0" class="hw-empty">No completed games yet.</div>

    <div class="hw-session-list">
      <div
        v-for="s in sessions"
        :key="s.id"
        class="hw-session-row"
        :class="{ active: selected?.id === s.id }"
        @click="selectSession(s)"
      >
        <div class="hw-sr-top">
          <span class="hw-sr-date">{{ formatDate(s.ended_at) }}</span>
          <span class="hw-sr-hands">{{ s.num_hands }} hand{{ s.num_hands !== 1 ? 's' : '' }}</span>
        </div>
        <div class="hw-sr-players">
          <span
            v-for="p in s.players.slice().sort((a, b) => b.final_stack - a.final_stack)"
            :key="p.name"
            class="hw-sr-player"
            :class="{ winner: p.final_stack === Math.max(...s.players.map(x => x.final_stack)) }"
          >{{ p.name }}<span v-if="p.is_llm"> 🤖</span> <span class="hw-sr-stack">{{ p.final_stack }}</span></span>
        </div>
        <div class="hw-sr-meta">{{ s.small_blind }}/{{ s.big_blind }} blinds · {{ s.starting_stack }} start</div>
      </div>
    </div>

    <!-- Hand explorer — shown when a session is selected and detail loaded -->
    <div v-if="detail" class="hw-explorer">
      <div v-if="detail.hand_history.length === 0" class="hw-empty">
        No hand data for this session.
      </div>

      <template v-else>
        <div class="hw-nav">
          <button class="hw-navbtn" @click="prevHand" :disabled="handIdx === 0">←</button>
          <span class="hw-nav-label">Hand {{ handIdx + 1 }} / {{ detail.hand_history.length }}</span>
          <button class="hw-navbtn" @click="nextHand" :disabled="handIdx === detail.hand_history.length - 1">→</button>
          <button class="hw-playbtn" @click="toggleAutoPlay">
            {{ autoPlaying ? '⏸ Pause' : '▶ Play' }}
          </button>
        </div>

        <div v-if="currentHand" class="hw-hand">
          <!-- Community cards -->
          <div class="hw-community">
            <CardSprite v-for="(c, i) in currentHand.communityCards" :key="i" :card="c" />
            <CardSprite
              v-for="i in Math.max(0, 5 - currentHand.communityCards.length)"
              :key="'ph' + i"
              :card="null"
            />
          </div>

          <div class="hw-pot">Pot: {{ currentHand.pot }}</div>

          <!-- Winner banner -->
          <div class="hw-winners">
            🏆
            <span v-for="(w, i) in currentHand.winners" :key="i">
              {{ w.name }}<span v-if="w.hand"> — {{ w.hand }}</span> +{{ w.amount }}
            </span>
          </div>

          <!-- Player results -->
          <div class="hw-players">
            <div v-for="p in currentHand.players" :key="p.name" class="hw-player-row">
              <span class="hw-pr-name">{{ p.name }}</span>
              <span class="hw-pr-stacks">{{ p.stack_before }} → {{ p.stack_after }}</span>
              <span v-if="p.showed" class="hw-pr-hand">{{ p.showed }}</span>
            </div>
          </div>

          <!-- Action log -->
          <div class="hw-actions">
            <div class="hw-actions-title">Actions</div>
            <div v-if="currentHand.actions.length === 0" class="hw-action-empty">
              No action log for this hand.
            </div>
            <div v-for="(a, i) in currentHand.actions" :key="i" class="hw-action-line">{{ a }}</div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import CardSprite from './CardSprite.vue'

const props = defineProps({
  sessions: { type: Array, default: () => [] },
})

const API = '/api'

const selected = ref(null)
const detail = ref(null)
const handIdx = ref(0)
const autoPlaying = ref(false)
let timer = null

function parseCommunity(str) {
  if (!str || str === '—') return []
  return str.split(' ').filter(Boolean).map(s => ({
    rank: s.slice(0, -1),
    suit: s.slice(-1),
  }))
}

const currentHand = computed(() => {
  if (!detail.value || !detail.value.hand_history.length) return null
  const h = detail.value.hand_history[handIdx.value]
  if (!h) return null
  return {
    ...h,
    communityCards: parseCommunity(h.community),
    actions: h.actions || [],
  }
})

async function selectSession(s) {
  stopAutoPlay()
  selected.value = s
  detail.value = null
  handIdx.value = 0
  try {
    const r = await fetch(`${API}/history/${s.id}`)
    if (r.ok) detail.value = await r.json()
  } catch (e) {
    console.error('Failed to load session detail', e)
  }
}

function prevHand() {
  if (handIdx.value > 0) handIdx.value--
}

function nextHand() {
  if (detail.value && handIdx.value < detail.value.hand_history.length - 1)
    handIdx.value++
}

function startAutoPlay() {
  if (autoPlaying.value || !detail.value) return
  autoPlaying.value = true
  timer = setInterval(() => {
    if (!detail.value || handIdx.value >= detail.value.hand_history.length - 1) {
      stopAutoPlay()
    } else {
      handIdx.value++
    }
  }, 3000)
}

function stopAutoPlay() {
  autoPlaying.value = false
  if (timer) { clearInterval(timer); timer = null }
}

function toggleAutoPlay() {
  autoPlaying.value ? stopAutoPlay() : startAutoPlay()
}

watch(selected, () => stopAutoPlay())
onUnmounted(() => stopAutoPlay())

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return iso }
}
</script>

<style scoped>
.history-widget {
  background: rgba(255,255,255,0.04);
  border: 1px solid #333;
  border-radius: 14px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.hw-header {
  font-size: 0.88em;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #aaa;
  padding-bottom: 10px;
  border-bottom: 1px solid #333;
}

.hw-empty {
  font-size: 0.82em;
  color: #555;
  text-align: center;
  padding: 16px 0;
}

/* Session list */
.hw-session-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 260px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #444 transparent;
}

.hw-session-row {
  background: rgba(255,255,255,0.03);
  border: 1px solid #2a2a2a;
  border-radius: 7px;
  padding: 9px 11px;
  cursor: pointer;
  transition: border-color 0.15s;
}
.hw-session-row:hover { border-color: #555; }
.hw-session-row.active { border-color: var(--gold); background: rgba(241,196,15,0.05); }

.hw-sr-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}
.hw-sr-date { font-size: 0.76em; color: #888; }
.hw-sr-hands { font-size: 0.76em; color: #aaa; font-weight: bold; }
.hw-sr-players { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 3px; }
.hw-sr-player {
  font-size: 0.76em;
  padding: 2px 6px;
  background: rgba(255,255,255,0.04);
  border-radius: 4px;
  color: #aaa;
}
.hw-sr-player.winner { color: var(--gold); background: rgba(241,196,15,0.10); }
.hw-sr-stack { color: #666; }
.hw-sr-meta { font-size: 0.7em; color: #555; }

/* Explorer */
.hw-explorer {
  border-top: 1px solid #2a2a2a;
  padding-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hw-nav {
  display: flex;
  align-items: center;
  gap: 6px;
}
.hw-navbtn {
  width: 34px;
  height: 34px;
  background: rgba(255,255,255,0.06);
  border: 1px solid #444;
  border-radius: 6px;
  color: #ccc;
  cursor: pointer;
  font-size: 1em;
  flex-shrink: 0;
}
.hw-navbtn:disabled { opacity: 0.25; cursor: not-allowed; }
.hw-navbtn:not(:disabled):hover { border-color: var(--gold); color: var(--gold); }
.hw-nav-label {
  flex: 1;
  text-align: center;
  font-size: 0.82em;
  color: #aaa;
}
.hw-playbtn {
  padding: 6px 12px;
  background: rgba(39,174,96,0.12);
  border: 1px solid #27ae60;
  border-radius: 6px;
  color: #27ae60;
  cursor: pointer;
  font-size: 0.82em;
  flex-shrink: 0;
}
.hw-playbtn:hover { background: rgba(39,174,96,0.22); }

/* Hand view */
.hw-hand { display: flex; flex-direction: column; gap: 10px; }

.hw-community {
  display: flex;
  gap: 5px;
  justify-content: center;
  flex-wrap: nowrap;
  overflow-x: auto;
}

.hw-pot {
  font-size: 0.84em;
  font-weight: bold;
  color: var(--gold);
  text-align: center;
}

.hw-winners {
  background: rgba(241,196,15,0.08);
  border: 1px solid rgba(241,196,15,0.25);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 0.84em;
  color: var(--gold);
  line-height: 1.5;
}

.hw-players {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.hw-player-row {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 0.8em;
  padding: 3px 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.hw-pr-name { color: #ccc; min-width: 80px; font-weight: bold; }
.hw-pr-stacks { color: #888; font-family: monospace; font-size: 0.95em; }
.hw-pr-hand { margin-left: auto; color: #5dade2; font-size: 0.88em; }

.hw-actions {
  background: rgba(0,0,0,0.25);
  border: 1px solid #222;
  border-radius: 6px;
  padding: 8px 10px;
  max-height: 200px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #444 transparent;
}
.hw-actions-title {
  font-size: 0.7em;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #555;
  margin-bottom: 5px;
}
.hw-action-line {
  font-size: 0.78em;
  color: #888;
  line-height: 1.8;
  border-bottom: 1px solid rgba(255,255,255,0.03);
}
.hw-action-line:last-child { border-bottom: none; }
.hw-action-empty { font-size: 0.78em; color: #555; font-style: italic; }
</style>
