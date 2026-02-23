import random
import asyncio
import discord
from enum import Enum

# ─── Constants ────────────────────────────────────────────────────────────────

NIGHT_ACTION_TIMEOUT = 30  # seconds
DAY_DISCUSSION_TIME  = 30  # seconds
VOTE_TIMEOUT         = 30  # seconds

# ─── Enums ────────────────────────────────────────────────────────────────────

class Phase(Enum):
    WAITING = "waiting"
    NIGHT   = "night"
    DAY     = "day"
    VOTING  = "voting"
    ENDED   = "ended"

class Role(Enum):
    WEREWOLF  = "Werewolf"
    SEER      = "Seer"
    DOCTOR    = "Doctor"
    HUNTER    = "Hunter"
    WITCH     = "Witch"
    BODYGUARD = "Bodyguard"
    CURSED    = "Cursed"
    JESTER    = "Jester"
    VILLAGER  = "Villager"

# ─── Role info ────────────────────────────────────────────────────────────────

ROLE_INFO = {
    Role.WEREWOLF: {
        "emoji": "🐺",
        "team": "Werewolves",
        "description": (
            "Setiap malam, kamu dan sesama Werewolf memilih satu pemain untuk dibunuh. "
            "Tujuanmu: kalahkan jumlah Villager."
        ),
        "color": discord.Color.red(),
    },
    Role.SEER: {
        "emoji": "🔮",
        "team": "Villagers",
        "description": (
            "Setiap malam kamu bisa memeriksa satu pemain dan mengetahui apakah dia "
            "Werewolf atau bukan. **Cursed akan terlihat sebagai Villager** sampai dia berubah."
        ),
        "color": discord.Color.purple(),
    },
    Role.DOCTOR: {
        "emoji": "💉",
        "team": "Villagers",
        "description": (
            "Setiap malam kamu bisa melindungi satu pemain dari serangan Werewolf. "
            "Kamu bisa melindungi dirimu sendiri, tapi tidak dua malam berturut-turut."
        ),
        "color": discord.Color.green(),
    },
    Role.HUNTER: {
        "emoji": "🏹",
        "team": "Villagers",
        "description": (
            "Jika kamu dibunuh (kapan pun), kamu bisa langsung menembak satu pemain "
            "lain sebelum mati. Cek DM saat kamu mati!"
        ),
        "color": discord.Color.orange(),
    },
    Role.WITCH: {
        "emoji": "🧙",
        "team": "Villagers",
        "description": (
            "Kamu punya dua ramuan: satu untuk menghidupkan korban malam ini, "
            "satu untuk meracuni pemain lain. Masing-masing hanya bisa dipakai sekali."
        ),
        "color": discord.Color.dark_teal(),
    },
    Role.BODYGUARD: {
        "emoji": "🛡️",
        "team": "Villagers",
        "description": (
            "Setiap malam kamu bisa melindungi satu pemain. "
            "Jika target diserang Werewolf, **kamu mati menggantikan target** tersebut. "
            "Kamu tidak bisa melindungi orang yang sama dua malam berturut-turut."
        ),
        "color": discord.Color.blue(),
    },
    Role.CURSED: {
        "emoji": "😈",
        "team": "Villagers",
        "description": (
            "Kamu mulai sebagai Villager biasa. "
            "Tapi jika **Werewolf memilihmu sebagai target malam**, kamu tidak mati — "
            "kamu **berubah menjadi Werewolf** dan bergabung dengan tim mereka! "
            "Seer akan melihatmu sebagai Villager sampai kamu berubah."
        ),
        "color": discord.Color.dark_magenta(),
    },
    Role.JESTER: {
        "emoji": "🃏",
        "team": "Solo",
        "description": (
            "Tujuanmu bukan menang bersama Villager atau Werewolf — "
            "kamu menang **hanya jika kamu berhasil dieksekusi oleh desa saat voting siang**. "
            "Bertingkahlah mencurigakan agar desa salah mengeksekusi kamu!"
        ),
        "color": discord.Color.from_rgb(255, 215, 0),
    },
    Role.VILLAGER: {
        "emoji": "👨‍🌾",
        "team": "Villagers",
        "description": (
            "Kamu adalah warga biasa. Gunakan logika dan diskusi untuk menemukan "
            "Werewolf dan hilangkan mereka lewat voting siang."
        ),
        "color": discord.Color.gold(),
    },
}

# ─── Role assignment table ────────────────────────────────────────────────────

# ─── Special role pool (dipilih acak tiap game) ──────────────────────────────
#
# Setiap slot "special" dipilih secara acak dari pool yang sesuai.
# ALWAYS_INCLUDE = wajib ada di semua game.
# POOL_SUPPORT   = role pendukung Villager (dipilih acak N dari pool ini).
# POOL_CHAOS     = role yang bikin game lebih chaotic (dipilih acak).
# Dengan begitu game 5 orang bisa dapat kombinasi berbeda tiap sesi!

_POOL_SUPPORT = [Role.DOCTOR, Role.HUNTER, Role.BODYGUARD, Role.WITCH]
_POOL_CHAOS   = [Role.CURSED, Role.JESTER]


def build_role_list(player_count: int) -> list[Role]:
    """
    Pilih role secara acak dari pool tiap game.
    Seer selalu ada. Wolf count ~25% (min 1). Sisa slot diisi acak dari pool,
    sisanya Villager — sehingga tiap game terasa berbeda.
    """
    # ── Jumlah wolf ───────────────────────────────────────────────────────────
    if player_count <= 4:
        wolf_count = 1
    elif player_count <= 7:
        wolf_count = 1 if player_count <= 5 else 2
    elif player_count <= 10:
        wolf_count = 2
    else:
        wolf_count = max(2, player_count // 4)

    # ── Slot special yang tersedia setelah wolf + Seer ────────────────────────
    base_count    = wolf_count + 1          # wolves + Seer
    special_slots = player_count - base_count  # berapa sisa slot buat special/villager

    # ── Berapa slot support & chaos ───────────────────────────────────────────
    # Skala: makin banyak pemain makin banyak role unik
    if player_count <= 5:
        n_support = 1   # 1 random support
        n_chaos   = random.randint(0, 1)
    elif player_count <= 7:
        n_support = 2
        n_chaos   = 1
    elif player_count <= 9:
        n_support = random.randint(2, 3)
        n_chaos   = random.randint(1, 2)
    elif player_count <= 11:
        n_support = random.randint(3, 4)
        n_chaos   = 2
    else:
        n_support = min(4, player_count // 3)
        n_chaos   = 2

    # Jangan melebihi slot yang tersedia
    total_special = n_support + n_chaos
    if total_special > special_slots:
        # Kurangi proporsional
        excess    = total_special - special_slots
        n_chaos   = max(0, n_chaos   - excess)
        excess    = max(0, excess - (n_chaos + 1))
        n_support = max(0, n_support - excess)

    # ── Pilih role acak dari pool ─────────────────────────────────────────────
    support_pool = _POOL_SUPPORT.copy()
    chaos_pool   = _POOL_CHAOS.copy()
    random.shuffle(support_pool)
    random.shuffle(chaos_pool)

    picked_support = support_pool[:n_support]
    picked_chaos   = chaos_pool[:n_chaos]

    # ── Rakit final list ──────────────────────────────────────────────────────
    roles  = [Role.WEREWOLF] * wolf_count
    roles += [Role.SEER]
    roles += picked_support
    roles += picked_chaos

    # Isi sisa dengan Villager
    while len(roles) < player_count:
        roles.append(Role.VILLAGER)

    return roles

# ─── Game class ───────────────────────────────────────────────────────────────

class WerewolfGame:
    def __init__(self, bot: discord.Client, channel: discord.TextChannel):
        self.bot     = bot
        self.channel = channel

        self.players:  list[discord.Member]       = []
        self.roles:    dict[discord.Member, Role] = {}
        self.alive:    list[discord.Member]       = []
        self.dead:     list[discord.Member]       = []
        self.phase                                 = Phase.WAITING
        self.day_number                            = 0

        # ── Night state ───────────────────────────────────────────────────────
        self.night_kill:           discord.Member | None = None
        self.doctor_save:          discord.Member | None = None   # Doctor target
        self.bodyguard_protect:    discord.Member | None = None   # Bodyguard target
        self.doctor_last_save:     discord.Member | None = None
        self.bodyguard_last_save:  discord.Member | None = None
        self.witch_heal:           bool                  = True
        self.witch_poison:         bool                  = True
        self.witch_poison_target:  discord.Member | None = None

        # ── Voting state ──────────────────────────────────────────────────────
        self.votes:        dict[discord.Member, discord.Member] = {}
        self.vote_message: discord.Message | None               = None

        # ── Internal tracking ─────────────────────────────────────────────────
        self._wolf_votes:    dict[discord.Member, discord.Member] = {}
        self._night_acted:   set[discord.Member]                  = set()
        self._pending_hunter: discord.Member | None               = None

        # Jester win tracking
        self.jester_winner: discord.Member | None = None

    # ── Player management ─────────────────────────────────────────────────────

    def add_player(self, member: discord.Member) -> bool:
        if member in self.players:
            return False
        self.players.append(member)
        return True

    def remove_player(self, member: discord.Member) -> bool:
        if member not in self.players:
            return False
        self.players.remove(member)
        return True

    # ── Helpers ───────────────────────────────────────────────────────────────

    def role_of(self, member: discord.Member) -> Role | None:
        return self.roles.get(member)

    def is_alive(self, member: discord.Member) -> bool:
        return member in self.alive

    def get_wolves(self) -> list[discord.Member]:
        return [p for p in self.alive if self.roles[p] == Role.WEREWOLF]

    def get_alive_non_wolves(self) -> list[discord.Member]:
        """Returns all alive players who are NOT on wolf team (includes Jester, Cursed pre-turn)."""
        return [p for p in self.alive if self.roles[p] != Role.WEREWOLF]

    def get_role_member(self, role: Role) -> discord.Member | None:
        for p in self.alive:
            if self.roles[p] == role:
                return p
        return None

    def alive_list_str(self) -> str:
        return "\n".join(f"• {p.display_name}" for p in self.alive)

    # ── Role assignment ───────────────────────────────────────────────────────

    def assign_roles(self):
        shuffled  = self.players.copy()
        random.shuffle(shuffled)
        role_list = build_role_list(len(shuffled))
        random.shuffle(role_list)

        self.roles      = {p: r for p, r in zip(shuffled, role_list)}
        self.alive      = shuffled.copy()
        self.dead       = []
        self.phase      = Phase.NIGHT
        self.day_number = 1

    # ── Win condition ─────────────────────────────────────────────────────────

    def check_win(self) -> str | None:
        """
        Returns: 'Villagers', 'Werewolves', 'Jester:<name>', or None.
        Jester wins are flagged separately and take priority.
        """
        if self.jester_winner:
            return f"Jester:{self.jester_winner.display_name}"

        wolves     = self.get_wolves()
        # Count non-wolves, excluding Jester (Jester neither helps nor counts as Villager win)
        non_wolves = [p for p in self.alive if self.roles[p] not in (Role.WEREWOLF,)]

        if not wolves:
            return "Villagers"
        # Wolves win when they equal or outnumber everyone else (including Jester)
        others = [p for p in self.alive if self.roles[p] != Role.WEREWOLF]
        if len(wolves) >= len(others):
            return "Werewolves"
        return None

    # ── Eliminate ─────────────────────────────────────────────────────────────

    def eliminate(self, member: discord.Member):
        if member in self.alive:
            self.alive.remove(member)
            self.dead.append(member)

    # ── Wolf vote ─────────────────────────────────────────────────────────────

    def cast_wolf_vote(self, wolf: discord.Member, target: discord.Member) -> bool:
        if wolf not in self.alive or self.roles[wolf] != Role.WEREWOLF:
            return False
        if target not in self.alive or self.roles.get(target) == Role.WEREWOLF:
            return False
        self._wolf_votes[wolf] = target
        return True

    def tally_wolf_vote(self) -> discord.Member | None:
        if not self._wolf_votes:
            return None
        from collections import Counter
        c = Counter(self._wolf_votes.values())
        return c.most_common(1)[0][0]

    # ── Seer check ────────────────────────────────────────────────────────────

    def seer_check(self, target: discord.Member) -> bool | None:
        """
        True  = is wolf (or Cursed who already turned)
        False = not wolf
        None  = invalid target
        Cursed before turning appears as False (Villager).
        """
        if target not in self.alive:
            return None
        return self.roles[target] == Role.WEREWOLF

    # ── Night resolve ─────────────────────────────────────────────────────────

    def resolve_night(self) -> dict:
        """
        Resolve all night actions in priority order:
          1. Wolf target chosen
          2. Cursed check — if target is Cursed, convert instead of kill
          3. Bodyguard intercept — BG dies instead of target
          4. Doctor save — cancels kill
          5. Witch heal — cancels kill (if already set via WitchView)
          6. Witch poison — kills separate target
          7. Apply all deaths

        Returns dict:
          wolf_target, killed, saved, poisoned,
          cursed_turned (Member|None), bodyguard_died (Member|None)
        """
        wolf_target = self.tally_wolf_vote()
        self.night_kill = wolf_target

        killed           = None
        saved            = False
        cursed_turned    = None
        bodyguard_died   = None
        poisoned         = None

        if wolf_target and wolf_target in self.alive:
            target_role = self.roles[wolf_target]

            # ── Cursed: convert instead of kill ───────────────────────────────
            if target_role == Role.CURSED:
                self.roles[wolf_target] = Role.WEREWOLF
                cursed_turned = wolf_target
                # No kill happens — Cursed joins wolves silently

            else:
                # ── Bodyguard intercept ───────────────────────────────────────
                if (self.bodyguard_protect == wolf_target
                        and self.bodyguard_protect in self.alive):
                    bg = self.get_role_member(Role.BODYGUARD)
                    # BG could be dead already (e.g. poisoned) — only intercept if alive
                    if bg and bg in self.alive:
                        bodyguard_died = bg
                        killed = bg         # BG dies instead
                    else:
                        # BG not alive, target still gets killed
                        killed = wolf_target
                # ── Doctor save ───────────────────────────────────────────────
                elif wolf_target == self.doctor_save and wolf_target in self.alive:
                    saved = True
                # ── Normal kill ───────────────────────────────────────────────
                else:
                    killed = wolf_target

        # Witch poison (already set in WitchView)
        if self.witch_poison_target and self.witch_poison_target in self.alive:
            poisoned = self.witch_poison_target

        # Apply deaths
        if killed:
            self.eliminate(killed)
        if poisoned and poisoned != killed:
            self.eliminate(poisoned)

        # Reset night state
        result = {
            "wolf_target":    wolf_target,
            "killed":         killed,
            "saved":          saved,
            "poisoned":       poisoned,
            "cursed_turned":  cursed_turned,
            "bodyguard_died": bodyguard_died,
        }

        self._wolf_votes          = {}
        self._night_acted         = set()
        self.doctor_last_save     = self.doctor_save
        self.bodyguard_last_save  = self.bodyguard_protect
        self.doctor_save          = None
        self.bodyguard_protect    = None
        self.witch_poison_target  = None
        self.night_kill           = None

        self.phase      = Phase.DAY
        self.day_number += 1
        return result

    # ── Day voting ────────────────────────────────────────────────────────────

    def cast_vote(self, voter: discord.Member, target: discord.Member) -> bool:
        if voter not in self.alive:
            return False
        if target not in self.alive:
            return False
        if voter == target:
            return False
        self.votes[voter] = target
        return True

    def tally_votes(self) -> discord.Member | None:
        """Most-voted player, or None on tie."""
        if not self.votes:
            return None
        from collections import Counter
        c   = Counter(self.votes.values())
        top = c.most_common(2)
        if len(top) == 1:
            return top[0][0]
        if top[0][1] > top[1][1]:
            return top[0][0]
        return None  # tie

    def resolve_vote(self) -> discord.Member | None:
        """
        Eliminate the voted player.
        If eliminated is Jester → flag jester_winner.
        Returns eliminated member or None.
        """
        target = self.tally_votes()
        self.votes = {}
        if target:
            if self.roles.get(target) == Role.JESTER:
                self.jester_winner = target
            self.eliminate(target)
        self.phase = Phase.NIGHT
        return target