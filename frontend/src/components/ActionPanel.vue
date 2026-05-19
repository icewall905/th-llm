<template>
  <div class="action-panel" v-if="isMyTurn">
    <div class="panel-title">Your turn</div>
    <div class="actions">
      <button class="btn fold" @click="act('fold')">Fold</button>
      <button v-if="va.check" class="btn check" @click="act('check')">Check</button>
      <button v-if="va.call" class="btn call" @click="act('call')">
        Call {{ va.call_amount }}
      </button>
      <div v-if="va.raise" class="raise-block">
        <input
          type="range"
          :min="va.min_raise"
          :max="va.max_raise"
          v-model.number="raiseAmount"
          class="raise-slider"
        />
        <div class="raise-info">Raise to {{ raiseAmount }}</div>
        <button class="btn raise" @click="act('raise', raiseAmount)">Raise {{ raiseAmount }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  isMyTurn: Boolean,
  va: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['action'])
const raiseAmount = ref(0)

watch(() => props.va, (va) => {
  if (va && va.min_raise) {
    raiseAmount.value = va.min_raise
  }
}, { immediate: true })

function act(type, amount = 0) {
  emit('action', { type, amount })
}
</script>

<style scoped>
.action-panel {
  background: rgba(0,0,0,0.75);
  border: 2px solid #f1c40f;
  border-radius: 12px;
  padding: 14px 20px;
  text-align: center;
}
.panel-title {
  font-size: 0.85em;
  color: #f1c40f;
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.actions {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
}
.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  font-size: 0.95em;
  font-weight: bold;
  cursor: pointer;
  transition: transform 0.1s, opacity 0.1s;
}
.btn:hover { transform: scale(1.05); }
.btn:active { transform: scale(0.97); }
.btn.fold { background: #c0392b; color: #fff; }
.btn.check { background: #27ae60; color: #fff; }
.btn.call { background: #2980b9; color: #fff; }
.btn.raise { background: #f39c12; color: #000; }
.raise-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.raise-slider {
  width: 140px;
  accent-color: #f39c12;
}
.raise-info {
  font-size: 0.8em;
  color: #f39c12;
}
@media (max-width: 899px) {
  .raise-slider { width: 100%; max-width: 280px; }
  .btn { min-height: 48px; padding: 12px 16px; }
}
</style>
