import random
import itertools
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from collections import Counter

logger = logging.getLogger(__name__)


RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["c", "d", "h", "s"]
RANK_VALUE = {r: i for i, r in enumerate(RANKS)}


class Phase(str, Enum):
    WAITING = "waiting"
    PRE_FLOP = "pre_flop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"


class PlayerStatus(str, Enum):
    ACTIVE = "active"
    FOLDED = "folded"
    ALL_IN = "all_in"
    OUT = "out"


@dataclass
class Card:
    rank: str
    suit: str

    def __str__(self):
        return f"{self.rank}{self.suit}"

    def to_dict(self):
        return {"rank": self.rank, "suit": self.suit}


@dataclass
class Player:
    id: str
    name: str
    is_llm: bool
    stack: int
    seat: int
    status: PlayerStatus = PlayerStatus.ACTIVE
    hole_cards: list[Card] = field(default_factory=list)
    bet_this_round: int = 0
    total_bet: int = 0
    personality: str = ""           # short tag shown in UI, e.g. "LAG"
    personality_prompt: str = ""    # injected into LLM system prompt

    def to_dict(self, reveal_cards=False):
        cards = [c.to_dict() for c in self.hole_cards] if reveal_cards else []
        return {
            "id": self.id,
            "name": self.name,
            "is_llm": self.is_llm,
            "stack": self.stack,
            "seat": self.seat,
            "status": self.status.value,
            "hole_cards": cards,
            "bet_this_round": self.bet_this_round,
            "personality": self.personality,
        }


# ── Hand evaluation ────────────────────────────────────────────────────────────

def _hand_rank(five_cards: list[Card]) -> tuple:
    ranks = sorted([RANK_VALUE[c.rank] for c in five_cards], reverse=True)
    suits = [c.suit for c in five_cards]
    flush = len(set(suits)) == 1
    straight = (ranks == list(range(ranks[0], ranks[0] - 5, -1))) or (
        sorted(ranks) == [0, 1, 2, 3, 12]
    )
    if straight and sorted(ranks) == [0, 1, 2, 3, 12]:
        ranks = [3, 2, 1, 0, -1]

    counts = Counter(ranks)
    freq = sorted(counts.values(), reverse=True)
    groups = sorted(counts.keys(), key=lambda r: (counts[r], r), reverse=True)

    if flush and straight:
        category = 8
    elif freq == [4, 1]:
        category = 7
    elif freq == [3, 2]:
        category = 6
    elif flush:
        category = 5
    elif straight:
        category = 4
    elif freq[0] == 3:
        category = 3
    elif freq == [2, 2, 1]:
        category = 2
    elif freq[0] == 2:
        category = 1
    else:
        category = 0

    return (category, groups)


def best_hand(cards: list[Card]) -> tuple:
    best = None
    for combo in itertools.combinations(cards, 5):
        rank = _hand_rank(list(combo))
        if best is None or rank > best:
            best = rank
    return best


HAND_NAMES = [
    "High Card", "One Pair", "Two Pair", "Three of a Kind",
    "Straight", "Flush", "Full House", "Four of a Kind", "Straight Flush",
]


def hand_name(cards: list[Card]) -> str:
    rank = best_hand(cards)
    return HAND_NAMES[rank[0]] if rank else "Unknown"


def describe_preflop_hand(hole_cards: list) -> str:
    if len(hole_cards) != 2:
        return "Unknown"
    c1, c2 = hole_cards
    r1, r2 = RANK_VALUE[c1.rank], RANK_VALUE[c2.rank]
    suited = c1.suit == c2.suit
    if c1.rank == c2.rank:
        name = {"A": "Aces", "K": "Kings", "Q": "Queens", "J": "Jacks", "10": "Tens"}.get(c1.rank, f"{c1.rank}s")
        return f"Pocket {name}"
    hi = c1.rank if r1 > r2 else c2.rank
    lo = c2.rank if r1 > r2 else c1.rank
    gap = abs(r1 - r2)
    s = "Suited" if suited else "Offsuit"
    if hi == "A": return f"Ace-{lo} {s}"
    if hi == "K": return f"King-{lo} {s}"
    if gap == 1:  return "Suited Connectors" if suited else f"Connectors ({hi}-{lo})"
    if gap == 2:  return f"One-Gapper ({hi}-{lo}{', suited' if suited else ''})"
    return f"{hi}-{lo} {s}"


# ── Per-player stats ───────────────────────────────────────────────────────────

def _empty_stats() -> dict:
    return {
        "hands_dealt": 0,
        "vpip": 0,          # voluntarily put chips in preflop
        "raises": 0,
        "folds": 0,
        "wins": 0,
        "showdown_hands": [],   # last 5 hand names shown at showdown
        "vpip_this_hand": False,
        "stack_start": 0,
    }


def _learning_tip(equity: float, draws: list, call_amount: int, pot: int) -> str:
    pct = equity * 100
    if pct >= 80:
        return "Strong favourite — consider building the pot with a bet or raise."
    if pct >= 60:
        return "Good hand — betting for value is usually correct here."
    if pct >= 40:
        return "Marginal spot — pot odds and position matter."
    if draws:
        if call_amount and pot:
            needed = 100 * call_amount / (pot + call_amount)
            if pct >= needed:
                return "Your draw has enough equity to call. Stay in."
        return "You have a draw — weigh pot odds before calling a large bet."
    if pct >= 25:
        return "Weak hand — fold unless pot odds make a call profitable."
    return "Very weak hand — folding is usually the right play here."


# ── Game ───────────────────────────────────────────────────────────────────────

class PokerGame:
    def __init__(self, room_id: str, small_blind: int = 10, big_blind: int = 20,
                 starting_stack: int = 1000):
        self.room_id = room_id
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.starting_stack = starting_stack

        self.players: list[Player] = []
        self.phase = Phase.WAITING
        self.community_cards: list[Card] = []
        self.pot = 0
        self.current_bet = 0
        self.deck: list[Card] = []

        self._action_queue: list[str] = []
        self.current_player_id: Optional[str] = None

        self.dealer_id: Optional[str] = None

        self.round_log: list[str] = []
        self.hand_log: list[str] = []
        self.winners: list[dict] = []

        # Cross-hand memory
        self._hand_log_offset: int = 0           # index into hand_log where current hand starts
        self.hand_history: list[dict] = []       # one entry per completed hand
        self.player_stats: dict[str, dict] = {}  # name -> stats dict

        self.num_human_slots: int = 0
        self.num_llm_slots: int = 0
        self.learning_mode: bool = False

    # ── Roster ────────────────────────────────────────────────────────────────

    def add_player(self, player_id: str, name: str, seat: int,
                   is_llm: bool = False) -> Player:
        p = Player(id=player_id, name=name, is_llm=is_llm,
                   stack=self.starting_stack, seat=seat)
        self.players.append(p)
        self.players.sort(key=lambda x: x.seat)
        if name not in self.player_stats:
            self.player_stats[name] = _empty_stats()
        return p

    def remove_player(self, player_id: str):
        self.players = [p for p in self.players if p.id != player_id]

    def get_player(self, player_id: str) -> Optional[Player]:
        return next((p for p in self.players if p.id == player_id), None)

    def active_players(self) -> list[Player]:
        return [p for p in self.players
                if p.status in (PlayerStatus.ACTIVE, PlayerStatus.ALL_IN)]

    def betting_players(self) -> list[Player]:
        return [p for p in self.players if p.status == PlayerStatus.ACTIVE]

    # ── Dealer rotation ───────────────────────────────────────────────────────

    def _eligible(self) -> list[Player]:
        return [p for p in self.players if p.stack > 0]

    def advance_dealer(self):
        eligible = self._eligible()
        if not eligible:
            return
        if self.dealer_id is None:
            self.dealer_id = eligible[0].id
            return
        pos = next((i for i, p in enumerate(eligible) if p.id == self.dealer_id), -1)
        self.dealer_id = eligible[(pos + 1) % len(eligible)].id

    def _dealer_idx_for_display(self) -> int:
        for i, p in enumerate(self.players):
            if p.id == self.dealer_id:
                return i
        return 0

    # ── Action queue helpers ──────────────────────────────────────────────────

    def _first_active_after(self, anchor_id: str) -> Optional[str]:
        ap = [p for p in self.players if p.status == PlayerStatus.ACTIVE]
        if not ap:
            return None
        start = next((i for i, p in enumerate(ap) if p.id == anchor_id), -1)
        if start == -1:
            return ap[0].id
        return ap[(start + 1) % len(ap)].id

    def _init_action_queue(self, first_player_id: str):
        ap = [p for p in self.players if p.status == PlayerStatus.ACTIVE]
        if not ap:
            self._action_queue = []
            self.current_player_id = None
            return
        start = next((i for i, p in enumerate(ap) if p.id == first_player_id), 0)
        self._action_queue = [p.id for p in ap[start:] + ap[:start]]
        self.current_player_id = self._action_queue[0]
        first = self.get_player(self.current_player_id)
        logger.info(f"Action queue init: {[self.get_player(pid).name for pid in self._action_queue if self.get_player(pid)]} — first: {first.name if first else '?'}")

    def _advance_queue(self):
        if self._action_queue and self._action_queue[0] == self.current_player_id:
            self._action_queue.pop(0)
        while self._action_queue:
            p = self.get_player(self._action_queue[0])
            if p and p.status == PlayerStatus.ACTIVE:
                break
            self._action_queue.pop(0)

        if self._action_queue:
            self.current_player_id = self._action_queue[0]
        else:
            self.current_player_id = None
            self._next_phase()

    def _rebuild_queue_after_raise(self, raiser_id: str):
        ap = [p for p in self.players if p.status == PlayerStatus.ACTIVE]
        raiser_pos = next((i for i, p in enumerate(ap) if p.id == raiser_id), -1)
        n = len(ap)
        self._action_queue = [
            ap[(raiser_pos + 1 + i) % n].id for i in range(n - 1)
        ]
        while self._action_queue:
            p = self.get_player(self._action_queue[0])
            if p and p.status == PlayerStatus.ACTIVE:
                break
            self._action_queue.pop(0)
        if self._action_queue:
            self.current_player_id = self._action_queue[0]
            raiser = self.get_player(raiser_id)
            logger.info(f"Queue rebuilt after raise by {raiser.name if raiser else raiser_id}: {[self.get_player(pid).name for pid in self._action_queue if self.get_player(pid)]}")
        else:
            self.current_player_id = None
            self._next_phase()

    # ── Deal ──────────────────────────────────────────────────────────────────

    def _fresh_deck(self):
        self.deck = [Card(r, s) for r in RANKS for s in SUITS]
        random.shuffle(self.deck)

    def _deal(self, n=1) -> list[Card]:
        cards = self.deck[:n]
        self.deck = self.deck[n:]
        return cards

    def _post_blind(self, player: Player, amount: int, label: str):
        amount = min(amount, player.stack)
        player.stack -= amount
        player.bet_this_round += amount
        player.total_bet += amount
        self.pot += amount
        if player.stack == 0:
            player.status = PlayerStatus.ALL_IN
        self.round_log.append(f"{player.name} posts {label} ({amount})")

    # ── Start hand ────────────────────────────────────────────────────────────

    def start_hand(self):
        self.phase = Phase.PRE_FLOP
        self.community_cards = []
        self.pot = 0
        self.current_bet = 0
        self.round_log = []
        self.winners = []
        self._hand_log_offset = len(self.hand_log)
        self._fresh_deck()

        for p in self.players:
            p.status = PlayerStatus.ACTIVE if p.stack > 0 else PlayerStatus.OUT
            p.hole_cards = []
            p.bet_this_round = 0
            p.total_bet = 0

        alive = [p for p in self.players if p.status == PlayerStatus.ACTIVE]
        if len(alive) < 2:
            logger.warning(f"start_hand: only {len(alive)} active player(s), cannot start")
            return

        for p in alive:
            p.hole_cards = self._deal(2)
            # Track stats
            s = self.player_stats.setdefault(p.name, _empty_stats())
            s["hands_dealt"] += 1
            s["vpip_this_hand"] = False
            s["stack_start"] = p.stack

        if self.dealer_id is None or not self.get_player(self.dealer_id):
            self.dealer_id = alive[0].id
        dealer = self.get_player(self.dealer_id)
        if not dealer or dealer.stack == 0:
            self.advance_dealer()

        n = len(alive)
        dealer_pos = next((i for i, p in enumerate(alive) if p.id == self.dealer_id), 0)

        if n == 2:
            sb = alive[dealer_pos]
            bb = alive[(dealer_pos + 1) % n]
            utg_id = sb.id
        else:
            sb = alive[(dealer_pos + 1) % n]
            bb = alive[(dealer_pos + 2) % n]
            utg_id = alive[(dealer_pos + 3) % n].id

        self._post_blind(sb, self.small_blind, "small blind")
        self._post_blind(bb, self.big_blind, "big blind")
        self.current_bet = self.big_blind

        self._init_action_queue(utg_id)

        dealer_player = self.get_player(self.dealer_id)
        logger.info(
            f"=== Hand #{len(self.hand_history)+1} starting (room {self.room_id}) ==="
        )
        logger.info(
            f"  Players: {[f'{p.name}({p.stack})' for p in alive]}  "
            f"| Dealer: {dealer_player.name if dealer_player else '?'}  "
            f"| SB: {sb.name}  | BB: {bb.name}"
        )
        logger.info(f"  Action queue: {self._action_queue}")

    # ── Valid actions ─────────────────────────────────────────────────────────

    def current_player(self) -> Optional[Player]:
        return self.get_player(self.current_player_id) if self.current_player_id else None

    def valid_actions(self, player: Player) -> dict:
        to_call = max(0, self.current_bet - player.bet_this_round)
        to_call = min(to_call, player.stack)
        can_check = to_call == 0
        min_raise_total = max(self.current_bet + self.big_blind, self.current_bet * 2)
        min_raise_add = max(0, min_raise_total - player.bet_this_round)
        min_raise_add = min(min_raise_add, player.stack)
        can_raise = player.stack > to_call
        return {
            "fold": True,
            "check": can_check,
            "call": not can_check,
            "call_amount": to_call,
            "raise": can_raise,
            "min_raise": min_raise_add if can_raise else 0,
            "max_raise": player.stack,
        }

    # ── Apply action ──────────────────────────────────────────────────────────

    def apply_action(self, player_id: str, action: str, amount: int = 0) -> str:
        player = self.get_player(player_id)
        if player is None or player.status != PlayerStatus.ACTIVE:
            logger.warning(
                f"apply_action IGNORED: player_id={player_id} action={action} "
                f"status={player.status.value if player else 'NOT_FOUND'} "
                f"phase={self.phase.value}"
            )
            return "invalid"
        if self.current_player_id != player_id:
            logger.warning(
                f"apply_action NOT_YOUR_TURN: {player.name} tried {action} but "
                f"current={self.current_player_id} phase={self.phase.value}"
            )
            return "not_your_turn"

        va = self.valid_actions(player)
        s = self.player_stats.setdefault(player.name, _empty_stats())
        msg = ""

        if action == "fold":
            player.status = PlayerStatus.FOLDED
            msg = f"{player.name} folds"
            s["folds"] += 1
            self.round_log.append(msg)
            self.hand_log.append(msg)
            self._action_queue = [pid for pid in self._action_queue if pid != player_id]
            remaining = self.betting_players()
            logger.info(
                f"[{self.phase.value}] {player.name} FOLDS | "
                f"stack={player.stack} pot={self.pot} remaining_bettors={len(remaining)}"
            )
            if len(remaining) <= 1:
                self.current_player_id = None
                self._next_phase()
            else:
                self._advance_queue()

        elif action == "check" and va["check"]:
            msg = f"{player.name} checks"
            self.round_log.append(msg)
            self.hand_log.append(msg)
            logger.info(f"[{self.phase.value}] {player.name} CHECKS | stack={player.stack} pot={self.pot}")
            self._advance_queue()

        elif action == "call" and va["call"]:
            amt = va["call_amount"]
            player.stack -= amt
            player.bet_this_round += amt
            player.total_bet += amt
            self.pot += amt
            if player.stack == 0:
                player.status = PlayerStatus.ALL_IN
            msg = f"{player.name} calls {amt}"
            self.round_log.append(msg)
            self.hand_log.append(msg)
            logger.info(f"[{self.phase.value}] {player.name} CALLS {amt} | stack={player.stack} pot={self.pot}")
            # VPIP: voluntary call preflop (not counting the big blind's check)
            if self.phase == Phase.PRE_FLOP and not s["vpip_this_hand"]:
                s["vpip"] += 1
                s["vpip_this_hand"] = True
            self._advance_queue()

        elif action == "raise" and va["raise"]:
            amount = max(va["min_raise"], min(amount, va["max_raise"]))
            player.stack -= amount
            player.bet_this_round += amount
            player.total_bet += amount
            self.pot += amount
            self.current_bet = player.bet_this_round
            if player.stack == 0:
                player.status = PlayerStatus.ALL_IN
            msg = f"{player.name} raises to {player.bet_this_round}"
            self.round_log.append(msg)
            self.hand_log.append(msg)
            logger.info(f"[{self.phase.value}] {player.name} RAISES to {player.bet_this_round} | stack={player.stack} pot={self.pot}")
            s["raises"] += 1
            if self.phase == Phase.PRE_FLOP and not s["vpip_this_hand"]:
                s["vpip"] += 1
                s["vpip_this_hand"] = True
            self._rebuild_queue_after_raise(player_id)

        else:
            return self.apply_action(player_id, "check" if va["check"] else "call")

        return msg

    # ── Phase transitions ─────────────────────────────────────────────────────

    def _next_phase(self):
        for p in self.players:
            p.bet_this_round = 0
        self.current_bet = 0
        self.round_log = []

        ap = self.active_players()
        bp = self.betting_players()
        logger.info(f"_next_phase: from {self.phase.value} | active={[p.name for p in ap]} betting={[p.name for p in bp]} pot={self.pot}")

        if len(bp) <= 1 and len(ap) <= 1:
            self._resolve_showdown()
            return

        if len(bp) == 0 or all(p.status == PlayerStatus.ALL_IN for p in ap):
            while self.phase not in (Phase.SHOWDOWN, Phase.RIVER):
                self._deal_community_card()
            self.phase = Phase.SHOWDOWN
            self._resolve_showdown()
            return

        if self.phase == Phase.PRE_FLOP:
            self.phase = Phase.FLOP
            self.community_cards += self._deal(3)
        elif self.phase == Phase.FLOP:
            self.phase = Phase.TURN
            self.community_cards += self._deal(1)
        elif self.phase == Phase.TURN:
            self.phase = Phase.RIVER
            self.community_cards += self._deal(1)
        elif self.phase in (Phase.RIVER, Phase.SHOWDOWN):
            self.phase = Phase.SHOWDOWN
            self._resolve_showdown()
            return

        first = self._first_active_after(self.dealer_id)
        if first:
            self._init_action_queue(first)
        else:
            self.current_player_id = None

    def _deal_community_card(self):
        if self.phase == Phase.PRE_FLOP:
            self.phase = Phase.FLOP
            self.community_cards += self._deal(3)
        elif self.phase == Phase.FLOP:
            self.phase = Phase.TURN
            self.community_cards += self._deal(1)
        elif self.phase == Phase.TURN:
            self.phase = Phase.RIVER
            self.community_cards += self._deal(1)

    # ── Showdown ──────────────────────────────────────────────────────────────

    def _resolve_showdown(self):
        self.phase = Phase.SHOWDOWN
        ap = self.active_players()
        went_to_showdown = len(ap) > 1
        logger.info(f"=== Showdown: pot={self.pot} active={[p.name for p in ap]} community={[str(c) for c in self.community_cards]} ===")

        if not ap:
            return

        # Snapshot stacks before distributing pot (for hand history)
        stack_before = {p.name: self.player_stats.get(p.name, {}).get("stack_start", p.stack)
                        for p in self.players if p.status != PlayerStatus.OUT}

        if len(ap) == 1:
            winner = ap[0]
            winner.stack += self.pot
            msg = f"{winner.name} wins {self.pot} (uncontested)"
            self.hand_log.append(msg)
            self.winners = [{"player": winner.to_dict(reveal_cards=True),
                             "amount": self.pot, "hand": ""}]
            winners_info = [{"name": winner.name, "hand": "", "amount": self.pot}]
            showed = {}
        else:
            scored = [(best_hand(p.hole_cards + self.community_cards), p) for p in ap]
            scored.sort(key=lambda x: x[0], reverse=True)
            top_score = scored[0][0]
            winners = [p for score, p in scored if score == top_score]

            share = self.pot // len(winners)
            remainder = self.pot % len(winners)
            self.winners = []
            winners_info = []
            showed = {p.name: hand_name(p.hole_cards + self.community_cards)
                      for _, p in scored}
            for i, w in enumerate(winners):
                amt = share + (remainder if i == 0 else 0)
                w.stack += amt
                hn = showed[w.name]
                self.hand_log.append(f"{w.name} wins {amt} with {hn}")
                self.winners.append({
                    "player": w.to_dict(reveal_cards=True),
                    "amount": amt,
                    "hand": hn,
                })
                winners_info.append({"name": w.name, "hand": hn, "amount": amt})

        # Update per-player stats
        winner_names = {w["name"] for w in winners_info}
        for p in self.players:
            if p.status == PlayerStatus.OUT:
                continue
            s = self.player_stats.setdefault(p.name, _empty_stats())
            if p.name in winner_names:
                s["wins"] += 1
            if p.name in showed:
                s["showdown_hands"] = (s["showdown_hands"] + [showed[p.name]])[-5:]

        winner_strs = [f"{w['name']} ({w['hand'] or 'uncontested'}) +{w['amount']}" for w in winners_info]
        logger.info(f"  Winners: {winner_strs}")

        # Record hand history
        community_str = " ".join(str(c) for c in self.community_cards) or "—"
        hand_entry = {
            "hand_num": len(self.hand_history) + 1,
            "community": community_str,
            "pot": sum(w["amount"] for w in winners_info),
            "went_to_showdown": went_to_showdown,
            "winners": winners_info,
            "actions": self.hand_log[self._hand_log_offset:],
            "players": [
                {
                    "name": p.name,
                    "stack_before": stack_before.get(p.name, 0),
                    "stack_after": p.stack,
                    "showed": showed.get(p.name) if went_to_showdown else None,
                    "hole_cards": [c.to_dict() for c in p.hole_cards]
                        if p.status in (PlayerStatus.ACTIVE, PlayerStatus.ALL_IN)
                        else [],
                }
                for p in self.players
                if p.status != PlayerStatus.OUT
            ],
        }
        self.hand_history.append(hand_entry)
        self.pot = 0

    # ── Equity & learning hints ───────────────────────────────────────────────

    def calculate_equities(self) -> dict[str, float]:
        """Monte Carlo / exact win-probability for each active player."""
        active = [p for p in self.players
                  if p.status in (PlayerStatus.ACTIVE, PlayerStatus.ALL_IN)
                  and p.hole_cards]
        if len(active) < 2:
            return {p.id: 1.0 for p in active} if active else {}

        known = {(c.rank, c.suit) for p in active for c in p.hole_cards}
        known |= {(c.rank, c.suit) for c in self.community_cards}
        remaining = [Card(r, s) for r in RANKS for s in SUITS if (r, s) not in known]
        cards_needed = 5 - len(self.community_cards)

        wins: dict[str, float] = {p.id: 0.0 for p in active}
        total = 0
        community = self.community_cards

        def _eval(extra: list) -> None:
            nonlocal total
            board = community + extra
            scores = [(best_hand(p.hole_cards + board), p) for p in active]
            top = max(s for s, _ in scores)
            tied = [p for s, p in scores if s == top]
            share = 1.0 / len(tied)
            for p in tied:
                wins[p.id] += share
            total += 1

        if cards_needed == 0:
            _eval([])
        elif cards_needed == 1:
            for c in remaining:
                _eval([c])
        elif cards_needed == 2:
            for i in range(len(remaining)):
                for j in range(i + 1, len(remaining)):
                    _eval([remaining[i], remaining[j]])
        else:
            # Pre-flop / 3-card run-out: Monte Carlo
            for _ in range(1200):
                _eval(random.sample(remaining, cards_needed))

        if not total:
            return {}
        return {pid: round(wins[pid] / total, 3) for pid in wins}

    def calculate_player_equity(self, player: Player, num_sims: int = 800) -> float:
        """Monte Carlo equity from the player's own perspective (opponents' cards unknown)."""
        if not player.hole_cards:
            return 0.0
        opps = [p for p in self.players
                if p.id != player.id and p.status in (PlayerStatus.ACTIVE, PlayerStatus.ALL_IN)]
        if not opps:
            return 1.0
        known = {(c.rank, c.suit) for c in player.hole_cards}
        known |= {(c.rank, c.suit) for c in self.community_cards}
        remaining = [Card(r, s) for r in RANKS for s in SUITS if (r, s) not in known]
        n_opp = len(opps)
        cards_needed = 5 - len(self.community_cards)
        total_extra = 2 * n_opp + cards_needed
        wins = 0.0
        for _ in range(num_sims):
            sample = random.sample(remaining, total_extra)
            board = list(self.community_cards) + sample[2 * n_opp:]
            my_score = best_hand(player.hole_cards + board)
            opp_best = max(best_hand(sample[i * 2:(i + 1) * 2] + board) for i in range(n_opp))
            if my_score > opp_best:
                wins += 1
            elif my_score == opp_best:
                wins += 0.5
        return round(wins / num_sims, 3)

    def learning_hints(self, player: Player, equity: float) -> dict:
        """Generate hand description, draw info, pot odds, and a strategic tip."""
        hole, community = player.hole_cards, self.community_cards
        # Hand description
        if len(hole) + len(community) >= 5:
            rank = best_hand(hole + community)
            groups = rank[1] if rank else []
            if rank and rank[0] == 2 and len(groups) >= 2:
                current_hand = f"Two Pair ({RANKS[groups[0]]}s and {RANKS[groups[1]]}s)"
            elif rank and rank[0] == 1 and groups:
                current_hand = f"One Pair ({RANKS[groups[0]]}s)"
            elif rank and rank[0] == 3 and groups:
                current_hand = f"Three of a Kind ({RANKS[groups[0]]}s)"
            else:
                current_hand = HAND_NAMES[rank[0]] if rank else "High Card"
        else:
            current_hand = describe_preflop_hand(hole)
        # Draw detection (flop/turn only)
        draws = []
        if self.phase in (Phase.FLOP, Phase.TURN) and len(community) >= 3:
            from collections import Counter as _C
            all_cards = hole + community
            suit_counts = _C(c.suit for c in all_cards)
            if max(suit_counts.values()) == 4:
                draws.append("Flush draw")
            unique_ranks = sorted({RANK_VALUE[c.rank] for c in all_cards})
            if 12 in unique_ranks:
                unique_ranks = [-1] + unique_ranks
            best_run = run = 1
            for i in range(1, len(unique_ranks)):
                run = run + 1 if unique_ranks[i] == unique_ranks[i - 1] + 1 else 1
                best_run = max(best_run, run)
            if best_run >= 4:
                draws.append("Open-ended straight draw")
            elif not draws:
                for i in range(len(unique_ranks) - 3):
                    w = unique_ranks[i:i + 4]
                    if w[-1] - w[0] == 4 and len(w) == 4:
                        draws.append("Gutshot straight draw")
                        break
        # Pot odds
        pot_odds = None
        va = self.valid_actions(player) if player.status == PlayerStatus.ACTIVE else {}
        call_amt = va.get("call_amount", 0)
        if call_amt and self.pot:
            ratio = self.pot / call_amt
            needed = 100 * call_amt / (self.pot + call_amt)
            pot_odds = f"Pot odds: {ratio:.1f}:1 — you need ~{needed:.0f}% equity to call profitably"
        return {
            "hand_name": current_hand,
            "draws": draws,
            "pot_odds": pot_odds,
            "tip": _learning_tip(equity, draws, call_amt, self.pot),
        }

    # ── State serialization ───────────────────────────────────────────────────

    def state_for_player(self, player_id: str) -> dict:
        player = self.get_player(player_id)
        players_data = []
        is_spectator = player is None
        for p in self.players:
            reveal = (p.id == player_id) or (self.phase == Phase.SHOWDOWN) or (is_spectator and p.is_llm)
            players_data.append(p.to_dict(reveal_cards=reveal))

        va = {}
        if (player and player.status == PlayerStatus.ACTIVE
                and self.current_player_id == player_id):
            va = self.valid_actions(player)

        state = {
            "room_id": self.room_id,
            "phase": self.phase.value,
            "players": players_data,
            "community_cards": [c.to_dict() for c in self.community_cards],
            "pot": self.pot,
            "current_bet": self.current_bet,
            "current_player_id": self.current_player_id,
            "your_id": player_id,
            "valid_actions": va,
            "round_log": self.round_log,
            "hand_log": self.hand_log[-30:],
            "dealer_idx": self._dealer_idx_for_display(),
            "winners": self.winners,
            "num_human_slots": self.num_human_slots,
            "num_llm_slots": self.num_llm_slots,
            "hand_num": len(self.hand_history),
            "learning_mode": self.learning_mode,
        }
        if is_spectator and self.phase not in (Phase.WAITING, Phase.SHOWDOWN):
            state["equities"] = self.calculate_equities()
        if (self.learning_mode
                and player is not None
                and not player.is_llm
                and self.phase not in (Phase.WAITING, Phase.SHOWDOWN)
                and player.status in (PlayerStatus.ACTIVE, PlayerStatus.ALL_IN)
                and player.hole_cards):
            eq = self.calculate_player_equity(player)
            state["learning"] = {"equity": eq, **self.learning_hints(player, eq)}
        return state

    # ── LLM prompt ────────────────────────────────────────────────────────────

    def text_state_for_llm(self, player: Player) -> str:
        phase_label = self.phase.value.replace("_", " ").upper()
        community = " ".join(str(c) for c in self.community_cards) or "none yet"
        hole = " ".join(str(c) for c in player.hole_cards)
        va = self.valid_actions(player)
        to_call = va.get("call_amount", 0)

        # ── Current situation ──────────────────────────────────────────────
        situation_lines = [
            f"  Pot: {self.pot}  |  Your stack: {player.stack}  |  To call: {to_call}",
        ]
        if to_call > 0 and self.pot > 0:
            ratio = (self.pot) / to_call
            equity_needed = 100 * to_call / (self.pot + to_call)
            situation_lines.append(
                f"  Pot odds: calling {to_call} into {self.pot} ({ratio:.1f}:1)"
                f" — need ~{equity_needed:.0f}% equity to break even"
            )

        opponents = [p for p in self.active_players() if p.id != player.id]
        pos_labels = {0: "BTN", 1: "SB", 2: "BB", 3: "UTG", 4: "HJ", 5: "CO"}
        ap = self.active_players()
        pos_idx = next((i for i, p in enumerate(ap) if p.id == player.id), 0)
        pos = pos_labels.get(pos_idx, "MP")
        situation_lines.append(
            f"  Position: {pos}  |  Opponents still in: {len(opponents)}"
        )

        # ── Actions this round ────────────────────────────────────────────
        history = "; ".join(self.round_log[-10:]) if self.round_log else "none"

        # ── Player tendencies ─────────────────────────────────────────────
        tendency_lines = []
        total_hands = max(
            (self.player_stats.get(p.name, {}).get("hands_dealt", 0) for p in self.players),
            default=0
        )
        for p in self.players:
            if p.id == player.id or p.status == PlayerStatus.OUT:
                continue
            s = self.player_stats.get(p.name, _empty_stats())
            dealt = s["hands_dealt"]
            if dealt < 2:
                continue
            vpip_pct = int(100 * s["vpip"] / dealt)
            style = "aggressive" if s["raises"] >= dealt * 0.4 else (
                "passive caller" if vpip_pct > 50 else "tight")
            showed = ", ".join(s["showdown_hands"][-3:]) if s["showdown_hands"] else "n/a"
            line = (
                f"  {p.name:<12} {dealt} hands — VPIP {vpip_pct}%,"
                f" raised {s['raises']}×, won {s['wins']} — {style}."
            )
            if s["showdown_hands"]:
                line += f" Showed: {showed}"
            tendency_lines.append(line)

        # ── Recent hand results ───────────────────────────────────────────
        history_lines = []
        for h in self.hand_history[-4:]:
            winners_str = ", ".join(
                f"{w['name']} ({w['hand'] or 'uncontested'})" for w in h["winners"]
            )
            pot_str = sum(w["amount"] for w in h["winners"])
            sd = "showdown" if h["went_to_showdown"] else "no showdown"
            history_lines.append(
                f"  Hand {h['hand_num']}: {winners_str} won {pot_str} — {h['community']} [{sd}]"
            )

        # ── Valid actions ─────────────────────────────────────────────────
        action_parts = []
        if va.get("check"):
            action_parts.append("check")
        if va.get("call"):
            action_parts.append(f"call {to_call}")
        if va.get("raise"):
            action_parts.append(f"raise (min {va['min_raise']}, max {va['max_raise']})")
        action_parts.append("fold")
        valid_str = " | ".join(action_parts)

        # ── Assemble ──────────────────────────────────────────────────────
        sections = [f"=== TEXAS HOLD'EM — {phase_label} ===\n"]

        sections.append("YOUR HAND")
        sections.append(f"  Hole cards  : {hole}")
        sections.append(f"  Community   : {community}\n")

        sections.append("CURRENT SITUATION")
        sections.extend(situation_lines)
        sections.append("")

        sections.append("ACTION THIS ROUND")
        sections.append(f"  {history}\n")

        if tendency_lines:
            sections.append(f"PLAYER TENDENCIES  (over {total_hands} hands)")
            sections.extend(tendency_lines)
            sections.append("")

        if history_lines:
            sections.append("RECENT HAND RESULTS")
            sections.extend(history_lines)
            sections.append("")

        sections.append("VALID ACTIONS")
        sections.append(f"  {valid_str}\n")
        sections.append("Respond with exactly one line: FOLD, CHECK, CALL, or RAISE <amount>")

        return "\n".join(sections)
