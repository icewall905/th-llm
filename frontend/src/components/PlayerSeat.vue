<template>
  <div class="seat" :class="[statusClass, { 'is-current': isCurrent, 'is-you': isYou }]">
    <div class="seat-header">
      <span class="name">{{ player.name }}</span>
      <span v-if="player.is_llm" class="llm-badge" title="AI Player">🤖</span>
      <span v-if="isDealer" class="badge dealer-badge">D</span>
      <span v-if="isSB" class="badge sb-badge">SB</span>
      <span v-if="isBB" class="badge bb-badge">BB</span>
    </div>
    <div v-if="isSpectator && player.is_llm && player.personality" class="personality-label">
      {{ player.personality }}
    </div>
    <div class="stack">💰 {{ player.stack }}</div>
    <div v-if="player.bet_this_round > 0" class="current-bet">Bet: {{ player.bet_this_round }}</div>
    <div class="cards">
      <template v-if="player.hole_cards && player.hole_cards.length">
        <CardSprite v-for="(c, i) in player.hole_cards" :key="i" :card="c" :small="true" />
      </template>
      <template v-else-if="player.status !== 'folded' && player.status !== 'out' && phase !== 'waiting'">
        <CardSprite :card="null" :small="true" />
        <CardSprite :card="null" :small="true" />
      </template>
    </div>
    <div v-if="player.status === 'folded'" class="status-label folded">FOLDED</div>
    <div v-if="player.status === 'all_in'" class="status-label all-in">ALL IN</div>
    <div v-if="isCurrent && isThinking" class="thinking">thinking…</div>
    <div v-if="equity != null && player.status !== 'folded' && player.status !== 'out'" class="equity-bar-wrap">
      <div class="equity-bar" :style="{ width: (equity * 100).toFixed(1) + '%' }" :class="equityClass"></div>
      <span class="equity-label">{{ (equity * 100).toFixed(1) }}%</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import CardSprite from './CardSprite.vue'

const props = defineProps({
  player: Object,
  isCurrent: Boolean,
  isYou: Boolean,
  isDealer: Boolean,
  isSB: Boolean,
  isBB: Boolean,
  phase: String,
  isThinking: Boolean,
  equity: { type: Number, default: null },
  isSpectator: { type: Boolean, default: false },
})

const statusClass = computed(() => {
  if (props.player.status === 'folded') return 'folded'
  if (props.player.status === 'all_in') return 'all-in'
  if (props.player.status === 'out') return 'out'
  return ''
})

const equityClass = computed(() => {
  const e = props.equity
  if (e == null) return ''
  if (e >= 0.6) return 'eq-high'
  if (e >= 0.35) return 'eq-mid'
  return 'eq-low'
})
</script>

<style scoped>
.seat {
  background: rgba(0,0,0,0.55);
  border: 2px solid #444;
  border-radius: 12px;
  padding: 8px 10px;
  min-width: 110px;
  text-align: center;
  transition: all 0.2s;
  position: relative;
}
.seat.is-current {
  border-color: #f1c40f;
  box-shadow: 0 0 16px rgba(241,196,15,0.6);
}
.seat.is-you {
  border-color: #2ecc71;
}
.seat.folded { opacity: 0.45; }
.seat.out { opacity: 0.25; }
.seat-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.name {
  font-weight: bold;
  font-size: 0.85em;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.llm-badge { font-size: 0.9em; }
.personality-label {
  font-size: 0.65em;
  color: #a29bfe;
  font-style: italic;
  margin-bottom: 2px;
}
.badge {
  font-size: 0.65em;
  font-weight: bold;
  padding: 1px 5px;
  border-radius: 8px;
}
.dealer-badge { background: #f39c12; color: #000; }
.sb-badge { background: #3498db; color: #fff; }
.bb-badge { background: #e74c3c; color: #fff; }
.stack {
  font-size: 0.82em;
  color: #f1c40f;
  margin: 2px 0;
}
.current-bet {
  font-size: 0.75em;
  color: #e67e22;
}
.cards {
  display: flex;
  gap: 4px;
  justify-content: center;
  margin-top: 6px;
}
.status-label {
  font-size: 0.7em;
  font-weight: bold;
  margin-top: 4px;
  padding: 2px 6px;
  border-radius: 4px;
}
.status-label.folded { background: #7f8c8d; }
.status-label.all-in { background: #e74c3c; }
.thinking {
  font-size: 0.7em;
  color: #f1c40f;
  animation: pulse 1s infinite;
  margin-top: 4px;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.equity-bar-wrap {
  position: relative;
  margin-top: 5px;
  height: 14px;
  background: rgba(255,255,255,0.08);
  border-radius: 4px;
  overflow: hidden;
}
.equity-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}
.equity-bar.eq-high { background: #27ae60; }
.equity-bar.eq-mid  { background: #f39c12; }
.equity-bar.eq-low  { background: #c0392b; }
.equity-label {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.68em;
  font-weight: bold;
  color: #fff;
  text-shadow: 0 0 3px rgba(0,0,0,0.8);
}
@media (max-width: 899px) {
  .seat { min-width: 88px; padding: 5px 7px; }
  .name { font-size: 0.78em; max-width: 62px; }
  .stack, .current-bet { font-size: 0.7em; }
}
</style>
