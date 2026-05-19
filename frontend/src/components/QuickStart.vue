<template>
  <Teleport to="body">
    <div class="qs-backdrop" @click.self="$emit('close')">
      <div class="qs-modal">
        <div class="qs-header">
          <span class="qs-title">Quickstart — Texas Hold'em</span>
          <button class="qs-close" @click="$emit('close')">✕</button>
        </div>

        <div class="qs-body">

          <section>
            <h3>Goal</h3>
            <p>Win chips by making the best 5-card hand from your 2 hole cards and the 5 community cards, or by being the last player who hasn't folded.</p>
          </section>

          <section>
            <h3>A hand, step by step</h3>
            <ol>
              <li><strong>Blinds</strong> — The two players left of the dealer post the small blind and big blind to seed the pot.</li>
              <li><strong>Pre-Flop</strong> — Everyone gets 2 private hole cards. First betting round.</li>
              <li><strong>Flop</strong> — 3 community cards are dealt face-up. Second betting round.</li>
              <li><strong>Turn</strong> — 1 more community card. Third betting round.</li>
              <li><strong>River</strong> — Final community card. Last betting round.</li>
              <li><strong>Showdown</strong> — Remaining players reveal their cards. Best hand wins.</li>
            </ol>
          </section>

          <section>
            <h3>Your actions</h3>
            <div class="action-grid">
              <div class="action-row">
                <span class="action-badge fold">Fold</span>
                <span>Give up your hand and any chips already bet.</span>
              </div>
              <div class="action-row">
                <span class="action-badge check">Check</span>
                <span>Pass the action without betting (only when no one has bet yet).</span>
              </div>
              <div class="action-row">
                <span class="action-badge call">Call</span>
                <span>Match the current bet to stay in.</span>
              </div>
              <div class="action-row">
                <span class="action-badge raise">Raise</span>
                <span>Increase the bet — opponents must call, re-raise, or fold.</span>
              </div>
            </div>
          </section>

          <section>
            <h3>Hand rankings <span class="rank-note">(high → low)</span></h3>
            <div class="ranks">
              <div class="rank-row" v-for="r in rankings" :key="r.name">
                <span class="rank-name">{{ r.name }}</span>
                <span class="rank-example">{{ r.example }}</span>
                <span class="rank-desc">{{ r.desc }}</span>
              </div>
            </div>
          </section>

          <section>
            <h3>Quick tips</h3>
            <ul>
              <li>Suit only matters for flushes — a high card beats an identical-rank low card.</li>
              <li>Aces can be high (<em>A-K-Q-J-10</em>) or low (<em>A-2-3-4-5</em>) in straights.</li>
              <li>Kicker (the highest unpaired card) breaks ties between same-rank hands.</li>
              <li>Going <strong>all-in</strong> means betting everything you have — you can't be forced out.</li>
            </ul>
          </section>

        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
defineEmits(['close'])

const rankings = [
  { name: 'Royal Flush',    example: 'A♠ K♠ Q♠ J♠ 10♠', desc: 'Top 5 same suit' },
  { name: 'Straight Flush', example: '7♥ 8♥ 9♥ 10♥ J♥', desc: '5 in a row, same suit' },
  { name: 'Four of a Kind', example: 'Q♠ Q♥ Q♦ Q♣ 5♠', desc: 'Four matching ranks' },
  { name: 'Full House',     example: 'K♠ K♥ K♦ 3♣ 3♠',  desc: 'Three of a kind + pair' },
  { name: 'Flush',          example: 'A♣ 9♣ 6♣ 4♣ 2♣',  desc: '5 same suit' },
  { name: 'Straight',       example: '5♠ 6♥ 7♦ 8♣ 9♠',  desc: '5 consecutive ranks' },
  { name: 'Three of a Kind',example: 'J♠ J♥ J♦ 8♣ 4♠',  desc: 'Three matching ranks' },
  { name: 'Two Pair',       example: 'A♠ A♦ 7♥ 7♣ K♠',  desc: 'Two different pairs' },
  { name: 'One Pair',       example: '10♠ 10♣ A♥ 6♦ 3♣', desc: 'One matching pair' },
  { name: 'High Card',      example: 'A♠ J♦ 8♣ 5♥ 2♦',  desc: 'No combination — highest card wins' },
]
</script>

<style scoped>
.qs-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.72);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.qs-modal {
  background: #141424;
  border: 1px solid #3a3a5a;
  border-radius: 14px;
  width: 100%;
  max-width: 560px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 40px rgba(0,0,0,0.7);
}

.qs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px 12px;
  border-bottom: 1px solid #2a2a3e;
  flex-shrink: 0;
}

.qs-title {
  font-size: 1em;
  font-weight: bold;
  color: #f1c40f;
  letter-spacing: 0.5px;
}

.qs-close {
  background: none;
  border: 1px solid #444;
  color: #888;
  border-radius: 6px;
  width: 28px;
  height: 28px;
  cursor: pointer;
  font-size: 0.85em;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.2s, color 0.2s;
}
.qs-close:hover { border-color: #e74c3c; color: #e74c3c; }

.qs-body {
  overflow-y: auto;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  scrollbar-width: thin;
  scrollbar-color: #333 transparent;
}

section h3 {
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 1.2px;
  color: #f1c40f;
  margin: 0 0 10px;
}

section p, section li {
  font-size: 0.88em;
  color: #ccc;
  line-height: 1.55;
}

section ol, section ul {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.rank-note { font-weight: normal; color: #777; font-size: 0.85em; text-transform: none; letter-spacing: 0; }

/* Actions */
.action-grid { display: flex; flex-direction: column; gap: 8px; }
.action-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.86em;
  color: #ccc;
}
.action-badge {
  flex-shrink: 0;
  width: 56px;
  text-align: center;
  padding: 3px 0;
  border-radius: 5px;
  font-size: 0.82em;
  font-weight: bold;
}
.action-badge.fold  { background: #c0392b; color: #fff; }
.action-badge.check { background: #27ae60; color: #fff; }
.action-badge.call  { background: #2980b9; color: #fff; }
.action-badge.raise { background: #f39c12; color: #000; }

/* Hand rankings */
.ranks { display: flex; flex-direction: column; gap: 5px; }
.rank-row {
  display: grid;
  grid-template-columns: 115px 155px 1fr;
  gap: 6px 10px;
  font-size: 0.83em;
  padding: 5px 8px;
  background: rgba(255,255,255,0.03);
  border-radius: 6px;
  align-items: center;
}
.rank-name { color: #eee; font-weight: bold; }
.rank-example { font-family: monospace; color: #aaa; }
.rank-desc { color: #777; font-size: 0.92em; }

@media (max-width: 480px) {
  .rank-row { grid-template-columns: 1fr 1fr; }
  .rank-desc { grid-column: 1 / -1; color: #666; }
}
</style>
