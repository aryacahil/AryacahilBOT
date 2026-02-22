"""
WowoCash Economy Engine - Fixed Version
"""

import json
import random
from datetime import datetime, date, timedelta
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

DATA_DIR  = Path(__file__).parent.parent / "data"
DATA_FILE = DATA_DIR / "wowocash.json"

# ─── Constants ────────────────────────────────────────────────────────────────

CURRENCY_ICON      = "💰"
DAILY_BASE         = 100
DAILY_STREAK_BONUS = 20
DAILY_STREAK_MAX   = 7
TRANSFER_FEE_PCT   = 0.05
GACHA_PULL_COST    = 150
GACHA_PITY_LIMIT   = 50
GACHA_SSR_PITY     = 100

RARITY_EMOJI = {"N": "⚪", "R": "🔵", "SR": "🟣", "SSR": "🌟"}

WW_REWARDS = {
    "win":          200,
    "lose":          50,
    "survive":       75,
    "jester_win":   500,
    "first_blood":   30,
}

SHOP_ITEMS = {
    "role_hint": {
        "id": "role_hint", "name": "📜 Role Hint",
        "description": "Reveal satu pemain secara acak di awal game berikutnya (hanya untukmu).",
        "price": 300, "max_stack": 5, "category": "game",
    },
    "double_vote": {
        "id": "double_vote", "name": "🗳️ Double Vote",
        "description": "Vote-mu dihitung 2x pada 1 voting siang. Satu kali pakai.",
        "price": 500, "max_stack": 3, "category": "game",
    },
    "shield": {
        "id": "shield", "name": "🛡️ Shield",
        "description": "Sekali dalam sebuah game, selamat dari 1 serangan malam.",
        "price": 750, "max_stack": 2, "category": "game",
    },
    "gacha_ticket": {
        "id": "gacha_ticket", "name": "🎟️ Gacha Ticket",
        "description": "Satu kali pull gacha gratis.",
        "price": 200, "max_stack": 20, "category": "misc",
    },
    "vip_badge": {
        "id": "vip_badge", "name": "⭐ VIP Badge",
        "description": "Badge eksklusif di profil WowoCash kamu.",
        "price": 2000, "max_stack": 1, "category": "cosmetic",
    },
    "lucky_charm": {
        "id": "lucky_charm", "name": "🍀 Lucky Charm",
        "description": "Tingkatkan peluang gacha SSR +2% untuk 10 pull berikutnya.",
        "price": 400, "max_stack": 3, "category": "misc",
    },
}

GACHA_POOL = [
    {"rarity": "N",   "type": "coins", "amount": 50,   "label": "50 WowoCash",   "weight": 35},
    {"rarity": "N",   "type": "coins", "amount": 100,  "label": "100 WowoCash",  "weight": 25},
    {"rarity": "R",   "type": "coins", "amount": 300,  "label": "300 WowoCash",  "weight": 15},
    {"rarity": "R",   "type": "item",  "amount": 1,    "item": "gacha_ticket",   "weight": 10},
    {"rarity": "SR",  "type": "coins", "amount": 700,  "label": "700 WowoCash",  "weight": 7},
    {"rarity": "SR",  "type": "item",  "amount": 1,    "item": "role_hint",      "weight": 4},
    {"rarity": "SR",  "type": "item",  "amount": 1,    "item": "double_vote",    "weight": 2},
    {"rarity": "SSR", "type": "coins", "amount": 2000, "label": "2000 WowoCash", "weight": 1},
    {"rarity": "SSR", "type": "item",  "amount": 1,    "item": "shield",         "weight": 0.7},
    {"rarity": "SSR", "type": "item",  "amount": 1,    "item": "vip_badge",      "weight": 0.3},
]

DAILY_MISSIONS = [
    {"id": "play_1",    "name": "Pemain Aktif",  "desc": "Main 1 game Werewolf",  "type": "play",    "target": 1, "reward": 80},
    {"id": "survive_1", "name": "Survivor",      "desc": "Selamat di 1 game",     "type": "survive", "target": 1, "reward": 100},
    {"id": "win_1",     "name": "Menang!",        "desc": "Menang 1 game",         "type": "win",     "target": 1, "reward": 150},
    {"id": "vote_3",    "name": "Suara Rakyat",  "desc": "Berikan vote 3 kali",   "type": "vote",    "target": 3, "reward": 60},
    {"id": "login",     "name": "Login Harian",  "desc": "Claim daily reward",    "type": "daily",   "target": 1, "reward": 50},
    {"id": "casino_3",  "name": "Penjudi Harian","desc": "Main casino 3 kali",    "type": "casino",  "target": 3, "reward": 120},
    {"id": "work_1",    "name": "Pekerja Keras", "desc": "Kerja 1 kali hari ini", "type": "work",    "target": 1, "reward": 50},
]

WEEKLY_MISSIONS = [
    {"id": "w_play_5",    "name": "Petualang Mingguan", "desc": "Main 5 game minggu ini",         "type": "play",     "target": 5,  "reward": 500},
    {"id": "w_win_3",     "name": "Juara Mingguan",     "desc": "Menang 3 game minggu ini",       "type": "win",      "target": 3,  "reward": 700},
    {"id": "w_gacha_3",   "name": "Penjudi Sejati",     "desc": "Pull gacha 3 kali minggu ini",   "type": "gacha",    "target": 3,  "reward": 300},
    {"id": "w_transfer",  "name": "Dermawan",           "desc": "Transfer ke 1 orang",            "type": "transfer", "target": 1,  "reward": 200},
    {"id": "w_casino_10", "name": "High Roller",        "desc": "Main casino 10 kali minggu ini", "type": "casino",   "target": 10, "reward": 600},
    {"id": "w_work_5",    "name": "Rajin Kerja",        "desc": "Kerja 5 kali minggu ini",        "type": "work",     "target": 5,  "reward": 400},
    {"id": "w_rob_3",     "name": "Kriminal",           "desc": "Rob orang 3 kali minggu ini",    "type": "rob",      "target": 3,  "reward": 350},
]

# ─── Cooldowns (seconds) ──────────────────────────────────────────────────────
COOLDOWN_WORK   = 3600
COOLDOWN_ROB    = 7200
COOLDOWN_HOURLY = 3600

# ─── Work jobs ────────────────────────────────────────────────────────────────
WORK_JOBS = [
    {"name": "Nelayan",   "emoji": "🎣", "min": 80,  "max": 200},
    {"name": "Petani",    "emoji": "🌾", "min": 70,  "max": 180},
    {"name": "Pedagang",  "emoji": "🛒", "min": 100, "max": 250},
    {"name": "Dokter",    "emoji": "🩺", "min": 150, "max": 350},
    {"name": "Hacker",    "emoji": "💻", "min": 120, "max": 300},
    {"name": "Streamer",  "emoji": "🎮", "min": 50,  "max": 500},
    {"name": "Penyanyi",  "emoji": "🎤", "min": 60,  "max": 400},
    {"name": "Pengacara", "emoji": "⚖️", "min": 200, "max": 500},
    {"name": "Mekanik",   "emoji": "🔧", "min": 90,  "max": 220},
    {"name": "Chef",      "emoji": "👨‍🍳", "min": 80,  "max": 230},
]

# ─── Slot symbols ─────────────────────────────────────────────────────────────
SLOT_SYMBOLS = ["🍒", "🍋", "🍇", "💎", "7️⃣", "⭐", "🔔", "🃏"]
SLOT_WEIGHTS  = [30,   25,   20,   10,    5,     5,    4,    1  ]

SLOT_PAYOUTS = {
    ("🍒","🍒","🍒"): 2,
    ("🍋","🍋","🍋"): 3,
    ("🍇","🍇","🍇"): 4,
    ("🔔","🔔","🔔"): 5,
    ("⭐","⭐","⭐"): 8,
    ("💎","💎","💎"): 15,
    ("7️⃣","7️⃣","7️⃣"): 20,
    ("🃏","🃏","🃏"): 50,
}


# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER
# ══════════════════════════════════════════════════════════════════════════════

def _load() -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text(json.dumps({"users": {}, "meta": {"version": 1}}, indent=2))
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(data: dict):
    DATA_DIR.mkdir(exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _today() -> str:
    return date.today().isoformat()

def _week() -> str:
    d = date.today()
    return f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"

def _now_ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

def _default_user(uid: str, username: str) -> dict:
    return {
        "id": uid, "username": username,
        "balance": 0, "lifetime": 0,
        "transactions": [],
        "inventory": {},
        "daily": {"last_claim": None, "streak": 0},
        "gacha": {"total_pulls": 0, "pity_sr": 0, "pity_ssr": 0, "lucky_charm": 0},
        "missions": {"daily": {}, "weekly": {}},
        "stats": {
            "games_played": 0, "games_won": 0, "games_survived": 0,
            "votes_cast": 0, "transfers_sent": 0, "gacha_pulls": 0,
        },
    }

def get_user(user_id: int, username: str = "") -> dict:
    data = _load()
    uid  = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = _default_user(uid, username)
        _save(data)
    elif username and data["users"][uid]["username"] != username:
        data["users"][uid]["username"] = username
        _save(data)
    return data["users"][uid]

def _save_user(user_id: int, user_data: dict):
    data = _load()
    data["users"][str(user_id)] = user_data
    _save(data)

def _add_balance(user: dict, amount: int, note: str) -> dict:
    """Add/subtract balance and log transaction. Mutates and returns user dict."""
    user["balance"] = max(0, user["balance"] + amount)
    if amount > 0:
        user["lifetime"] += amount
    user["transactions"].insert(0, {"amount": amount, "note": note, "ts": _now_ts()})
    user["transactions"] = user["transactions"][:30]
    return user

# ══════════════════════════════════════════════════════════════════════════════
# MISSIONS  — fixed: no nested user variable shadowing
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_missions(user: dict) -> dict:
    today = _today()
    week  = _week()
    if today not in user["missions"]["daily"]:
        user["missions"]["daily"][today] = {m["id"]: 0 for m in DAILY_MISSIONS}
        keys = sorted(user["missions"]["daily"].keys())
        for old in keys[:-7]:
            del user["missions"]["daily"][old]
    if week not in user["missions"]["weekly"]:
        user["missions"]["weekly"][week] = {m["id"]: 0 for m in WEEKLY_MISSIONS}
        keys = sorted(user["missions"]["weekly"].keys())
        for old in keys[:-4]:
            del user["missions"]["weekly"][old]
    return user

def _progress_mission(user: dict, mission_type: str, amount: int = 1) -> dict:
    """
    Increment progress for all missions matching type.
    Fixed: no nested function, no variable shadowing.
    """
    user  = _ensure_missions(user)
    today = _today()
    week  = _week()

    # Daily missions
    for m in DAILY_MISSIONS:
        if m["type"] != mission_type:
            continue
        current = user["missions"]["daily"][today].get(m["id"], 0)
        if current >= m["target"]:
            continue
        new_val = min(current + amount, m["target"])
        user["missions"]["daily"][today][m["id"]] = new_val
        if new_val >= m["target"]:
            user = _add_balance(user, m["reward"], f"Misi harian selesai: {m['name']}")

    # Weekly missions
    for m in WEEKLY_MISSIONS:
        if m["type"] != mission_type:
            continue
        current = user["missions"]["weekly"][week].get(m["id"], 0)
        if current >= m["target"]:
            continue
        new_val = min(current + amount, m["target"])
        user["missions"]["weekly"][week][m["id"]] = new_val
        if new_val >= m["target"]:
            user = _add_balance(user, m["reward"], f"Misi mingguan selesai: {m['name']}")

    return user

# ══════════════════════════════════════════════════════════════════════════════
# DAILY
# ══════════════════════════════════════════════════════════════════════════════

def claim_daily(user_id: int, username: str) -> dict:
    user  = get_user(user_id, username)
    today = _today()
    last  = user["daily"]["last_claim"]

    if last == today:
        now      = datetime.utcnow()
        midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
        diff     = midnight - now
        hrs      = int(diff.total_seconds()) // 3600
        mins     = (int(diff.total_seconds()) % 3600) // 60
        return {"success": False, "next_in": f"{hrs}j {mins}m", "streak": user["daily"]["streak"]}

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    streak    = min(user["daily"]["streak"] + 1, DAILY_STREAK_MAX) if last == yesterday else 1
    reward    = DAILY_BASE + (streak - 1) * DAILY_STREAK_BONUS

    user["daily"]["last_claim"] = today
    user["daily"]["streak"]     = streak
    user = _add_balance(user, reward, f"Daily login (streak {streak})")
    user = _progress_mission(user, "daily", 1)

    _save_user(user_id, user)
    return {"success": True, "reward": reward, "streak": streak}

# ══════════════════════════════════════════════════════════════════════════════
# MISSIONS INFO
# ══════════════════════════════════════════════════════════════════════════════

def get_missions(user_id: int, username: str = "") -> dict:
    user  = get_user(user_id, username)
    user  = _ensure_missions(user)
    today = _today()
    week  = _week()

    daily_list = []
    for m in DAILY_MISSIONS:
        prog = user["missions"]["daily"][today].get(m["id"], 0)
        daily_list.append({**m, "progress": prog, "done": prog >= m["target"]})

    weekly_list = []
    for m in WEEKLY_MISSIONS:
        prog = user["missions"]["weekly"][week].get(m["id"], 0)
        weekly_list.append({**m, "progress": prog, "done": prog >= m["target"]})

    return {"daily": daily_list, "weekly": weekly_list, "balance": user["balance"]}

# ══════════════════════════════════════════════════════════════════════════════
# GACHA
# ══════════════════════════════════════════════════════════════════════════════

def _single_pull(user: dict) -> tuple:
    """Do one pull. Returns (updated_user, result_dict)."""
    g = user["gacha"]
    g["total_pulls"]         += 1
    g["pity_sr"]             += 1
    g["pity_ssr"]            += 1
    user["stats"]["gacha_pulls"] += 1

    force_ssr = g["pity_ssr"] >= GACHA_SSR_PITY
    force_sr  = g["pity_sr"]  >= GACHA_PITY_LIMIT

    if force_ssr:
        pool = [e for e in GACHA_POOL if e["rarity"] == "SSR"]
    elif force_sr:
        pool = [e for e in GACHA_POOL if e["rarity"] in ("SR", "SSR")]
    else:
        lucky_boost = 20 if g.get("lucky_charm", 0) > 0 else 0
        if g.get("lucky_charm", 0) > 0:
            g["lucky_charm"] -= 1
        pool = []
        for e in GACHA_POOL:
            w = e["weight"] + lucky_boost if e["rarity"] == "SSR" else e["weight"]
            pool.append({**e, "weight": w})

    weights = [e["weight"] for e in pool]
    chosen  = random.choices(pool, weights=weights, k=1)[0]

    if chosen["rarity"] in ("SR", "SSR"):
        g["pity_sr"] = 0
    if chosen["rarity"] == "SSR":
        g["pity_ssr"] = 0

    if chosen["type"] == "coins":
        user = _add_balance(user, chosen["amount"], f"Gacha: {chosen['label']}")
        result = {**chosen, "display": chosen["label"]}
    else:
        item_id = chosen["item"]
        user["inventory"][item_id] = user["inventory"].get(item_id, 0) + chosen["amount"]
        result = {**chosen, "display": SHOP_ITEMS[item_id]["name"]}

    user = _progress_mission(user, "gacha", 1)
    return user, result

def gacha_pull(user_id: int, username: str, count: int = 1, use_ticket: bool = False) -> dict:
    user = get_user(user_id, username)

    if use_ticket:
        tickets = user["inventory"].get("gacha_ticket", 0)
        if tickets < count:
            return {"success": False, "error": f"Tiket tidak cukup! Kamu punya {tickets} tiket."}
        user["inventory"]["gacha_ticket"] = tickets - count
    else:
        cost = GACHA_PULL_COST * count
        if user["balance"] < cost:
            return {"success": False, "error": f"WowoCash tidak cukup! Butuh {cost:,}, punya {user['balance']:,}."}
        user = _add_balance(user, -cost, f"Gacha x{count}")

    results = []
    for _ in range(count):
        user, res = _single_pull(user)
        results.append(res)

    _save_user(user_id, user)
    return {
        "success":     True,
        "results":     results,
        "new_balance": user["balance"],
        "pity_sr":     user["gacha"]["pity_sr"],
        "pity_ssr":    user["gacha"]["pity_ssr"],
    }

# ══════════════════════════════════════════════════════════════════════════════
# TRANSFER  — renamed from 'transfer' to avoid shadowing issues
# ══════════════════════════════════════════════════════════════════════════════

def send_transfer(sender_id: int, sender_name: str,
                  receiver_id: int, receiver_name: str,
                  amount: int) -> dict:
    if sender_id == receiver_id:
        return {"success": False, "error": "Tidak bisa transfer ke diri sendiri!"}
    if amount < 10:
        return {"success": False, "error": "Minimum transfer adalah 10 WowoCash."}

    sender   = get_user(sender_id, sender_name)
    receiver = get_user(receiver_id, receiver_name)

    fee       = max(1, int(amount * TRANSFER_FEE_PCT))
    total_out = amount + fee

    if sender["balance"] < total_out:
        return {"success": False, "error": f"WowoCash tidak cukup! Butuh {total_out:,} (termasuk fee {fee:,})."}

    sender   = _add_balance(sender,   -total_out, f"Transfer ke {receiver_name} (fee {fee})")
    receiver = _add_balance(receiver,  amount,     f"Diterima dari {sender_name}")

    sender["stats"]["transfers_sent"] += 1
    sender = _progress_mission(sender, "transfer", 1)

    _save_user(sender_id,   sender)
    _save_user(receiver_id, receiver)

    return {
        "success":          True,
        "amount":           amount,
        "fee":              fee,
        "sender_balance":   sender["balance"],
        "receiver_balance": receiver["balance"],
    }

# ══════════════════════════════════════════════════════════════════════════════
# SHOP
# ══════════════════════════════════════════════════════════════════════════════

def buy_item(user_id: int, username: str, item_id: str, quantity: int = 1) -> dict:
    if item_id not in SHOP_ITEMS:
        return {"success": False, "error": "Item tidak ditemukan!"}

    item    = SHOP_ITEMS[item_id]
    user    = get_user(user_id, username)
    current = user["inventory"].get(item_id, 0)

    if current + quantity > item["max_stack"]:
        space = item["max_stack"] - current
        return {"success": False, "error": f"Maks stack {item['max_stack']}! Kamu hanya bisa beli {space} lagi."}

    total_cost = item["price"] * quantity
    if user["balance"] < total_cost:
        return {"success": False, "error": f"WowoCash tidak cukup! Butuh {total_cost:,}, punya {user['balance']:,}."}

    user = _add_balance(user, -total_cost, f"Beli {item['name']} x{quantity}")
    user["inventory"][item_id] = current + quantity
    _save_user(user_id, user)

    return {"success": True, "item": item, "quantity": quantity, "cost": total_cost, "new_balance": user["balance"]}

def get_inventory(user_id: int, username: str = "") -> dict:
    user = get_user(user_id, username)
    inv  = [
        {**SHOP_ITEMS[iid], "count": cnt}
        for iid, cnt in user["inventory"].items()
        if iid in SHOP_ITEMS
    ]
    return {"items": inv, "balance": user["balance"]}

# ══════════════════════════════════════════════════════════════════════════════
# LEADERBOARD & PROFILE
# ══════════════════════════════════════════════════════════════════════════════

def get_leaderboard(top: int = 10) -> list:
    data  = _load()
    users = sorted(data["users"].values(), key=lambda u: u["balance"], reverse=True)
    return [
        {"rank": i + 1, "username": u["username"], "balance": u["balance"], "lifetime": u["lifetime"]}
        for i, u in enumerate(users[:top])
    ]

def get_profile(user_id: int, username: str = "") -> dict:
    user  = get_user(user_id, username)
    user  = _ensure_missions(user)
    today = _today()
    week  = _week()

    daily_done  = sum(1 for m in DAILY_MISSIONS
                      if user["missions"]["daily"].get(today, {}).get(m["id"], 0) >= m["target"])
    weekly_done = sum(1 for m in WEEKLY_MISSIONS
                      if user["missions"]["weekly"].get(week, {}).get(m["id"], 0) >= m["target"])

    badges = []
    if user["inventory"].get("vip_badge", 0):
        badges.append("⭐ VIP")
    if user["stats"]["games_won"] >= 10:
        badges.append("🏆 Veteran")
    if user["stats"]["gacha_pulls"] >= 50:
        badges.append("🎰 Penjudi")
    if user["daily"]["streak"] >= 7:
        badges.append("🔥 Streak 7")

    return {
        **user,
        "daily_done":            daily_done,
        "weekly_done":           weekly_done,
        "badges":                badges,
        "missions_total_daily":  len(DAILY_MISSIONS),
        "missions_total_weekly": len(WEEKLY_MISSIONS),
    }

# ══════════════════════════════════════════════════════════════════════════════
# WEREWOLF GAME REWARDS
# ══════════════════════════════════════════════════════════════════════════════

def award_game_end(players_result: list) -> list:
    awards = []
    for pr in players_result:
        uid   = pr["user_id"]
        uname = pr["username"]
        user  = get_user(uid, uname)
        total = 0
        breakdown = []

        if pr.get("is_jester_win"):
            total += WW_REWARDS["jester_win"]
            breakdown.append(f"🃏 Jester win +{WW_REWARDS['jester_win']}")
        elif pr.get("won"):
            total += WW_REWARDS["win"]
            breakdown.append(f"🏆 Menang +{WW_REWARDS['win']}")
        else:
            total += WW_REWARDS["lose"]
            breakdown.append(f"🎮 Partisipasi +{WW_REWARDS['lose']}")

        if pr.get("survived") and not pr.get("is_jester_win"):
            total += WW_REWARDS["survive"]
            breakdown.append(f"💪 Survive +{WW_REWARDS['survive']}")

        if pr.get("is_first_blood"):
            total += WW_REWARDS["first_blood"]
            breakdown.append(f"🩸 First Blood +{WW_REWARDS['first_blood']}")

        user = _add_balance(user, total, "Game reward")
        user["stats"]["games_played"] += 1
        if pr.get("won") or pr.get("is_jester_win"):
            user["stats"]["games_won"] += 1
        if pr.get("survived"):
            user["stats"]["games_survived"] += 1

        user = _progress_mission(user, "play", 1)
        if pr.get("won") or pr.get("is_jester_win"):
            user = _progress_mission(user, "win", 1)
        if pr.get("survived"):
            user = _progress_mission(user, "survive", 1)

        _save_user(uid, user)
        awards.append({
            "user_id": uid, "username": uname,
            "awarded": total, "breakdown": breakdown, "balance": user["balance"],
        })
    return awards

def progress_vote(user_id: int, username: str):
    user = get_user(user_id, username)
    user["stats"]["votes_cast"] += 1
    user = _progress_mission(user, "vote", 1)
    _save_user(user_id, user)

# ══════════════════════════════════════════════════════════════════════════════
# COOLDOWN HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_cooldown_secs(user: dict, key: str) -> int:
    """Returns remaining cooldown in seconds, 0 if ready."""
    cd = user.get("cooldowns", {}).get(key)
    if not cd:
        return 0
    from datetime import datetime
    last = datetime.fromisoformat(cd)
    now  = datetime.utcnow()
    limits = {"work": COOLDOWN_WORK, "rob": COOLDOWN_ROB, "hourly": COOLDOWN_HOURLY}
    limit  = limits.get(key, 3600)
    diff   = (now - last).total_seconds()
    return max(0, int(limit - diff))

def _set_cooldown(user: dict, key: str) -> dict:
    if "cooldowns" not in user:
        user["cooldowns"] = {}
    user["cooldowns"][key] = datetime.utcnow().isoformat()
    return user

def fmt_cooldown(secs: int) -> str:
    if secs <= 0:
        return "Siap!"
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if h:
        return f"{h}j {m}m"
    if m:
        return f"{m}m {s}d"
    return f"{s}d"

# ══════════════════════════════════════════════════════════════════════════════
# WORK
# ══════════════════════════════════════════════════════════════════════════════

def do_work(user_id: int, username: str) -> dict:
    user = get_user(user_id, username)
    cd   = _get_cooldown_secs(user, "work")
    if cd > 0:
        return {"success": False, "cooldown": cd, "error": f"Kamu lelah! Istirahat dulu **{fmt_cooldown(cd)}**."}

    job    = random.choice(WORK_JOBS)
    earned = random.randint(job["min"], job["max"])
    # Bonus: streak multiplier
    streak = user["daily"].get("streak", 1)
    bonus  = int(earned * min(streak, 7) * 0.05)
    total  = earned + bonus

    user = _set_cooldown(user, "work")
    user = _add_balance(user, total, f"Kerja sebagai {job['name']}")
    user = _progress_mission(user, "work", 1)
    _save_user(user_id, user)

    return {
        "success": True,
        "job":     job,
        "earned":  earned,
        "bonus":   bonus,
        "total":   total,
        "balance": user["balance"],
    }

# ══════════════════════════════════════════════════════════════════════════════
# HOURLY
# ══════════════════════════════════════════════════════════════════════════════

def claim_hourly(user_id: int, username: str) -> dict:
    user = get_user(user_id, username)
    cd   = _get_cooldown_secs(user, "hourly")
    if cd > 0:
        return {"success": False, "cooldown": cd, "error": f"Tunggu **{fmt_cooldown(cd)}** lagi."}

    streak = user["daily"].get("streak", 1)
    base   = 30
    bonus  = min(streak, 7) * 5
    total  = base + bonus

    user = _set_cooldown(user, "hourly")
    user = _add_balance(user, total, "Hourly reward")
    _save_user(user_id, user)
    return {"success": True, "total": total, "balance": user["balance"], "streak_bonus": bonus}

# ══════════════════════════════════════════════════════════════════════════════
# ROB
# ══════════════════════════════════════════════════════════════════════════════

def do_rob(robber_id: int, robber_name: str, victim_id: int, victim_name: str) -> dict:
    if robber_id == victim_id:
        return {"success": False, "error": "Tidak bisa merampok diri sendiri!"}

    robber = get_user(robber_id, robber_name)
    victim = get_user(victim_id, victim_name)

    cd = _get_cooldown_secs(robber, "rob")
    if cd > 0:
        return {"success": False, "cooldown": cd, "error": f"Polisi masih mengejarmu! Tunggu **{fmt_cooldown(cd)}**."}

    if victim["balance"] < 50:
        return {"success": False, "error": f"**{victim_name}** tidak punya cukup uang untuk dirampok (min. 50 💰)."}

    # 45% success chance
    success = random.random() < 0.45
    robber  = _set_cooldown(robber, "rob")

    if success:
        steal = random.randint(
            min(50, victim["balance"] // 4),
            min(300, victim["balance"] // 3),
        )
        robber = _add_balance(robber, steal,  f"Merampok {victim_name}")
        victim = _add_balance(victim, -steal, f"Dirampok oleh {robber_name}")
        robber = _progress_mission(robber, "rob", 1)
        _save_user(robber_id, robber)
        _save_user(victim_id, victim)
        return {"success": True, "robbed": True, "amount": steal,
                "robber_balance": robber["balance"], "victim_balance": victim["balance"]}
    else:
        # Caught — pay fine
        fine = random.randint(30, 100)
        robber = _add_balance(robber, -fine, f"Ketahuan merampok {victim_name} (denda)")
        _save_user(robber_id, robber)
        return {"success": True, "robbed": False, "fine": fine, "robber_balance": robber["balance"]}

# ══════════════════════════════════════════════════════════════════════════════
# CASINO GAMES
# ══════════════════════════════════════════════════════════════════════════════

MIN_BET = 10
MAX_BET = 5000

def _validate_bet(user: dict, bet: int) -> str | None:
    if bet < MIN_BET:
        return f"Minimum bet adalah {MIN_BET:,} 💰."
    if bet > MAX_BET:
        return f"Maximum bet adalah {MAX_BET:,} 💰."
    if user["balance"] < bet:
        return f"WowoCash tidak cukup! Kamu punya {user['balance']:,} 💰."
    return None

# ── Coin Flip ──────────────────────────────────────────────────────────────────

def casino_coinflip(user_id: int, username: str, bet: int, choice: str) -> dict:
    """choice: 'heads' or 'tails'"""
    user = get_user(user_id, username)
    err  = _validate_bet(user, bet)
    if err:
        return {"success": False, "error": err}

    result  = random.choice(["heads", "tails"])
    won     = result == choice
    delta   = bet if won else -bet
    user    = _add_balance(user, delta, f"Coin flip: {'menang' if won else 'kalah'} {bet:,}")
    user    = _progress_mission(user, "casino", 1)
    _save_user(user_id, user)

    return {
        "success": True, "won": won,
        "result": result, "choice": choice,
        "delta": delta, "balance": user["balance"],
    }

# ── Dice Roll ─────────────────────────────────────────────────────────────────

def casino_dice(user_id: int, username: str, bet: int, guess: int) -> dict:
    """guess: 1-6"""
    user = get_user(user_id, username)
    err  = _validate_bet(user, bet)
    if err:
        return {"success": False, "error": err}
    if not 1 <= guess <= 6:
        return {"success": False, "error": "Tebak angka 1–6!"}

    roll = random.randint(1, 6)
    won  = roll == guess
    delta = bet * 5 if won else -bet
    user  = _add_balance(user, delta, f"Dice: {'menang' if won else 'kalah'} (roll {roll})")
    user  = _progress_mission(user, "casino", 1)
    _save_user(user_id, user)

    return {
        "success": True, "won": won,
        "roll": roll, "guess": guess,
        "delta": delta, "balance": user["balance"],
    }

# ── Slot Machine ──────────────────────────────────────────────────────────────

def casino_slots(user_id: int, username: str, bet: int) -> dict:
    user = get_user(user_id, username)
    err  = _validate_bet(user, bet)
    if err:
        return {"success": False, "error": err}

    reels  = random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=3)
    combo  = tuple(reels)
    mult   = SLOT_PAYOUTS.get(combo, 0)

    # Two cherry bonus
    if mult == 0 and reels.count("🍒") == 2:
        mult = 0.5

    winnings = int(bet * mult)
    delta    = winnings - bet
    note     = f"Slots {'win' if delta > 0 else 'lose'} x{mult}"
    user     = _add_balance(user, delta, note)
    user     = _progress_mission(user, "casino", 1)
    _save_user(user_id, user)

    return {
        "success": True,
        "reels": reels, "combo": combo,
        "multiplier": mult, "winnings": winnings,
        "delta": delta, "balance": user["balance"],
        "won": delta > 0,
    }

# ── Number Guess ──────────────────────────────────────────────────────────────

def casino_number(user_id: int, username: str, bet: int, guess: int, max_num: int = 10) -> dict:
    """Guess number 1-max_num. Payout = max_num * 0.9x bet."""
    user = get_user(user_id, username)
    err  = _validate_bet(user, bet)
    if err:
        return {"success": False, "error": err}
    if not 1 <= guess <= max_num:
        return {"success": False, "error": f"Tebak angka 1–{max_num}!"}

    number = random.randint(1, max_num)
    won    = number == guess
    mult   = int(max_num * 0.9) if won else 0
    delta  = bet * mult - bet if won else -bet
    user   = _add_balance(user, delta, f"Number guess {'win' if won else 'lose'}")
    user   = _progress_mission(user, "casino", 1)
    _save_user(user_id, user)

    return {
        "success": True, "won": won,
        "number": number, "guess": guess,
        "multiplier": mult, "delta": delta,
        "balance": user["balance"],
    }

# ── Blackjack ─────────────────────────────────────────────────────────────────

_BJ_DECK = (
    [2,3,4,5,6,7,8,9,10,10,10,10,11] * 4
)
_BJ_SUITS = ["♠","♥","♦","♣"]
_BJ_RANKS = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]

def _bj_hand_value(hand: list) -> int:
    total = sum(hand)
    aces  = hand.count(11)
    while total > 21 and aces:
        total -= 10
        aces  -= 1
    return total

def blackjack_deal(user_id: int, username: str, bet: int) -> dict:
    """Start a blackjack hand. Returns state to be stored by cog."""
    user = get_user(user_id, username)
    err  = _validate_bet(user, bet)
    if err:
        return {"success": False, "error": err}

    deck   = _BJ_DECK.copy()
    random.shuffle(deck)
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]

    # Deduct bet immediately
    user = _add_balance(user, -bet, f"Blackjack bet {bet:,}")
    _save_user(user_id, user)

    state = {
        "player": player, "dealer": dealer,
        "deck": deck, "bet": bet,
        "done": False, "user_id": user_id, "username": username,
    }

    # Natural blackjack?
    if _bj_hand_value(player) == 21:
        return blackjack_resolve(state, "stand")

    return {"success": True, "state": state, "balance": user["balance"]}

def blackjack_resolve(state: dict, action: str) -> dict:
    """action: 'hit' or 'stand'"""
    player  = state["player"]
    dealer  = state["dealer"]
    deck    = state["deck"]
    bet     = state["bet"]
    uid     = state["user_id"]
    uname   = state["username"]

    if action == "hit":
        player.append(deck.pop())
        state["player"] = player
        pval = _bj_hand_value(player)
        if pval > 21:
            # Bust — money already deducted
            user = get_user(uid, uname)
            user = _progress_mission(user, "casino", 1)
            _save_user(uid, user)
            return {
                "success": True, "done": True,
                "result": "bust", "player": player, "dealer": dealer,
                "player_val": pval, "dealer_val": _bj_hand_value(dealer),
                "delta": -bet, "balance": user["balance"],
            }
        if pval == 21:
            action = "stand"  # auto stand on 21
        else:
            return {"success": True, "done": False, "state": state,
                    "player": player, "dealer": dealer,
                    "player_val": pval, "dealer_val": dealer[0],
                    "balance": get_user(uid, uname)["balance"]}

    # Stand — dealer plays
    dval = _bj_hand_value(dealer)
    while dval < 17:
        dealer.append(deck.pop())
        dval = _bj_hand_value(dealer)

    pval = _bj_hand_value(player)
    user = get_user(uid, uname)
    user = _progress_mission(user, "casino", 1)

    if dval > 21 or pval > dval:
        result = "win"
        mult   = 1.5 if pval == 21 and len(player) == 2 else 1
        delta  = int(bet * (1 + mult))
        user   = _add_balance(user, delta, f"Blackjack win x{1+mult}")
    elif pval == dval:
        result = "push"
        delta  = bet
        user   = _add_balance(user, delta, "Blackjack push (refund)")
    else:
        result = "lose"
        delta  = -bet  # already deducted, just for display

    _save_user(uid, user)
    return {
        "success": True, "done": True,
        "result": result, "player": player, "dealer": dealer,
        "player_val": pval, "dealer_val": dval,
        "delta": delta if result != "lose" else -bet,
        "balance": user["balance"],
    }