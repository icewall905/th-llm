<template>
  <div class="log-panel">
    <div class="log-title">Game Log</div>
    <div class="log-entries">
      <div v-for="(entry, i) in reversedEntries" :key="i" class="log-entry">{{ entry }}</div>
      <div v-if="!entries.length" class="log-empty">No actions yet</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  entries: { type: Array, default: () => [] },
})

const reversedEntries = computed(() => [...props.entries].reverse())
</script>

<style scoped>
.log-panel {
  background: rgba(0,0,0,0.6);
  border: 1px solid #444;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 360px;
}
.log-title {
  padding: 8px 12px;
  font-size: 0.8em;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #aaa;
  border-bottom: 1px solid #333;
}
.log-entries {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
  font-size: 0.82em;
  line-height: 1.7;
}
.log-entry {
  color: #ccc;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  padding: 1px 0;
}
.log-empty { color: #555; font-style: italic; }
.log-entries::-webkit-scrollbar { width: 4px; }
.log-entries::-webkit-scrollbar-thumb { background: #444; border-radius: 2px; }
@media (max-width: 899px) {
  .log-panel { max-height: 180px; }
}
@media (max-width: 599px) {
  .log-panel { max-height: none; border: none; background: transparent; }
}
</style>
