<template>
  <div class="hints-panel">
    <div class="hints-title">🎓 Learning Mode</div>

    <!-- Win probability -->
    <div class="hints-equity-row">
      <span class="hints-label">Win probability</span>
      <div class="hints-bar-wrap">
        <div class="hints-bar" :style="{ width: equityPct + '%' }" :class="equityClass" />
        <span class="hints-pct">{{ equityPct }}%</span>
      </div>
    </div>

    <!-- Current hand -->
    <div class="hints-row">
      <span class="hints-icon">🃏</span>
      <span>{{ learning.hand_name }}</span>
    </div>

    <!-- Draws -->
    <div v-if="learning.draws && learning.draws.length" class="hints-row hints-draw">
      <span class="hints-icon">🎯</span>
      <span>{{ learning.draws.join(' · ') }}</span>
    </div>

    <!-- Pot odds -->
    <div v-if="learning.pot_odds" class="hints-row hints-odds">
      <span class="hints-icon">⚖️</span>
      <span>{{ learning.pot_odds }}</span>
    </div>

    <!-- Strategic tip -->
    <div class="hints-row hints-tip">
      <span class="hints-icon">💡</span>
      <span>{{ learning.tip }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  learning: { type: Object, required: true },
})

const equityPct = computed(() => (props.learning.equity * 100).toFixed(1))
const equityClass = computed(() => {
  const e = props.learning.equity
  if (e >= 0.6) return 'eq-high'
  if (e >= 0.35) return 'eq-mid'
  return 'eq-low'
})
</script>

<style scoped>
.hints-panel {
  background: rgba(0, 0, 0, 0.6);
  border: 1px solid #2ecc71;
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hints-title {
  font-size: 0.72em;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #2ecc71;
  margin-bottom: 2px;
}

.hints-equity-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.hints-label {
  font-size: 0.75em;
  color: #aaa;
  white-space: nowrap;
  flex-shrink: 0;
}
.hints-bar-wrap {
  position: relative;
  flex: 1;
  height: 18px;
  background: rgba(255,255,255,0.08);
  border-radius: 5px;
  overflow: hidden;
}
.hints-bar {
  height: 100%;
  border-radius: 5px;
  transition: width 0.4s ease;
}
.hints-bar.eq-high { background: #27ae60; }
.hints-bar.eq-mid  { background: #f39c12; }
.hints-bar.eq-low  { background: #c0392b; }
.hints-pct {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75em;
  font-weight: bold;
  color: #fff;
  text-shadow: 0 0 4px rgba(0,0,0,0.9);
}

.hints-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 0.82em;
  color: #ddd;
  line-height: 1.4;
}
.hints-icon {
  flex-shrink: 0;
  width: 18px;
  text-align: center;
}
.hints-draw { color: #a29bfe; }
.hints-odds { color: #fdcb6e; }
.hints-tip  { color: #b2bec3; font-style: italic; }
</style>
