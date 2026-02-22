import discord
import asyncio
import random
import discord
from discord.ext import commands
from discord import app_commands
from economy.wowocash import (
    claim_daily, get_profile, get_missions,
    send_transfer, buy_item, get_inventory,
    get_leaderboard,
    SHOP_ITEMS,
    CURRENCY_ICON, DAILY_BASE, DAILY_STREAK_BONUS, DAILY_STREAK_MAX,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def cash(amount: int) -> str:
    return f"{CURRENCY_ICON} **{amount:,}**"

def wowo_color() -> discord.Color:
    return discord.Color.from_rgb(255, 193, 7)

def err_embed(msg: str) -> discord.Embed:
    return discord.Embed(description=f"❌ {msg}", color=discord.Color.red())

# ══════════════════════════════════════════════════════════════════════════════
# SHOP VIEW
# ══════════════════════════════════════════════════════════════════════════════

class ShopView(discord.ui.View):
    def __init__(self, cog: "WowoCash", user: discord.Member):
        super().__init__(timeout=120)
        self.cog      = cog
        self.user     = user
        self.category = "game"
        self._rebuild()

    def _rebuild(self):
        self.clear_items()

        cat_select = discord.ui.Select(
            placeholder="Pilih kategori...",
            options=[
                discord.SelectOption(label="⚔️ Game Items", value="game",     default=self.category == "game"),
                discord.SelectOption(label="🎰 Misc",       value="misc",     default=self.category == "misc"),
                discord.SelectOption(label="✨ Cosmetic",   value="cosmetic", default=self.category == "cosmetic"),
            ],
            custom_id="shop_cat",
            row=0,
        )
        cat_select.callback = self._on_cat
        self.add_item(cat_select)

        items = [i for i in SHOP_ITEMS.values() if i["category"] == self.category]
        for idx, item in enumerate(items[:4]):
            btn = discord.ui.Button(
                label=f"Beli {item['name']} ({item['price']:,} 💰)",
                style=discord.ButtonStyle.success,
                custom_id=f"shop_buy_{item['id']}",
                row=idx + 1,
            )
            btn.callback = self._make_buy_cb(item["id"])
            self.add_item(btn)

    def _make_buy_cb(self, item_id: str):
        async def _cb(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("❌ Ini bukan shopmu!", ephemeral=True)
                return
            result = buy_item(interaction.user.id, interaction.user.display_name, item_id)
            if not result["success"]:
                await interaction.response.send_message(embed=err_embed(result["error"]), ephemeral=True)
                return
            item = result["item"]
            await interaction.response.send_message(
                embed=discord.Embed(
                    title=f"✅ Berhasil Beli!",
                    description=f"{item['name']} x{result['quantity']}\nSisa saldo: {cash(result['new_balance'])}",
                    color=discord.Color.green(),
                ),
                ephemeral=True,
            )
        return _cb

    async def _on_cat(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Ini bukan shopmu!", ephemeral=True)
            return
        self.category = interaction.data["values"][0]
        self._rebuild()
        await interaction.response.edit_message(embed=self._shop_embed(), view=self)

    def _shop_embed(self) -> discord.Embed:
        profile = get_profile(self.user.id, self.user.display_name)
        embed = discord.Embed(
            title=f"🛒 WowoCash Shop",
            description=f"Saldo kamu: {cash(profile['balance'])}",
            color=wowo_color(),
        )
        items = [i for i in SHOP_ITEMS.values() if i["category"] == self.category]
        for item in items:
            inv_count = profile["inventory"].get(item["id"], 0)
            embed.add_field(
                name=f"{item['name']} — {item['price']:,} 💰",
                value=f"{item['description']}\n`Stack: {inv_count}/{item['max_stack']}`",
                inline=False,
            )
        embed.set_footer(text="Klik tombol untuk membeli")
        return embed

# ══════════════════════════════════════════════════════════════════════════════
# MISSIONS VIEW
# ══════════════════════════════════════════════════════════════════════════════

class MissionsView(discord.ui.View):
    def __init__(self, user: discord.Member):
        super().__init__(timeout=60)
        self.user     = user
        self.show_tab = "daily"

    @discord.ui.button(label="📅 Harian", style=discord.ButtonStyle.primary, custom_id="missions_daily")
    async def daily_tab(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Ini bukan misimu!", ephemeral=True)
            return
        self.show_tab = "daily"
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="📆 Mingguan", style=discord.ButtonStyle.secondary, custom_id="missions_weekly")
    async def weekly_tab(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Ini bukan misimu!", ephemeral=True)
            return
        self.show_tab = "weekly"
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    def _build_embed(self) -> discord.Embed:
        data  = get_missions(self.user.id, self.user.display_name)
        mlist = data["daily"] if self.show_tab == "daily" else data["weekly"]
        title = "📅 Misi Harian" if self.show_tab == "daily" else "📆 Misi Mingguan"

        embed = discord.Embed(title=title, color=wowo_color())
        embed.description = f"Saldo: {cash(data['balance'])}"
        for m in mlist:
            fill = int((m["progress"] / m["target"]) * 10)
            bar  = "█" * fill + "░" * (10 - fill)
            stat = "✅" if m["done"] else "⏳"
            embed.add_field(
                name=f"{stat} {m['name']}",
                value=f"{m['desc']}\n`{bar}` {m['progress']}/{m['target']}\n💰 Reward: **{m['reward']:,}**",
                inline=False,
            )
        embed.set_footer(text="Harian reset tiap tengah malam • Mingguan reset tiap Senin")
        return embed

# ══════════════════════════════════════════════════════════════════════════════
# MAIN COG
# ══════════════════════════════════════════════════════════════════════════════

class WowoCash(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /wowo_daily ───────────────────────────────────────────────────────────

    @app_commands.command(name="wowo_daily", description="Claim hadiah login harian")
    async def daily(self, interaction: discord.Interaction):
        result = claim_daily(interaction.user.id, interaction.user.display_name)

        if not result["success"]:
            embed = discord.Embed(
                title=f"⏰ Sudah Claim Hari Ini!",
                description=f"Kembali lagi dalam **{result['next_in']}**.",
                color=discord.Color.orange(),
            )
            embed.set_footer(text=f"Streak: 🔥 {result['streak']} hari")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        streak = result["streak"]
        reward = result["reward"]
        next_reward = DAILY_BASE + min(streak, DAILY_STREAK_MAX - 1) * DAILY_STREAK_BONUS

        embed = discord.Embed(
            title="🎁 Daily Login Berhasil!",
            description=f"Kamu mendapat {cash(reward)}!",
            color=discord.Color.green(),
        )
        streak_label = f"{streak} hari (MAKS! 🎉)" if streak >= DAILY_STREAK_MAX else f"{streak} hari → besok +{next_reward}"
        embed.add_field(name="🔥 Streak", value=streak_label, inline=True)
        bar = "🔥" * streak + "⬜" * (DAILY_STREAK_MAX - streak)
        embed.add_field(name="Progress Streak", value=bar, inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /wowo_balance ─────────────────────────────────────────────────────────

    @app_commands.command(name="wowo_balance", description="Cek saldo WowoCash")
    @app_commands.describe(user="User lain (opsional)")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        target  = user or interaction.user
        profile = get_profile(target.id, target.display_name)
        embed = discord.Embed(title=f"{CURRENCY_ICON} Saldo {target.display_name}", color=wowo_color())
        embed.add_field(name="💰 Saldo",          value=f"{profile['balance']:,}",  inline=True)
        embed.add_field(name="📈 Total Diperoleh", value=f"{profile['lifetime']:,}", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    # ── /wowo_profile ─────────────────────────────────────────────────────────

    @app_commands.command(name="wowo_profile", description="Lihat profil WowoCash lengkap")
    @app_commands.describe(user="User lain (opsional)")
    async def profile_cmd(self, interaction: discord.Interaction, user: discord.Member = None):
        target  = user or interaction.user
        profile = get_profile(target.id, target.display_name)
        stats   = profile["stats"]

        embed = discord.Embed(title=f"👤 Profil {target.display_name}", color=wowo_color())
        embed.set_thumbnail(url=target.display_avatar.url)
        if profile["badges"]:
            embed.description = "  ".join(profile["badges"])

        embed.add_field(name=f"{CURRENCY_ICON} Saldo",   value=f"{profile['balance']:,}",           inline=True)
        embed.add_field(name="📈 Total Earned",           value=f"{profile['lifetime']:,}",           inline=True)
        embed.add_field(name="🔥 Daily Streak",           value=f"{profile['daily']['streak']} hari", inline=True)
        embed.add_field(name="🎮 Games Played",           value=str(stats["games_played"]),           inline=True)
        embed.add_field(name="🏆 Games Won",              value=str(stats["games_won"]),              inline=True)
        embed.add_field(name="💪 Survived",               value=str(stats["games_survived"]),         inline=True)
        embed.add_field(name="🎰 Gacha Pulls",            value=str(stats["gacha_pulls"]),            inline=True)
        embed.add_field(name="📦 Inventory",              value=f"{len(profile['inventory'])} jenis", inline=True)
        embed.add_field(
            name="📋 Misi",
            value=f"Harian: {profile['daily_done']}/{profile['missions_total_daily']} | Mingguan: {profile['weekly_done']}/{profile['missions_total_weekly']}",
            inline=False,
        )
        txs = profile.get("transactions", [])[:5]
        if txs:
            tx_str = "\n".join(
                f"`{'+'if t['amount']>0 else ''}{t['amount']:,}` {t['note']}" for t in txs
            )
            embed.add_field(name="📜 Transaksi Terakhir", value=tx_str, inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /wowo_missions ────────────────────────────────────────────────────────

    @app_commands.command(name="wowo_missions", description="Lihat misi harian & mingguan")
    async def missions_cmd(self, interaction: discord.Interaction):
        view  = MissionsView(interaction.user)
        embed = view._build_embed()
        await interaction.response.send_message(embed=embed, view=view)

    # ── /wowo_shop ────────────────────────────────────────────────────────────

    @app_commands.command(name="wowo_shop", description="Lihat dan beli item di shop")
    async def shop(self, interaction: discord.Interaction):
        view  = ShopView(self, interaction.user)
        embed = view._shop_embed()
        await interaction.response.send_message(embed=embed, view=view)

    # ── /wowo_inventory ───────────────────────────────────────────────────────

    @app_commands.command(name="wowo_inventory", description="Lihat inventaris kamu")
    async def inventory(self, interaction: discord.Interaction):
        inv   = get_inventory(interaction.user.id, interaction.user.display_name)
        embed = discord.Embed(
            title=f"🎒 Inventaris {interaction.user.display_name}",
            description=f"Saldo: {cash(inv['balance'])}",
            color=wowo_color(),
        )
        if not inv["items"]:
            embed.add_field(name="Kosong", value="Belum ada item. Beli di `/wowo_shop`!", inline=False)
        else:
            for item in inv["items"]:
                embed.add_field(
                    name=f"{item['name']} ×{item['count']}",
                    value=item["description"],
                    inline=False,
                )
        await interaction.response.send_message(embed=embed)

    # ── /wowo_transfer ────────────────────────────────────────────────────────

    @app_commands.command(name="wowo_transfer", description="Kirim WowoCash ke user lain")
    @app_commands.describe(target="Penerima", amount="Jumlah yang dikirim")
    async def wowo_transfer(self, interaction: discord.Interaction, target: discord.Member, amount: int):
        if amount <= 0:
            await interaction.response.send_message(embed=err_embed("Jumlah harus lebih dari 0!"), ephemeral=True)
            return

        result = send_transfer(
            interaction.user.id, interaction.user.display_name,
            target.id, target.display_name,
            amount,
        )
        if not result["success"]:
            await interaction.response.send_message(embed=err_embed(result["error"]), ephemeral=True)
            return

        embed = discord.Embed(title="✅ Transfer Berhasil!", color=discord.Color.green())
        embed.add_field(name="Pengirim",     value=interaction.user.mention,       inline=True)
        embed.add_field(name="Penerima",     value=target.mention,                 inline=True)
        embed.add_field(name="💰 Dikirim",   value=f"{result['amount']:,}",         inline=True)
        embed.add_field(name="🏦 Fee (5%)",  value=f"{result['fee']:,}",            inline=True)
        embed.add_field(name="Sisa Saldo",   value=f"{result['sender_balance']:,}", inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /wowo_leaderboard ─────────────────────────────────────────────────────

    @app_commands.command(name="wowo_leaderboard", description="Top 10 saldo WowoCash")
    async def leaderboard(self, interaction: discord.Interaction):
        lb    = get_leaderboard(10)
        embed = discord.Embed(title=f"{CURRENCY_ICON} WowoCash Leaderboard", color=wowo_color())
        if not lb:
            embed.description = "Belum ada data."
        else:
            medals = ["🥇", "🥈", "🥉"]
            lines  = [
                f"{medals[e['rank']-1] if e['rank'] <= 3 else f'`#{e[chr(114)+(chr(97)+chr(110)+chr(107))]}`'} **{e['username']}** — {e['balance']:,} 💰"
                for e in lb
            ]
            embed.description = "\n".join(lines)
        embed.set_footer(text="Update realtime dari data lokal")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(WowoCash(bot))