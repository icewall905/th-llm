<template>
  <div class="card" :class="[suitColor, { facedown: !card, small: small }]">
    <template v-if="card">
      <span class="rank">{{ card.rank }}</span>
      <span class="suit-sym">{{ suitSymbol }}</span>
    </template>
    <template v-else>
      <span class="back-pattern">🂠</span>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  card: { type: Object, default: null }, // { rank, suit } or null for face-down
  small: { type: Boolean, default: false },
})

const SUIT_SYMBOLS = { c: '♣', d: '♦', h: '♥', s: '♠' }
const suitSymbol = computed(() => props.card ? SUIT_SYMBOLS[props.card.suit] || props.card.suit : '')
const suitColor = computed(() => {
  if (!props.card) return ''
  return props.card.suit === 'd' || props.card.suit === 'h' ? 'red' : 'black'
})
</script>

<style scoped>
.card {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 72px;
  background: #fff;
  border: 2px solid #ccc;
  border-radius: 6px;
  font-weight: bold;
  font-size: 14px;
  box-shadow: 2px 2px 6px rgba(0,0,0,0.4);
  user-select: none;
  flex-shrink: 0;
}
.card.small {
  width: 38px;
  height: 52px;
  font-size: 11px;
}
.card.red { color: #c0392b; }
.card.black { color: #1a1a1a; }
.card.facedown {
  background: linear-gradient(135deg, #1a237e, #283593);
  border-color: #5c6bc0;
  color: #9fa8da;
  font-size: 28px;
}
.rank { line-height: 1; font-size: 1.1em; }
.suit-sym { font-size: 1.3em; line-height: 1; }
.back-pattern { font-size: 2em; }
@media (max-width: 899px) {
  .card:not(.small) { width: 42px; height: 58px; font-size: 12px; }
}
</style>
