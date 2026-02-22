"""
WowoCash Casino Cog
Commands:
  /wowo_gacha       — Gacha dengan animasi rolling
  /wowo_work        — Kerja untuk dapat uang (cooldown 1 jam)
  /wowo_hourly      — Reward per jam
  /wowo_rob         — Coba rampok user lain (45% sukses)
  /wowo_coinflip    — Coin flip bet
  /wowo_dice        — Tebak dadu (1-6, payout 5x)
  /wowo_slots       — Slot machine
  /wowo_number      — Tebak angka (1-10, payout 9x)
  /wowo_blackjack   — Blackjack vs dealer
"""

import asyncio
import random
import discord
from discord.ext import commands
from discord import app_commands
from economy.wowocash import (
    claim_daily, get_profile, get_missions,
    gacha_pull, send_transfer, buy_item, get_inventory,
    get_leaderboard,
    do_work, claim_hourly, do_rob,
    casino_coinflip, casino_dice, casino_slots, casino_number,
    blackjack_deal, blackjack_resolve,
    SHOP_ITEMS, GACHA_PULL_COST, RARITY_EMOJI, SLOT_SYMBOLS, SLOT_WEIGHTS,
    CURRENCY_ICON, DAILY_BASE, DAILY_STREAK_BONUS, DAILY_STREAK_MAX,
    fmt_cooldown, MIN_BET, MAX_BET,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def cash(n: int) -> str:
    return f"💰 **{n:,}**"

def wowo_color():
    return discord.Color.from_rgb(255, 193, 7)

def err_embed(msg: str) -> discord.Embed:
    return discord.Embed(description=f"❌ {msg}", color=discord.Color.red())

def result_color(won: bool) -> discord.Color:
    return discord.Color.green() if won else discord.Color.red()

# ══════════════════════════════════════════════════════════════════════════════
# ANIMATED GACHA VIEW
# ══════════════════════════════════════════════════════════════════════════════

GACHA_ROLL_FRAMES = [
    "⚪ ⚪ ⚪ ⚪ ⚪",
    "🔵 ⚪ ⚪ ⚪ ⚪",
    "🔵 🔵 ⚪ ⚪ ⚪",
    "🟣 🔵 🔵 ⚪ ⚪",
    "🟣 🟣 🔵 🔵 ⚪",
    "🌟 🟣 🟣 🔵 🔵",
]

RARITY_COLORS = {
    "N":   discord.Color.light_grey(),
    "R":   discord.Color.blue(),
    "SR":  discord.Color.purple(),
    "SSR": discord.Color.gold(),
}

RARITY_BANNER = {
    "N":   "```\n[ N  ] Normal\n```",
    "R":   "```ansi\n\u001b[0;34m[ R  ] Rare\u001b[0m\n```",
    "SR":  "```ansi\n\u001b[0;35m[ SR ] Super Rare ✨\u001b[0m\n```",
    "SSR": "```ansi\n\u001b[0;33m[ SSR] ULTRA RARE 🌟🌟🌟\u001b[0m\n```",
}

class AnimatedGachaView(discord.ui.View):
    def __init__(self, cog: "Casino", user: discord.Member, count: int):
        super().__init__(timeout=60)
        self.cog   = cog
        self.user  = user
        self.count = count

    @discord.ui.button(label="🔄 Pull Lagi", style=discord.ButtonStyle.primary,   custom_id="ag_repull")
    async def repull(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Ini bukan gachamu!", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog._run_animated_gacha(interaction, self.user, self.count)

    @discord.ui.button(label="🎟️ Pakai Tiket", style=discord.ButtonStyle.secondary, custom_id="ag_ticket")
    async def ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Ini bukan gachamu!", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog._run_animated_gacha(interaction, self.user, 1, use_ticket=True)

# ══════════════════════════════════════════════════════════════════════════════
# BLACKJACK VIEW
# ══════════════════════════════════════════════════════════════════════════════

_CARD_EMOJI = {
    2:"2",3:"3",4:"4",5:"5",6:"6",7:"7",8:"8",9:"9",
    10:"10",11:"A",
}

def _hand_str(hand: list, hide_second: bool = False) -> str:
    cards = []
    for i, v in enumerate(hand):
        if i == 1 and hide_second:
            cards.append("🂠")
        else:
            label = _CARD_EMOJI.get(v, str(v))
            cards.append(f"`{label}`")
    return " ".join(cards)

def _bj_embed(state: dict, result_data: dict | None = None) -> discord.Embed:
    from economy.wowocash import _bj_hand_value
    player = state["player"]
    dealer = state["dealer"]
    pval   = _bj_hand_value(player)
    bet    = state["bet"]

    if result_data:
        dval  = result_data["dealer_val"]
        res   = result_data["result"]
        title_map = {"win": "✅ Menang!", "lose": "❌ Kalah!", "bust": "💥 Bust!", "push": "🤝 Seri!"}
        color_map = {"win": discord.Color.green(), "lose": discord.Color.red(),
                     "bust": discord.Color.red(), "push": discord.Color.greyple()}
        delta = result_data["delta"]
        sign  = "+" if delta > 0 else ""
        embed = discord.Embed(
            title       = f"🃏 Blackjack — {title_map.get(res, res)}",
            description = f"{'Jackpot! ' if res=='win' and pval==21 and len(player)==2 else ''}Saldo: {cash(result_data['balance'])}",
            color       = color_map.get(res, discord.Color.grey()),
        )
        embed.add_field(name=f"👤 Kamu ({pval})",  value=_hand_str(player),  inline=True)
        embed.add_field(name=f"🤖 Dealer ({dval})", value=_hand_str(dealer), inline=True)
        embed.add_field(name="Hasil", value=f"{sign}{delta:,} 💰", inline=False)
    else:
        dval_show = dealer[0]
        embed = discord.Embed(
            title       = "🃏 Blackjack",
            description = f"Bet: {cash(bet)}",
            color       = wowo_color(),
        )
        embed.add_field(name=f"👤 Kamu ({pval})",       value=_hand_str(player),             inline=True)
        embed.add_field(name="🤖 Dealer (?)",           value=_hand_str(dealer, hide_second=True), inline=True)
        embed.set_footer(text="Hit = ambil kartu • Stand = berhenti")
    return embed

class BlackjackView(discord.ui.View):
    def __init__(self, state: dict, cog: "Casino", user: discord.Member):
        super().__init__(timeout=60)
        self.state = state
        self.cog   = cog
        self.user  = user
        self.done  = False

    @discord.ui.button(label="🃏 Hit", style=discord.ButtonStyle.primary,   custom_id="bj_hit")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Ini bukan mejamu!", ephemeral=True)
            return
        if self.done:
            return
        result = blackjack_resolve(self.state, "hit")
        if result["done"]:
            self.done = True
            for c in self.children: c.disabled = True
            await interaction.response.edit_message(embed=_bj_embed(self.state, result), view=self)
        else:
            self.state = result["state"]
            await interaction.response.edit_message(embed=_bj_embed(self.state), view=self)

    @discord.ui.button(label="✋ Stand", style=discord.ButtonStyle.secondary, custom_id="bj_stand")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Ini bukan mejamu!", ephemeral=True)
            return
        if self.done:
            return
        self.done = True
        for c in self.children: c.disabled = True
        result = blackjack_resolve(self.state, "stand")
        await interaction.response.edit_message(embed=_bj_embed(self.state, result), view=self)

    async def on_timeout(self):
        # Auto-stand on timeout
        for c in self.children: c.disabled = True

# ══════════════════════════════════════════════════════════════════════════════
# SLOT ANIMATION FRAMES
# ══════════════════════════════════════════════════════════════════════════════

async def _animate_slots(message: discord.Message, final_reels: list, bet: int, delta: int, balance: int):
    """Edit message through rolling frames then reveal final result."""
    spinning = ["🎰", "🎰", "🎰"]

    # Rolling phase — 4 frames
    for frame_i in range(4):
        frame_reels = [
            random.choice(SLOT_SYMBOLS) if frame_i < 3 or i > frame_i - 2 else final_reels[i]
            for i in range(3)
        ]
        disp   = " | ".join(frame_reels)
        embed  = discord.Embed(
            title       = "🎰 Slot Machine — Spinning...",
            description = f"```\n[ {disp} ]\n```",
            color       = wowo_color(),
        )
        embed.set_footer(text=f"Bet: {bet:,} 💰")
        await message.edit(embed=embed)
        await asyncio.sleep(0.6)

    # Reveal reels one by one
    revealed = ["❓", "❓", "❓"]
    for i in range(3):
        revealed[i] = final_reels[i]
        disp  = " | ".join(revealed)
        color = discord.Color.green() if delta > 0 else discord.Color.red() if i == 2 else wowo_color()
        embed = discord.Embed(
            title       = "🎰 Slot Machine",
            description = f"```\n[ {disp} ]\n```",
            color       = color,
        )
        embed.set_footer(text=f"Bet: {bet:,} 💰")
        await message.edit(embed=embed)
        await asyncio.sleep(0.5)

    # Final result
    sign  = "+" if delta > 0 else ""
    title = "🎰 JACKPOT! 🎉" if delta > bet * 5 else ("🎰 Menang!" if delta > 0 else "🎰 Kalah...")
    embed = discord.Embed(
        title       = title,
        description = f"```\n[ {' | '.join(final_reels)} ]\n```",
        color       = discord.Color.green() if delta > 0 else discord.Color.red(),
    )
    embed.add_field(name="Hasil",  value=f"{sign}{delta:,} 💰", inline=True)
    embed.add_field(name="Saldo",  value=f"{balance:,} 💰",     inline=True)
    await message.edit(embed=embed)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN COG
# ══════════════════════════════════════════════════════════════════════════════

class Casino(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ══════════════════════════════════════════════════════════════════════════
    # ANIMATED GACHA
    # ══════════════════════════════════════════════════════════════════════════

    @app_commands.command(name="wowo_gacha", description="🎰 Pull gacha dengan animasi!")
    @app_commands.describe(count="Jumlah pull")
    @app_commands.choices(count=[
        app_commands.Choice(name=f"1x  — {GACHA_PULL_COST:,} 💰",      value=1),
        app_commands.Choice(name=f"10x — {GACHA_PULL_COST * 10:,} 💰",  value=10),
    ])
    async def gacha(self, interaction: discord.Interaction, count: int = 1):
        await interaction.response.defer()
        await self._run_animated_gacha(interaction, interaction.user, count)

    async def _run_animated_gacha(self, interaction: discord.Interaction,
                                   user: discord.Member, count: int,
                                   use_ticket: bool = False):
        # Phase 1: Loading embed
        loading = discord.Embed(
            title       = "🎰 Mempersiapkan Gacha...",
            description = GACHA_ROLL_FRAMES[0],
            color       = discord.Color.light_grey(),
        )
        msg = await interaction.followup.send(embed=loading)

        # Phase 2: Roll animation (cycle through frames)
        for frame in GACHA_ROLL_FRAMES[1:]:
            await asyncio.sleep(0.4)
            loading.description = frame
            await msg.edit(embed=loading)

        await asyncio.sleep(0.3)

        # Phase 3: Actually pull
        result = gacha_pull(user.id, user.display_name, count, use_ticket=use_ticket)

        if not result["success"]:
            await msg.edit(embed=err_embed(result["error"]))
            return

        results = result["results"]

        if count == 1:
            # Single pull — dramatic reveal
            r     = results[0]
            color = RARITY_COLORS.get(r["rarity"], wowo_color())
            emoji = RARITY_EMOJI[r["rarity"]]

            # Suspense frame
            suspense = discord.Embed(
                title       = "✨ Membuka...",
                description = "```\n[ ? ? ? ]\n```",
                color       = color,
            )
            await msg.edit(embed=suspense)
            await asyncio.sleep(0.8)

            # Reveal
            embed = discord.Embed(
                title       = f"{emoji} {RARITY_BANNER.get(r['rarity'], r['rarity'])}",
                description = f"**{r['display']}**",
                color       = color,
            )
            embed.add_field(name="Saldo",   value=f"{result['new_balance']:,} 💰",   inline=True)
            embed.add_field(name="🔮 Pity", value=f"SR:{result['pity_sr']}/50  SSR:{result['pity_ssr']}/100", inline=True)

            # SSR — extra celebration
            if r["rarity"] == "SSR":
                embed.description = f"🌟🌟🌟 **{r['display']}** 🌟🌟🌟\n\n*ULTRA RARE GET!*"

            view = AnimatedGachaView(self, user, count)
            await msg.edit(embed=embed, view=view)

        else:
            # 10-pull — reveal one by one with delay
            lines         = []
            rarity_counts = {}

            reveal_embed = discord.Embed(
                title = "✨ 10x Pull — Revealing...",
                color = wowo_color(),
            )
            await msg.edit(embed=reveal_embed)
            await asyncio.sleep(0.3)

            for i, r in enumerate(results):
                emoji = RARITY_EMOJI[r["rarity"]]
                line  = f"{emoji} **[{r['rarity']}]** {r['display']}"
                lines.append(line)
                rarity_counts[r["rarity"]] = rarity_counts.get(r["rarity"], 0) + 1

                color = RARITY_COLORS.get(r["rarity"], wowo_color())
                reveal_embed = discord.Embed(
                    title       = f"✨ 10x Pull — {i+1}/10",
                    description = "\n".join(lines),
                    color       = color,
                )
                await msg.edit(embed=reveal_embed)
                # Longer pause for SR/SSR
                delay = 0.8 if r["rarity"] in ("SR", "SSR") else 0.25
                await asyncio.sleep(delay)

            # Final summary
            best_rarity = max(rarity_counts, key=lambda x: ["N","R","SR","SSR"].index(x))
            summary     = " · ".join(f"{RARITY_EMOJI[k]} {k}×{v}" for k, v in sorted(rarity_counts.items()))
            final_color = RARITY_COLORS.get(best_rarity, wowo_color())

            final_embed = discord.Embed(
                title       = "🎰 10x Pull — Selesai!",
                description = "\n".join(lines),
                color       = final_color,
            )
            final_embed.add_field(name="📊 Ringkasan", value=summary,                                inline=True)
            final_embed.add_field(name="Saldo",        value=f"{result['new_balance']:,} 💰",        inline=True)
            final_embed.add_field(name="🔮 Pity",      value=f"SR:{result['pity_sr']}/50  SSR:{result['pity_ssr']}/100", inline=False)

            view = AnimatedGachaView(self, user, count)
            await msg.edit(embed=final_embed, view=view)

    # ══════════════════════════════════════════════════════════════════════════
    # WORK
    # ══════════════════════════════════════════════════════════════════════════

    @app_commands.command(name="wowo_work", description="💼 Kerja untuk dapat WowoCash (cooldown 1 jam)")
    async def work(self, interaction: discord.Interaction):
        result = do_work(interaction.user.id, interaction.user.display_name)
        if not result["success"]:
            embed = discord.Embed(
                title       = "😴 Kamu Kelelahan!",
                description = result["error"],
                color       = discord.Color.orange(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        job   = result["job"]
        bonus = result["bonus"]
        embed = discord.Embed(
            title       = f"{job['emoji']} Kamu Bekerja sebagai {job['name']}!",
            color       = discord.Color.green(),
        )
        desc = f"Kamu mendapat {cash(result['earned'])}"
        if bonus > 0:
            desc += f" + {cash(bonus)} (streak bonus)"
        desc += f"\n\n**Total: {cash(result['total'])}** 🎉"
        embed.description = desc
        embed.add_field(name="💰 Saldo Sekarang", value=f"{result['balance']:,}", inline=True)
        embed.set_footer(text="Bisa kerja lagi dalam 1 jam")
        await interaction.response.send_message(embed=embed)

    # ══════════════════════════════════════════════════════════════════════════
    # HOURLY
    # ══════════════════════════════════════════════════════════════════════════

    @app_commands.command(name="wowo_hourly", description="⏰ Claim reward per jam")
    async def hourly(self, interaction: discord.Interaction):
        result = claim_hourly(interaction.user.id, interaction.user.display_name)
        if not result["success"]:
            embed = discord.Embed(
                title       = "⏰ Belum Waktunya!",
                description = result["error"],
                color       = discord.Color.orange(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title       = "⏰ Hourly Reward!",
            description = f"Kamu mendapat {cash(result['total'])}!",
            color       = discord.Color.green(),
        )
        if result["streak_bonus"] > 0:
            embed.add_field(name="🔥 Streak Bonus", value=f"+{result['streak_bonus']}", inline=True)
        embed.add_field(name="💰 Saldo", value=f"{result['balance']:,}", inline=True)
        embed.set_footer(text="Kembali lagi dalam 1 jam!")
        await interaction.response.send_message(embed=embed)

    # ══════════════════════════════════════════════════════════════════════════
    # ROB
    # ══════════════════════════════════════════════════════════════════════════

    @app_commands.command(name="wowo_rob", description="🦹 Coba rampok user lain! (45% sukses)")
    @app_commands.describe(target="User yang ingin dirampok")
    async def rob(self, interaction: discord.Interaction, target: discord.Member):
        result = do_rob(interaction.user.id, interaction.user.display_name,
                        target.id, target.display_name)
        if not result["success"]:
            await interaction.response.send_message(embed=err_embed(result["error"]), ephemeral=True)
            return

        if result["robbed"]:
            embed = discord.Embed(
                title       = "🦹 Berhasil Merampok!",
                description = f"Kamu berhasil mencuri {cash(result['amount'])} dari **{target.display_name}**!",
                color       = discord.Color.green(),
            )
            embed.add_field(name="💰 Saldo Kamu", value=f"{result['robber_balance']:,}", inline=True)
        else:
            embed = discord.Embed(
                title       = "🚔 Ketahuan!",
                description = f"Kamu gagal merampok dan kena denda {cash(result['fine'])}!",
                color       = discord.Color.red(),
            )
            embed.add_field(name="💰 Saldo Kamu", value=f"{result['robber_balance']:,}", inline=True)
        embed.set_footer(text="Bisa rob lagi dalam 2 jam")
        await interaction.response.send_message(embed=embed)

    # ══════════════════════════════════════════════════════════════════════════
    # COIN FLIP
    # ══════════════════════════════════════════════════════════════════════════

    @app_commands.command(name="wowo_coinflip", description="🪙 Coin flip — heads atau tails?")
    @app_commands.describe(bet="Jumlah bet", choice="Pilih heads atau tails")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Heads 🦅", value="heads"),
        app_commands.Choice(name="Tails 🌟", value="tails"),
    ])
    async def coinflip(self, interaction: discord.Interaction, bet: int, choice: str):
        await interaction.response.defer()

        # Animation
        frames = ["🪙", "🌀", "🪙", "🌀", "🪙"]
        embed  = discord.Embed(title="🪙 Melempar koin...", description="🌀 Spinning...", color=wowo_color())
        msg    = await interaction.followup.send(embed=embed)

        for f in frames:
            embed.description = f"{f} ..."
            await msg.edit(embed=embed)
            await asyncio.sleep(0.3)

        result = casino_coinflip(interaction.user.id, interaction.user.display_name, bet, choice)
        if not result["success"]:
            await msg.edit(embed=err_embed(result["error"]))
            return

        coin_emoji = "🦅 HEADS" if result["result"] == "heads" else "🌟 TAILS"
        sign       = "+" if result["delta"] > 0 else ""
        embed = discord.Embed(
            title       = f"🪙 {coin_emoji}!",
            description = f"Pilihanmu: **{choice.upper()}** {'✅' if result['won'] else '❌'}",
            color       = result_color(result["won"]),
        )
        embed.add_field(name="Hasil",  value=f"{sign}{result['delta']:,} 💰", inline=True)
        embed.add_field(name="Saldo",  value=f"{result['balance']:,} 💰",     inline=True)
        await msg.edit(embed=embed)

    # ══════════════════════════════════════════════════════════════════════════
    # DICE
    # ══════════════════════════════════════════════════════════════════════════

    @app_commands.command(name="wowo_dice", description="🎲 Tebak angka dadu 1-6 (payout 5x!)")
    @app_commands.describe(bet="Jumlah bet", guess="Tebakan angka 1-6")
    async def dice(self, interaction: discord.Interaction, bet: int, guess: int):
        await interaction.response.defer()

        dice_frames = ["⚀","⚁","⚂","⚃","⚄","⚅"]
        embed = discord.Embed(title="🎲 Melempar dadu...", description="🎲 ...", color=wowo_color())
        msg   = await interaction.followup.send(embed=embed)

        for _ in range(5):
            embed.description = f"{random.choice(dice_frames)} ..."
            await msg.edit(embed=embed)
            await asyncio.sleep(0.25)

        result = casino_dice(interaction.user.id, interaction.user.display_name, bet, guess)
        if not result["success"]:
            await msg.edit(embed=err_embed(result["error"]))
            return

        dice_face = ["⚀","⚁","⚂","⚃","⚄","⚅"][result["roll"] - 1]
        sign      = "+" if result["delta"] > 0 else ""
        embed = discord.Embed(
            title       = f"{dice_face} Dadu jatuh di angka **{result['roll']}**!",
            description = f"Tebakanmu: **{guess}** {'✅ TEPAT!' if result['won'] else '❌'}",
            color       = result_color(result["won"]),
        )
        embed.add_field(name="Hasil",  value=f"{sign}{result['delta']:,} 💰", inline=True)
        embed.add_field(name="Saldo",  value=f"{result['balance']:,} 💰",     inline=True)
        if result["won"]:
            embed.set_footer(text="🎉 Jackpot! Payout 5x!")
        await msg.edit(embed=embed)

    # ══════════════════════════════════════════════════════════════════════════
    # SLOT MACHINE
    # ══════════════════════════════════════════════════════════════════════════

    @app_commands.command(name="wowo_slots", description="🎰 Slot Machine! Match 3 untuk jackpot!")
    @app_commands.describe(bet="Jumlah bet")
    async def slots(self, interaction: discord.Interaction, bet: int):
        result = casino_slots(interaction.user.id, interaction.user.display_name, bet)
        if not result["success"]:
            await interaction.response.send_message(embed=err_embed(result["error"]), ephemeral=True)
            return

        # Start animation
        embed = discord.Embed(title="🎰 Slot Machine", description="```\n[ 🎰 | 🎰 | 🎰 ]\n```", color=wowo_color())
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        await _animate_slots(msg, result["reels"], bet, result["delta"], result["balance"])

    # ══════════════════════════════════════════════════════════════════════════
    # NUMBER GUESS
    # ══════════════════════════════════════════════════════════════════════════

    @app_commands.command(name="wowo_number", description="🔢 Tebak angka 1-10 (payout 9x!)")
    @app_commands.describe(bet="Jumlah bet", guess="Tebakan angka 1-10")
    async def number_guess(self, interaction: discord.Interaction, bet: int, guess: int):
        await interaction.response.defer()

        # Suspense animation
        embed = discord.Embed(title="🔢 Memilih angka...", description="🤔 ...", color=wowo_color())
        msg   = await interaction.followup.send(embed=embed)

        for _ in range(4):
            n = random.randint(1, 10)
            embed.description = f"**{n}** ..."
            await msg.edit(embed=embed)
            await asyncio.sleep(0.3)

        result = casino_number(interaction.user.id, interaction.user.display_name, bet, guess)
        if not result["success"]:
            await msg.edit(embed=err_embed(result["error"]))
            return

        sign  = "+" if result["delta"] > 0 else ""
        embed = discord.Embed(
            title       = f"🔢 Angkanya: **{result['number']}**!",
            description = f"Tebakanmu: **{guess}** {'✅ TEPAT!' if result['won'] else '❌'}",
            color       = result_color(result["won"]),
        )
        embed.add_field(name="Hasil",  value=f"{sign}{result['delta']:,} 💰", inline=True)
        embed.add_field(name="Saldo",  value=f"{result['balance']:,} 💰",     inline=True)
        if result["won"]:
            embed.set_footer(text=f"🎉 Jackpot! Payout {result['multiplier']}x!")
        await msg.edit(embed=embed)

    # ══════════════════════════════════════════════════════════════════════════
    # BLACKJACK
    # ══════════════════════════════════════════════════════════════════════════

    @app_commands.command(name="wowo_blackjack", description="🃏 Blackjack vs Dealer! (Blackjack = 1.5x)")
    @app_commands.describe(bet="Jumlah bet")
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        result = blackjack_deal(interaction.user.id, interaction.user.display_name, bet)
        if not result["success"]:
            await interaction.response.send_message(embed=err_embed(result["error"]), ephemeral=True)
            return

        # Natural blackjack or immediate result
        if result.get("done"):
            embed = _bj_embed({"player": result["player"], "dealer": result["dealer"], "bet": bet}, result)
            await interaction.response.send_message(embed=embed)
            return

        state = result["state"]
        embed = _bj_embed(state)
        view  = BlackjackView(state, self, interaction.user)
        await interaction.response.send_message(embed=embed, view=view)

    # ══════════════════════════════════════════════════════════════════════════
    # CASINO MENU
    # ══════════════════════════════════════════════════════════════════════════

    @app_commands.command(name="wowo_casino", description="🎰 Lihat semua game casino")
    async def casino_menu(self, interaction: discord.Interaction):
        profile = get_profile(interaction.user.id, interaction.user.display_name)
        embed   = discord.Embed(
            title       = "🎰 WowoCash Casino",
            description = f"Saldo kamu: {cash(profile['balance'])}",
            color       = wowo_color(),
        )
        games = [
            ("🪙 `/wowo_coinflip`",  f"Heads/Tails — bet, menang 2x (min {MIN_BET}, max {MAX_BET:,})"),
            ("🎲 `/wowo_dice`",      f"Tebak dadu 1-6 — menang 5x"),
            ("🎰 `/wowo_slots`",     f"Slot Machine — match 3, jackpot 🃏🃏🃏 = 50x!"),
            ("🔢 `/wowo_number`",    f"Tebak angka 1-10 — menang 9x"),
            ("🃏 `/wowo_blackjack`", f"Blackjack vs Dealer — BJ payout 1.5x"),
            ("🎰 `/wowo_gacha`",     f"Gacha pull — SSR drop animasi dramatis!"),
        ]
        for name, desc in games:
            embed.add_field(name=name, value=desc, inline=False)

        embed.add_field(
            name  = "━━━━━━━━━━━━━━━━━━━━━━",
            value = (
                "💼 `/wowo_work` — Kerja (1 jam cooldown)\n"
                "⏰ `/wowo_hourly` — Reward tiap jam\n"
                "🦹 `/wowo_rob` — Rampok user lain (2 jam cooldown)"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Min bet: {MIN_BET:,} 💰 | Max bet: {MAX_BET:,} 💰")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Casino(bot))