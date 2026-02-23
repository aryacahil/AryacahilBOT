"""
Russian Roulette — Multiplayer (3 Nyawa)
─────────────────────────────────────────
/roulette create <bet>  — Buat meja
/roulette cancel        — Batalkan (host, sebelum mulai)
/roulette status        — Lihat status game

Cara main:
- Revolver 6 silinder, 1 peluru, dikocok ulang tiap ronde penuh
- Pemain gantian narik trigger
- Kena peluru → kehilangan 1 ❤️ (dari 3)
- Habis 3 nyawa → MATI → kehilangan bet
- Kalau semua silinder habis tanpa ada yang mati → spin ulang
- Pemenang terakhir ambil semua pot
"""

import asyncio
import random
import discord
from discord.ext import commands
from discord import app_commands
from economy.wowocash import (
    get_user, _save_user, _add_balance, _progress_mission,
    MIN_BET, MAX_BET,
)

# ─── Constants ────────────────────────────────────────────────────────────────

MAX_PLAYERS   = 6
MAX_LIVES     = 3
LOBBY_TIMEOUT = 120
TURN_TIMEOUT  = 10
CYLINDERS     = 6

# ─── Helpers ─────────────────────────────────────────────────────────────────

def cash(n: int) -> str:
    return f"💰 **{n:,}**"

def rr_color() -> discord.Color:
    return discord.Color.from_rgb(180, 0, 0)

def err_embed(msg: str) -> discord.Embed:
    return discord.Embed(description=f"❌ {msg}", color=discord.Color.red())

def lives_display(hp: int) -> str:
    """❤️❤️❤️ / ❤️❤️🖤 / ❤️🖤🖤 / 💀"""
    return "".join("❤️" if i < hp else "🖤" for i in range(MAX_LIVES))

# ──────────────────────────────────────────────────────────────────────────────
# GAME STATE
# ──────────────────────────────────────────────────────────────────────────────

class RRGame:
    def __init__(self, channel: discord.TextChannel, host: discord.Member, bet: int):
        self.channel  = channel
        self.host     = host
        self.bet      = bet

        self.players: list[discord.Member]        = [host]
        self.alive:   list[discord.Member]        = []
        self.dead:    list[discord.Member]        = []
        self.lives:   dict[discord.Member, int]   = {}   # member → remaining HP
        self.pot:     int  = 0

        self.started: bool = False
        self.ended:   bool = False

        # Revolver
        self.cylinder: int = 0
        self.bullet:   int = 0
        self.shots:    int = 0

        # Turn
        self.turn_idx: int = 0
        self.round:    int = 1

    @property
    def current_player(self) -> discord.Member:
        return self.alive[self.turn_idx % len(self.alive)]

    def spin(self):
        self.bullet   = random.randint(0, CYLINDERS - 1)
        self.cylinder = 0
        self.shots    = 0

    def pull_trigger(self) -> bool:
        fired         = (self.cylinder == self.bullet)
        self.cylinder = (self.cylinder + 1) % CYLINDERS
        self.shots   += 1
        return fired

    def hit(self, player: discord.Member) -> bool:
        """Apply 1 damage. Returns True if player just died (HP reached 0)."""
        self.lives[player] = self.lives.get(player, MAX_LIVES) - 1
        if self.lives[player] <= 0:
            self.alive.remove(player)
            self.dead.append(player)
            return True
        return False

    def lives_table(self) -> str:
        lines = []
        for p in self.players:
            if p in self.alive:
                lines.append(f"{lives_display(self.lives[p])} {p.display_name}")
            else:
                lines.append(f"💀 ~~{p.display_name}~~")
        return "\n".join(lines)

# ──────────────────────────────────────────────────────────────────────────────
# LOBBY VIEW
# ──────────────────────────────────────────────────────────────────────────────

class LobbyView(discord.ui.View):
    def __init__(self, cog: "RouletteCog", game: RRGame):
        super().__init__(timeout=LOBBY_TIMEOUT)
        self.cog  = cog
        self.game = game

    def lobby_embed(self) -> discord.Embed:
        g = self.game
        embed = discord.Embed(
            title       = "🔫 Russian Roulette — Lobby",
            description = (
                f"**Bet:** {cash(g.bet)} per pemain\n"
                f"**Pot perkiraan:** {cash(g.bet * len(g.players))}\n\n"
                f"🔫 6 silinder • 1 peluru • {MAX_LIVES} nyawa per pemain\n"
                f"Kena peluru = -1 ❤️ • Habis nyawa = 💀 + kehilangan bet\n"
                f"**Pemenang terakhir ambil semua pot!**"
            ),
            color=rr_color(),
        )
        embed.add_field(
            name  = f"Pemain ({len(g.players)}/{MAX_PLAYERS})",
            value = "\n".join(
                f"{'👑' if p == g.host else '🎯'} {p.display_name}" for p in g.players
            ),
            inline=False,
        )
        embed.set_footer(text=f"Host: {g.host.display_name} • Min 2 pemain")
        return embed

    @discord.ui.button(label="🎯 Join", style=discord.ButtonStyle.danger, custom_id="rr_join")
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = self.game
        if g.started:
            await interaction.response.send_message("❌ Game sudah berjalan!", ephemeral=True)
            return
        if interaction.user in g.players:
            await interaction.response.send_message("❌ Kamu sudah di lobby!", ephemeral=True)
            return
        if len(g.players) >= MAX_PLAYERS:
            await interaction.response.send_message(f"❌ Lobby penuh! (max {MAX_PLAYERS})", ephemeral=True)
            return
        u = get_user(interaction.user.id, interaction.user.display_name)
        if u["balance"] < g.bet:
            await interaction.response.send_message(
                f"❌ WowoCash tidak cukup! Butuh {cash(g.bet)}, punya {cash(u['balance'])}.",
                ephemeral=True,
            )
            return
        g.players.append(interaction.user)
        await interaction.response.edit_message(embed=self.lobby_embed(), view=self)

    @discord.ui.button(label="🚪 Leave", style=discord.ButtonStyle.secondary, custom_id="rr_leave")
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = self.game
        if g.started:
            await interaction.response.send_message("❌ Sudah terlanjur mulai!", ephemeral=True)
            return
        if interaction.user not in g.players:
            await interaction.response.send_message("❌ Kamu tidak ada di lobby.", ephemeral=True)
            return
        if interaction.user == g.host:
            await interaction.response.send_message("❌ Host tidak bisa leave. Gunakan /roulette cancel.", ephemeral=True)
            return
        g.players.remove(interaction.user)
        await interaction.response.edit_message(embed=self.lobby_embed(), view=self)

    @discord.ui.button(label="▶️ Mulai", style=discord.ButtonStyle.primary, custom_id="rr_start")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = self.game
        if interaction.user != g.host:
            await interaction.response.send_message("❌ Hanya host yang bisa mulai!", ephemeral=True)
            return
        if len(g.players) < 2:
            await interaction.response.send_message("❌ Minimal 2 pemain!", ephemeral=True)
            return
        if g.started:
            await interaction.response.send_message("❌ Sudah dimulai!", ephemeral=True)
            return

        # Cek saldo semua pemain
        broke = [p.display_name for p in g.players
                 if get_user(p.id, p.display_name)["balance"] < g.bet]
        if broke:
            await interaction.response.send_message(
                f"❌ Saldo tidak cukup: {', '.join(broke)}", ephemeral=True
            )
            return

        # Potong bet
        for p in g.players:
            u = get_user(p.id, p.display_name)
            u = _add_balance(u, -g.bet, "Russian Roulette bet")
            _save_user(p.id, u)

        g.pot     = g.bet * len(g.players)
        g.started = True

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🔫 Russian Roulette — Dimulai!",
                description="Memuat revolver...",
                color=rr_color(),
            ),
            view=self,
        )
        await self.cog._run_game(g)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

# ──────────────────────────────────────────────────────────────────────────────
# SHOOT VIEW
# ──────────────────────────────────────────────────────────────────────────────

class ShootView(discord.ui.View):
    def __init__(self, cog: "RouletteCog", game: RRGame, current: discord.Member):
        super().__init__(timeout=TURN_TIMEOUT)
        self.cog     = cog
        self.game    = game
        self.current = current
        self.fired   = False

    @discord.ui.button(label="🔫 Tarik Trigger", style=discord.ButtonStyle.danger, custom_id="rr_shoot")
    async def shoot_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.current.id:
            await interaction.response.send_message(
                f"❌ Bukan giliranmu! Sekarang giliran **{self.current.display_name}**.",
                ephemeral=True,
            )
            return
        if self.fired:
            await interaction.response.send_message("❌ Sudah ditembak!", ephemeral=True)
            return

        self.fired = True
        for child in self.children:
            child.disabled = True

        # Suspense animation
        suspense = discord.Embed(
            title       = "🔫 Mengarahkan pistol...",
            description = f"**{self.current.display_name}** menaruh revolver di kepala...\n\n`...`",
            color       = discord.Color.from_rgb(100, 0, 0),
        )
        await interaction.response.edit_message(embed=suspense, view=self)

        for emoji, text in [("3️⃣", "Jari di trigger..."), ("2️⃣", "Napas ditahan..."), ("1️⃣", "💢 *KLIK*")]:
            await asyncio.sleep(0.9)
            suspense.description = (
                f"**{self.current.display_name}** menaruh revolver di kepala...\n\n{emoji} {text}"
            )
            await interaction.edit_original_response(embed=suspense)

        await asyncio.sleep(1.0)

        fired = self.game.pull_trigger()
        self.stop()
        await self.cog._resolve_shot(interaction, self.game, self.current, fired)

    async def on_timeout(self):
        if not self.fired:
            self.fired = True
            for child in self.children:
                child.disabled = True
            await self.cog._auto_shoot(self.game, self.current)

# ──────────────────────────────────────────────────────────────────────────────
# MAIN COG
# ──────────────────────────────────────────────────────────────────────────────

class RouletteCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self.games: dict[int, RRGame]      = {}
        self._tasks: dict[int, asyncio.Task] = {}

    roulette = app_commands.Group(name="roulette", description="🔫 Russian Roulette")

    # ── /roulette create ──────────────────────────────────────────────────────

    @roulette.command(name="create", description="Buat meja Russian Roulette")
    @app_commands.describe(bet="Jumlah taruhan per pemain")
    async def create(self, interaction: discord.Interaction, bet: int):
        cid = interaction.channel_id
        if cid in self.games:
            await interaction.response.send_message(
                "❌ Sudah ada game di channel ini!", ephemeral=True
            )
            return
        if not (MIN_BET <= bet <= MAX_BET):
            await interaction.response.send_message(
                f"❌ Bet harus antara {MIN_BET:,}–{MAX_BET:,} 💰.", ephemeral=True
            )
            return
        u = get_user(interaction.user.id, interaction.user.display_name)
        if u["balance"] < bet:
            await interaction.response.send_message(
                f"❌ WowoCash tidak cukup! Butuh {cash(bet)}, punya {cash(u['balance'])}.",
                ephemeral=True,
            )
            return

        game            = RRGame(interaction.channel, interaction.user, bet)
        self.games[cid] = game
        view            = LobbyView(self, game)
        await interaction.response.send_message(embed=view.lobby_embed(), view=view)

    # ── /roulette cancel ──────────────────────────────────────────────────────

    @roulette.command(name="cancel", description="Batalkan game (host only, sebelum mulai)")
    async def cancel(self, interaction: discord.Interaction):
        cid  = interaction.channel_id
        game = self.games.get(cid)
        if not game:
            await interaction.response.send_message("❌ Tidak ada game aktif.", ephemeral=True)
            return
        if game.started:
            await interaction.response.send_message("❌ Game sudah dimulai!", ephemeral=True)
            return
        if interaction.user != game.host:
            await interaction.response.send_message("❌ Hanya host yang bisa cancel!", ephemeral=True)
            return
        del self.games[cid]
        await interaction.response.send_message(
            embed=discord.Embed(title="🚫 Game Dibatalkan", color=discord.Color.greyple())
        )

    # ── /roulette status ──────────────────────────────────────────────────────

    @roulette.command(name="status", description="Lihat status game saat ini")
    async def status(self, interaction: discord.Interaction):
        game = self.games.get(interaction.channel_id)
        if not game:
            await interaction.response.send_message("❌ Tidak ada game aktif.", ephemeral=True)
            return
        embed = discord.Embed(title="🔫 Russian Roulette — Status", color=rr_color())
        if not game.started:
            embed.description = f"Menunggu pemain... ({len(game.players)} sudah join)"
        else:
            embed.add_field(name="🏆 Pot",     value=cash(game.pot),                   inline=True)
            embed.add_field(name="🔄 Ronde",   value=str(game.round),                  inline=True)
            embed.add_field(name="🎯 Giliran", value=game.current_player.display_name, inline=True)
            embed.add_field(name="❤️ Nyawa",   value=game.lives_table(),               inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ──────────────────────────────────────────────────────────────────────────
    # GAME LOOP
    # ──────────────────────────────────────────────────────────────────────────

    async def _run_game(self, game: RRGame):
        cid = game.channel.id

        # Setup
        game.alive    = game.players.copy()
        game.lives    = {p: MAX_LIVES for p in game.players}
        random.shuffle(game.alive)
        game.turn_idx = 0
        game.round    = 1
        game.spin()

        await self._send_intro(game)
        await asyncio.sleep(2)

        while len(game.alive) > 1:
            current = game.current_player

            # Spin ulang kalau semua silinder habis
            if game.shots >= CYLINDERS:
                await game.channel.send(embed=discord.Embed(
                    title       = "🔄 Spin Ulang!",
                    description = "Semua silinder sudah dicoba — **mengocok ulang revolver...**\n🎲 *Klik... klik... klik...*",
                    color       = rr_color(),
                ))
                await asyncio.sleep(2)
                game.spin()
                game.round += 1

            embed = self._turn_embed(game, current)
            view  = ShootView(self, game, current)
            await game.channel.send(
                content=f"🔫 {current.mention} — **giliranmu!**",
                embed=embed,
                view=view,
            )

            await view.wait()

            if cid not in self.games:
                return

        if game.alive:
            await self._end_game(game, game.alive[0])

    async def _send_intro(self, game: RRGame):
        embed = discord.Embed(title="🔫 Russian Roulette — DIMULAI", color=rr_color())
        embed.add_field(
            name  = "Peserta",
            value = "\n".join(
                f"`{i+1}.` {p.display_name} {lives_display(MAX_LIVES)}"
                for i, p in enumerate(game.alive)
            ),
            inline=True,
        )
        embed.add_field(name="💰 Pot",   value=cash(game.pot), inline=True)
        embed.add_field(name="❤️ Nyawa", value=f"{MAX_LIVES} per pemain",  inline=True)

        msg = await game.channel.send(embed=embed)
        for icon, text in [
            ("🔫", "Mengambil revolver..."),
            ("🔄", "Memasukkan 1 peluru..."),
            ("💨", "Mengocok silinder..."),
            ("🎯", f"Siap! Urutan: {' → '.join(p.display_name for p in game.alive)}"),
        ]:
            await asyncio.sleep(0.7)
            embed.description = f"{icon} *{text}*"
            await msg.edit(embed=embed)

    def _turn_embed(self, game: RRGame, current: discord.Member) -> discord.Embed:
        # Chamber visualization
        chambers = ["✅" if i < game.shots else "⬜" for i in range(CYLINDERS)]
        chambers_str = " ".join(chambers)

        embed = discord.Embed(
            title       = f"🔫 Ronde {game.round} — Giliran {current.display_name}",
            description = (
                f"```\n[ {chambers_str} ]\n```\n"
                f"*{game.shots} sudah ditarik — {CYLINDERS - game.shots} tersisa*"
            ),
            color=rr_color(),
        )
        embed.add_field(name="❤️ Status Nyawa", value=game.lives_table(), inline=False)
        embed.add_field(name="💰 Pot",           value=cash(game.pot),    inline=True)
        embed.set_footer(text=f"⏱️ {TURN_TIMEOUT}d untuk menarik trigger...")
        return embed

    # ──────────────────────────────────────────────────────────────────────────
    # RESOLVE SHOT
    # ──────────────────────────────────────────────────────────────────────────

    async def _resolve_shot(
        self,
        interaction: discord.Interaction,
        game: RRGame,
        player: discord.Member,
        fired: bool,
    ):
        cid = game.channel.id
        if cid not in self.games:
            return

        if not fired:
            # ── SELAMAT ───────────────────────────────────────────────────────
            embed = discord.Embed(
                title = f"✅ {player.display_name} Selamat!",
                color = discord.Color.green(),
            )
            for frame in ["💨 *...*", "😰 *...*", "😅 **KLIK.**", "✅ **Kosong!**"]:
                embed.description = frame
                await interaction.edit_original_response(embed=embed)
                await asyncio.sleep(0.5)

            embed.description = f"Silinder kosong! {player.display_name} masih hidup... 😤"
            embed.add_field(name="❤️ Status Nyawa", value=game.lives_table(), inline=False)
            await interaction.edit_original_response(embed=embed)

            # Advance turn
            game.turn_idx = (game.alive.index(player) + 1) % len(game.alive)

        else:
            # ── KENA TEMBAK ───────────────────────────────────────────────────
            embed = discord.Embed(color=discord.Color.from_rgb(50, 0, 0))
            for icon, text in [("💥", "**DUAR!!!**"), ("🩸", f"**{player.display_name} terkena peluru!**")]:
                embed.title       = icon
                embed.description = text
                await interaction.edit_original_response(embed=embed)
                await asyncio.sleep(0.8)

            # Apply damage
            died = game.hit(player)
            hp   = game.lives.get(player, 0)

            if died:
                # ── MATI ──────────────────────────────────────────────────────
                embed = discord.Embed(
                    title       = f"💀 {player.display_name} MATI!",
                    description = (
                        f"**{player.display_name}** kehabisan nyawa!\n"
                        f"{lives_display(0)}\n\n"
                        f"💸 Kehilangan {cash(game.bet)}"
                    ),
                    color=discord.Color.red(),
                )
                embed.add_field(name="❤️ Status Nyawa", value=game.lives_table(), inline=False)
                await interaction.edit_original_response(embed=embed)

                if game.alive:
                    game.turn_idx = game.turn_idx % len(game.alive)

                await asyncio.sleep(1.5)

                if len(game.alive) == 1:
                    await self._end_game(game, game.alive[0])
                elif len(game.alive) == 0:
                    await self._end_game(game, None)

            else:
                # ── TERLUKA — masih hidup ─────────────────────────────────────
                embed = discord.Embed(
                    title       = f"🩸 {player.display_name} Terluka! ({lives_display(hp)})",
                    description = (
                        f"**{player.display_name}** terkena peluru tapi masih hidup!\n"
                        f"Sisa nyawa: {lives_display(hp)} **({hp}/{MAX_LIVES})**"
                    ),
                    color=discord.Color.from_rgb(200, 50, 50),
                )
                embed.add_field(name="❤️ Status Semua", value=game.lives_table(), inline=False)
                await interaction.edit_original_response(embed=embed)

                # Turn tetap maju ke berikutnya
                game.turn_idx = (game.alive.index(player) + 1) % len(game.alive)

    # ──────────────────────────────────────────────────────────────────────────
    # AUTO SHOOT
    # ──────────────────────────────────────────────────────────────────────────

    async def _auto_shoot(self, game: RRGame, player: discord.Member):
        cid = game.channel.id
        if cid not in self.games or game.ended:
            return

        fired = game.pull_trigger()
        embed = discord.Embed(
            title       = f"⏰ {player.display_name} Timeout!",
            description = f"**{player.display_name}** terlalu lama — revolver otomatis ditembak!",
            color       = discord.Color.orange(),
        )

        if fired:
            died = game.hit(player)
            hp   = game.lives.get(player, 0)

            if died:
                embed.title       = f"💀 {player.display_name} MATI! (Timeout)"
                embed.description = (
                    f"Revolver otomatis berbunyi dan mengenai **{player.display_name}**!\n"
                    f"{lives_display(0)} — kehabisan nyawa!\n💸 Kehilangan {cash(game.bet)}"
                )
                embed.color = discord.Color.red()
                await game.channel.send(embed=embed)
                if game.alive:
                    game.turn_idx = game.turn_idx % len(game.alive)
                if len(game.alive) <= 1:
                    await self._end_game(game, game.alive[0] if game.alive else None)
            else:
                embed.description = (
                    f"Revolver otomatis berbunyi dan mengenai **{player.display_name}**!\n"
                    f"Sisa nyawa: {lives_display(hp)} **({hp}/{MAX_LIVES})**\n"
                    f"💸 -1 nyawa"
                )
                embed.color = discord.Color.from_rgb(200, 50, 50)
                await game.channel.send(embed=embed)
                game.turn_idx = (game.alive.index(player) + 1) % len(game.alive) if player in game.alive else 0
        else:
            embed.description += "\n\n✅ **Kosong.** Lanjut ke berikutnya."
            await game.channel.send(embed=embed)
            if player in game.alive:
                game.turn_idx = (game.alive.index(player) + 1) % len(game.alive)

    # ──────────────────────────────────────────────────────────────────────────
    # END GAME
    # ──────────────────────────────────────────────────────────────────────────

    async def _end_game(self, game: RRGame, winner: discord.Member | None):
        cid = game.channel.id
        if game.ended:
            return
        game.ended = True

        if winner:
            u = get_user(winner.id, winner.display_name)
            u = _add_balance(u, game.pot, f"Russian Roulette menang (pot {game.pot:,})")
            u = _progress_mission(u, "casino", 1)
            _save_user(winner.id, u)

            death_roll = "\n".join(
                f"`{i+1}.` 💀 ~~{p.display_name}~~  {lives_display(0)}"
                for i, p in enumerate(game.dead)
            )
            embed = discord.Embed(
                title       = f"🏆 {winner.display_name} MENANG!",
                description = (
                    f"**{winner.display_name}** adalah satu-satunya yang selamat!\n"
                    f"Sisa nyawa: {lives_display(game.lives.get(winner, 0))}\n\n"
                    f"💰 Mengambil seluruh pot: **{game.pot:,} WowoCash**!"
                ),
                color=discord.Color.gold(),
            )
            if death_roll:
                embed.add_field(name="💀 Urutan Mati", value=death_roll,        inline=False)
            embed.add_field(
                name  = "📊 Ringkasan",
                value = f"Pemain: {len(game.players)} • Bet: {cash(game.bet)} • Pot: {cash(game.pot)}",
                inline=False,
            )
            embed.set_footer(text="Gunakan /roulette create untuk main lagi!")
            await game.channel.send(embed=embed)
        else:
            await game.channel.send(embed=discord.Embed(
                title       = "💀 Semua Mati!",
                description = "Tidak ada pemenang. Pot hangus.",
                color       = discord.Color.dark_grey(),
            ))

        self.games.pop(cid, None)
        task = self._tasks.pop(cid, None)
        if task and not task.done():
            task.cancel()


async def setup(bot: commands.Bot):
    await bot.add_cog(RouletteCog(bot))