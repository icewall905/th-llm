<template>
  <div class="table-wrapper">
    <div class="table-felt">
      <!-- Community cards + pot -->
      <div class="community-area">
        <div class="pot-display" v-if="state.pot > 0">Pot: {{ state.pot }}</div>
        <div class="community-cards">
          <CardSprite
            v-for="(c, i) in state.community_cards"
            :key="i"
            :card="c"
          />
          <CardSprite
            v-for="i in placeholders"
            :key="'ph' + i"
            :card="null"
            class="placeholder"
          />
        </div>
        <div class="phase-label">{{ phaseLabel }}</div>
      </div>

      <!-- Player seats positioned around the table -->
      <div
        v-for="(player, idx) in state.players"
        :key="player.id"
        class="seat-wrapper"
        :style="seatStyle(idx, state.players.length)"
      >
        <PlayerSeat
          :player="player"
          :isCurrent="player.id === state.current_player_id"
          :isYou="player.id === state.your_id"
          :isDealer="isDealerSeat(idx)"
          :isSB="isSBSeat(idx)"
          :isBB="isBBSeat(idx)"
          :phase="state.phase"
          :isThinking="llmThinking === player.id"
          :equity="state.equities
            ? (state.equities[player.id] ?? null)
            : (player.id === state.your_id && state.learning ? state.learning.equity : null)"
          :isSpectator="isSpectator"
        />
      </div>
    </div>

    <!-- Showdown winners banner -->
    <div v-if="state.phase === 'showdown' && state.winners && state.winners.length" class="winners-banner">
      <div v-for="w in state.winners" :key="w.player.id" class="winner-entry">
        🏆 {{ w.player.name }} wins {{ w.amount }}
        <span v-if="w.hand"> — {{ w.hand }}</span>
        <span class="winner-cards">
          <CardSprite v-for="(c, i) in w.player.hole_cards" :key="i" :card="c" :small="true" />
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import CardSprite from './CardSprite.vue'
import PlayerSeat from './PlayerSeat.vue'

const props = defineProps({
  state: Object,
  llmThinking: { type: String, default: null },
  isSpectator: { type: Boolean, default: false },
})

const PHASE_LABELS = {
  waiting: 'Waiting for players',
  pre_flop: 'Pre-Flop',
  flop: 'Flop',
  turn: 'Turn',
  river: 'River',
  showdown: 'Showdown',
}

const phaseLabel = computed(() => PHASE_LABELS[props.state.phase] || '')

const placeholders = computed(() => {
  const shown = props.state.community_cards?.length || 0
  const total = 5
  return Math.max(0, total - shown)
})

function seatStyle(idx, total) {
  const angle = (idx / total) * 360 - 90
  const rad = (angle * Math.PI) / 180
  const rx = 42  // horizontal radius %
  const ry = 36  // vertical radius %
  const cx = 50
  const cy = 50
  const x = cx + rx * Math.cos(rad)
  const y = cy + ry * Math.sin(rad)
  return {
    position: 'absolute',
    left: `${x}%`,
    top: `${y}%`,
    transform: 'translate(-50%, -50%)',
  }
}

function isDealerSeat(idx) {
  const alive = props.state.players?.filter(p => p.status !== 'out') || []
  if (!alive.length) return false
  return idx === props.state.dealer_idx % props.state.players.length
}

function isSBSeat(idx) {
  const alive = props.state.players?.filter(p => p.status !== 'out') || []
  if (alive.length < 2) return false
  const dealerIdx = props.state.dealer_idx % props.state.players.length
  if (alive.length === 2) return false
  const sbIdx = (dealerIdx + 1) % props.state.players.length
  return idx === sbIdx
}

function isBBSeat(idx) {
  const alive = props.state.players?.filter(p => p.status !== 'out') || []
  if (alive.length < 2) return false
  const dealerIdx = props.state.dealer_idx % props.state.players.length
  const bbOffset = alive.length === 2 ? 1 : 2
  const bbIdx = (dealerIdx + bbOffset) % props.state.players.length
  return idx === bbIdx
}
</script>

<style scoped>
.table-wrapper {
  position: relative;
  width: 100%;
}
.table-felt {
  position: relative;
  width: 100%;
  padding-bottom: 55%;
  background: radial-gradient(ellipse at center, #2d5a1b 0%, #1e3d0f 60%, #152d09 100%);
  border-radius: 50%;
  border: 8px solid #5d3a1a;
  box-shadow: 0 0 40px rgba(0,0,0,0.8), inset 0 0 60px rgba(0,0,0,0.3);
  overflow: visible;
}
.community-area {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  z-index: 2;
}
.pot-display {
  font-size: 1.1em;
  font-weight: bold;
  color: #f1c40f;
  margin-bottom: 8px;
  text-shadow: 1px 1px 4px rgba(0,0,0,0.8);
}
.community-cards {
  display: flex;
  gap: 6px;
  justify-content: center;
  flex-wrap: nowrap;
}
.community-cards .placeholder {
  opacity: 0.2;
}
.phase-label {
  font-size: 0.75em;
  color: rgba(255,255,255,0.5);
  margin-top: 6px;
  text-transform: uppercase;
  letter-spacing: 2px;
}
.seat-wrapper {
  z-index: 5;
}
.winners-banner {
  margin-top: 16px;
  background: linear-gradient(135deg, rgba(241,196,15,0.15), rgba(243,156,18,0.1));
  border: 2px solid #f1c40f;
  border-radius: 10px;
  padding: 12px 20px;
  text-align: center;
}
.winner-entry {
  font-size: 1em;
  font-weight: bold;
  color: #f1c40f;
  margin: 4px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}
.winner-cards {
  display: flex;
  gap: 4px;
}
</style>
