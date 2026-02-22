import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from games.werewolf_game import (
    WerewolfGame, Phase, Role, ROLE_INFO,
    NIGHT_ACTION_TIMEOUT, DAY_DISCUSSION_TIME, VOTE_TIMEOUT
)

# ══════════════════════════════════════════════════════════════════════════════
# EMBED HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def make_embed(title: str, description: str = "", color=discord.Color.dark_gray()) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)

def role_dm_embed(role: Role) -> discord.Embed:
    info = ROLE_INFO[role]
    embed = discord.Embed(
        title       = f"{info['emoji']} Role Kamu: {role.value}",
        description = info["description"],
        color       = info["color"],
    )
    embed.set_footer(text=f"Tim: {info['team']}")
    return embed

# ══════════════════════════════════════════════════════════════════════════════
# LOBBY VIEW
# ══════════════════════════════════════════════════════════════════════════════

class LobbyView(discord.ui.View):
    def __init__(self, cog: "Werewolf", game: WerewolfGame):
        super().__init__(timeout=None)
        self.cog  = cog
        self.game = game

    def lobby_embed(self) -> discord.Embed:
        embed = discord.Embed(title="🐺 Werewolf — Lobby", color=discord.Color.dark_red())
        if self.game.players:
            embed.add_field(
                name  = f"Pemain ({len(self.game.players)})",
                value = "\n".join(f"• {p.display_name}" for p in self.game.players),
                inline=False,
            )
        else:
            embed.add_field(name="Pemain", value="*Belum ada pemain*", inline=False)

        # Role preview based on player count
        from games.werewolf_game import build_role_list
        from collections import Counter
        if len(self.game.players) >= 4:
            role_count = Counter(build_role_list(len(self.game.players)))
            preview = " · ".join(
                f"{ROLE_INFO[r]['emoji']} {r.value} ×{c}" for r, c in role_count.items()
            )
            embed.add_field(name="Role yang akan dipakai", value=preview, inline=False)

        embed.set_footer(text="Minimal 4 pemain untuk mulai • Pastikan DM terbuka!")
        return embed

    @discord.ui.button(label="✋ Join", style=discord.ButtonStyle.success, custom_id="lobby_join")
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game.phase != Phase.WAITING:
            await interaction.response.send_message("❌ Game sudah berjalan!", ephemeral=True)
            return
        if not self.game.add_player(interaction.user):
            await interaction.response.send_message("❌ Kamu sudah bergabung!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.lobby_embed(), view=self)

    @discord.ui.button(label="🚪 Leave", style=discord.ButtonStyle.secondary, custom_id="lobby_leave")
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game.phase != Phase.WAITING:
            await interaction.response.send_message("❌ Tidak bisa keluar, game sudah mulai!", ephemeral=True)
            return
        if not self.game.remove_player(interaction.user):
            await interaction.response.send_message("❌ Kamu tidak ada di lobby.", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.lobby_embed(), view=self)

    @discord.ui.button(label="▶️ Start", style=discord.ButtonStyle.primary, custom_id="lobby_start")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game.phase != Phase.WAITING:
            await interaction.response.send_message("❌ Game sudah berjalan!", ephemeral=True)
            return
        if len(self.game.players) < 4:
            await interaction.response.send_message("❌ Minimal 4 pemain!", ephemeral=True)
            return
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=make_embed("🎲 Memulai game...", "Role sedang dibagikan via DM!", discord.Color.blurple()),
            view=self,
        )
        await self.cog._start_game(self.game)

    @discord.ui.button(label="🗑️ Cancel", style=discord.ButtonStyle.danger, custom_id="lobby_cancel")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cid  = self.game.channel.id
        task = self.cog._game_tasks.pop(cid, None)
        if task:
            task.cancel()
        self.cog.games.pop(cid, None)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=make_embed("🗑️ Game Dibatalkan", "", discord.Color.greyple()),
            view=self,
        )

# ══════════════════════════════════════════════════════════════════════════════
# NIGHT SELECT VIEW  — generic dropdown DM
# ══════════════════════════════════════════════════════════════════════════════

class NightSelectView(discord.ui.View):
    def __init__(
        self,
        actor:       discord.Member,
        targets:     list[discord.Member],
        callback,
        placeholder: str = "Pilih target...",
        timeout:     int = NIGHT_ACTION_TIMEOUT,
    ):
        super().__init__(timeout=timeout)
        self.actor    = actor
        self.callback = callback
        self.done     = False

        options         = [discord.SelectOption(label=t.display_name, value=str(t.id)) for t in targets]
        select          = discord.ui.Select(placeholder=placeholder, options=options)
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user != self.actor:
            await interaction.response.send_message("❌ Ini bukan aksimu!", ephemeral=True)
            return
        if self.done:
            await interaction.response.send_message("❌ Kamu sudah memilih!", ephemeral=True)
            return
        self.done = True
        for child in self.children:
            child.disabled = True

        target_id   = int(interaction.data["values"][0])
        target      = discord.utils.get(self.actor.guild.members, id=target_id)
        result_text = await self.callback(self.actor, target)

        await interaction.response.edit_message(
            embed=make_embed("✅ Aksi Dikonfirmasi", result_text, discord.Color.green()),
            view=self,
        )
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

# ══════════════════════════════════════════════════════════════════════════════
# WITCH VIEW
# ══════════════════════════════════════════════════════════════════════════════

class WitchView(discord.ui.View):
    def __init__(self, actor: discord.Member, game: WerewolfGame, timeout: int = NIGHT_ACTION_TIMEOUT):
        super().__init__(timeout=timeout)
        self.actor = actor
        self.game  = game
        if not game.witch_heal:
            self.heal_btn.disabled = True
        if not game.witch_poison:
            self.poison_btn.disabled = True

    @discord.ui.button(label="💊 Sembuhkan Korban", style=discord.ButtonStyle.success, custom_id="witch_heal")
    async def heal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.actor:
            await interaction.response.send_message("❌ Bukan aksimu!", ephemeral=True)
            return
        if not self.game.witch_heal:
            await interaction.response.send_message("❌ Ramuan sembuh sudah habis!", ephemeral=True)
            return
        if self.game.night_kill is None:
            await interaction.response.send_message("❌ Belum ada korban malam ini.", ephemeral=True)
            return
        victim               = self.game.night_kill
        self.game.witch_heal = False
        self.game.doctor_save = victim   # reuse doctor_save slot
        self.game._night_acted.add(self.actor)
        button.disabled = True
        await interaction.response.edit_message(
            embed=make_embed("✅ Ramuan Sembuh", f"Kamu menyelamatkan **{victim.display_name}**!\nRamuan sembuh habis.", discord.Color.green()),
            view=self,
        )

    @discord.ui.button(label="☠️ Racuni Seseorang", style=discord.ButtonStyle.danger, custom_id="witch_poison_btn")
    async def poison_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.actor:
            await interaction.response.send_message("❌ Bukan aksimu!", ephemeral=True)
            return
        if not self.game.witch_poison:
            await interaction.response.send_message("❌ Ramuan racun sudah habis!", ephemeral=True)
            return
        targets = [p for p in self.game.alive if p != self.actor]
        options = [discord.SelectOption(label=t.display_name, value=str(t.id)) for t in targets]
        select  = discord.ui.Select(placeholder="Pilih target racun...", options=options, custom_id="witch_poison_select")

        async def _poison_cb(sel_i: discord.Interaction):
            if sel_i.user != self.actor:
                await sel_i.response.send_message("❌ Bukan aksimu!", ephemeral=True)
                return
            tid    = int(sel_i.data["values"][0])
            target = discord.utils.get(self.actor.guild.members, id=tid)
            self.game.witch_poison        = False
            self.game.witch_poison_target = target
            self.game._night_acted.add(self.actor)
            for child in self.children:
                child.disabled = True
            await sel_i.response.edit_message(
                embed=make_embed("✅ Racun Digunakan", f"Kamu meracuni **{target.display_name}**!\nRamuan racun habis.", discord.Color.red()),
                view=self,
            )

        select.callback = _poison_cb
        self.add_item(select)
        button.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="⏭️ Lewati", style=discord.ButtonStyle.secondary, custom_id="witch_skip")
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.actor:
            await interaction.response.send_message("❌ Bukan aksimu!", ephemeral=True)
            return
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=make_embed("⏭️ Dilewati", "Kamu tidak menggunakan ramuan malam ini.", discord.Color.greyple()),
            view=self,
        )
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

# ══════════════════════════════════════════════════════════════════════════════
# VOTING VIEW
# ══════════════════════════════════════════════════════════════════════════════

class VoteView(discord.ui.View):
    def __init__(self, game: WerewolfGame, timeout: int = VOTE_TIMEOUT):
        super().__init__(timeout=timeout)
        self.game = game
        self._rebuild_select()

    def _rebuild_select(self):
        self.clear_items()
        options         = [discord.SelectOption(label=p.display_name, value=str(p.id)) for p in self.game.alive]
        select          = discord.ui.Select(placeholder="Pilih siapa yang akan dieksekusi...", options=options, custom_id="vote_select")
        select.callback = self._on_vote
        self.add_item(select)

    async def _on_vote(self, interaction: discord.Interaction):
        voter = interaction.user
        if not self.game.is_alive(voter):
            await interaction.response.send_message("❌ Kamu sudah mati!", ephemeral=True)
            return
        tid    = int(interaction.data["values"][0])
        target = discord.utils.get(voter.guild.members, id=tid)
        if not self.game.cast_vote(voter, target):
            await interaction.response.send_message("❌ Vote tidak valid!", ephemeral=True)
            return
        # Track for WowoCash missions
        try:
            from economy.wowocash import progress_vote
            progress_vote(voter.id, voter.display_name)
        except Exception:
            pass
        await interaction.response.edit_message(embed=self.vote_embed(), view=self)
        await interaction.followup.send(f"🗳️ **{voter.display_name}** memvote **{target.display_name}**")

    def vote_embed(self) -> discord.Embed:
        from collections import Counter
        embed     = discord.Embed(title="🗳️ Voting Berjalan", color=discord.Color.orange())
        alive_str = "\n".join(f"• {p.display_name}" for p in self.game.alive)
        embed.add_field(name="Pemain Hidup", value=alive_str, inline=True)
        if self.game.votes:
            tally = Counter(self.game.votes.values())
            embed.add_field(
                name  = "📊 Tally",
                value = "\n".join(f"**{p.display_name}** — {v} vote{'s' if v>1 else ''}" for p, v in tally.most_common()),
                inline=True,
            )
        not_voted = [p for p in self.game.alive if p not in self.game.votes]
        if not_voted:
            embed.add_field(
                name  = f"⏳ Belum Vote ({len(not_voted)})",
                value = "\n".join(f"• {p.display_name}" for p in not_voted),
                inline=False,
            )
        embed.set_footer(text=f"⏱️ {VOTE_TIMEOUT} detik | Kamu bisa ganti vote kapan saja")
        return embed

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

# ══════════════════════════════════════════════════════════════════════════════
# HUNTER VIEW
# ══════════════════════════════════════════════════════════════════════════════

class HunterView(discord.ui.View):
    def __init__(self, hunter: discord.Member, game: WerewolfGame, cog: "Werewolf"):
        super().__init__(timeout=30)
        self.hunter = hunter
        self.game   = game
        self.cog    = cog
        self.shot   = False

        options         = [discord.SelectOption(label=p.display_name, value=str(p.id)) for p in game.alive]
        select          = discord.ui.Select(placeholder="Tembak siapa?", options=options)
        select.callback = self._on_shoot
        self.add_item(select)

    async def _on_shoot(self, interaction: discord.Interaction):
        if interaction.user != self.hunter:
            await interaction.response.send_message("❌ Bukan aksimu!", ephemeral=True)
            return
        if self.shot:
            return
        self.shot                  = True
        self.game._pending_hunter  = None
        tid    = int(interaction.data["values"][0])
        target = discord.utils.get(self.hunter.guild.members, id=tid)
        self.game.eliminate(target)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=make_embed("🏹 Tembakan!", f"Kamu menembak **{target.display_name}**!", discord.Color.orange()),
            view=self,
        )
        await self.game.channel.send(embed=make_embed(
            "🏹 Hunter Menembak!",
            f"**{self.hunter.display_name}** menembak **{target.display_name}** sebelum mati!",
            discord.Color.orange(),
        ))
        winner = self.game.check_win()
        if winner:
            await self.cog.end_game(self.game, winner)
        self.stop()

    async def on_timeout(self):
        self.game._pending_hunter = None
        for child in self.children:
            child.disabled = True

# ══════════════════════════════════════════════════════════════════════════════
# MAIN COG
# ══════════════════════════════════════════════════════════════════════════════

class Werewolf(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot          = bot
        self.games:       dict[int, WerewolfGame] = {}
        self._game_tasks: dict[int, asyncio.Task] = {}

    def get_game(self, channel_id: int) -> WerewolfGame | None:
        return self.games.get(channel_id)

    async def safe_dm(self, member: discord.Member, **kwargs) -> bool:
        try:
            await member.send(**kwargs)
            return True
        except discord.Forbidden:
            return False

    async def announce(self, game: WerewolfGame, **kwargs):
        await game.channel.send(**kwargs)

    # ── /ww_create ────────────────────────────────────────────────────────────

    @app_commands.command(name="ww_create", description="Buat game Werewolf di channel ini")
    async def create(self, interaction: discord.Interaction):
        cid = interaction.channel_id
        if cid in self.games:
            await interaction.response.send_message("❌ Sudah ada game di channel ini!", ephemeral=True)
            return
        game            = WerewolfGame(self.bot, interaction.channel)
        self.games[cid] = game
        view            = LobbyView(self, game)
        await interaction.response.send_message(embed=view.lobby_embed(), view=view)

    # ── /ww_status ────────────────────────────────────────────────────────────

    @app_commands.command(name="ww_status", description="Lihat status game saat ini")
    async def status(self, interaction: discord.Interaction):
        game = self.get_game(interaction.channel_id)
        if not game:
            await interaction.response.send_message("❌ Tidak ada game.", ephemeral=True)
            return
        embed = discord.Embed(title="📊 Status Game", color=discord.Color.blurple())
        embed.add_field(name="Fase",         value=game.phase.value.capitalize(), inline=True)
        embed.add_field(name="Hari",         value=str(game.day_number),          inline=True)
        embed.add_field(name="Pemain Hidup", value=str(len(game.alive)),           inline=True)
        if game.alive:
            embed.add_field(name="Masih Hidup", value=game.alive_list_str(), inline=False)
        if game.dead:
            dead_str = "\n".join(
                f"💀 {p.display_name} ({ROLE_INFO[game.roles[p]]['emoji']} {game.roles[p].value})"
                for p in game.dead
            )
            embed.add_field(name="Sudah Mati", value=dead_str, inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /ww_cancel ────────────────────────────────────────────────────────────

    @app_commands.command(name="ww_cancel", description="Batalkan game Werewolf")
    async def cancel(self, interaction: discord.Interaction):
        cid = interaction.channel_id
        if cid not in self.games:
            await interaction.response.send_message("❌ Tidak ada game.", ephemeral=True)
            return
        task = self._game_tasks.pop(cid, None)
        if task:
            task.cancel()
        del self.games[cid]
        await interaction.response.send_message(embed=make_embed("🗑️ Game Dibatalkan", "", discord.Color.greyple()))

    # ══════════════════════════════════════════════════════════════════════════
    # START GAME
    # ══════════════════════════════════════════════════════════════════════════

    async def _start_game(self, game: WerewolfGame):
        game.assign_roles()

        # Send role DMs
        failed = []
        for player in game.players:
            ok = await self.safe_dm(player, embed=role_dm_embed(game.role_of(player)))
            if not ok:
                failed.append(player.display_name)
        if failed:
            await self.announce(game, content=f"⚠️ Tidak bisa DM ke: {', '.join(failed)}. Pastikan DM terbuka!")

        # Tell wolves their teammates + Cursed identity (wolves know who is Cursed)
        wolves = game.get_wolves()
        cursed = game.get_role_member(Role.CURSED)
        if len(wolves) >= 1:
            wolf_names = ", ".join(w.display_name for w in wolves)
            cursed_hint = f"\n🔮 **Cursed**: {cursed.display_name} (akan berubah jika kalian serang)" if cursed else ""
            for wolf in wolves:
                others = [w for w in wolves if w != wolf]
                teammates = ", ".join(w.display_name for w in others) if others else "Tidak ada"
                await self.safe_dm(wolf, embed=make_embed(
                    "🐺 Info Tim Serigala",
                    f"Sesama serigala: **{teammates}**{cursed_hint}",
                    discord.Color.red(),
                ))

        cid               = game.channel.id
        task              = asyncio.create_task(self.game_loop(game))
        self._game_tasks[cid] = task

    # ══════════════════════════════════════════════════════════════════════════
    # GAME LOOP
    # ══════════════════════════════════════════════════════════════════════════

    async def game_loop(self, game: WerewolfGame):
        cid = game.channel.id
        try:
            while True:
                winner = game.check_win()
                if winner:
                    await self.end_game(game, winner)
                    return
                await self.run_night(game)
                winner = game.check_win()
                if winner:
                    await self.end_game(game, winner)
                    return
                await self.run_day(game)
                winner = game.check_win()
                if winner:
                    await self.end_game(game, winner)
                    return
        except asyncio.CancelledError:
            pass
        finally:
            self.games.pop(cid, None)
            self._game_tasks.pop(cid, None)

    # ══════════════════════════════════════════════════════════════════════════
    # NIGHT PHASE
    # ══════════════════════════════════════════════════════════════════════════

    async def run_night(self, game: WerewolfGame):
        game.phase = Phase.NIGHT

        await self.announce(game, embed=discord.Embed(
            title       = f"🌙 Malam ke-{game.day_number}",
            description = (
                "Desa tertidur...\n\n"
                "Setiap role akan mendapat **pesan DM** dengan tombol aksi.\n"
                "**Werewolf, Seer, Doctor, Bodyguard, Witch** — cek DM kalian!\n\n"
                f"⏱️ Waktu aksi: **{NIGHT_ACTION_TIMEOUT} detik**"
            ),
            color=discord.Color.dark_blue(),
        ))

        # ── Wolves ────────────────────────────────────────────────────────────
        wolves  = game.get_wolves()
        targets = [p for p in game.alive if game.roles[p] != Role.WEREWOLF]

        for wolf in wolves:
            other_wolves = [w for w in wolves if w != wolf]
            desc = ""
            if other_wolves:
                desc += f"Sesama serigala: **{', '.join(w.display_name for w in other_wolves)}**\n\n"
            desc += "Pilih target untuk dibunuh malam ini:"

            async def wolf_cb(actor, target, _wolves=wolves):
                ok = game.cast_wolf_vote(actor, target)
                if not ok:
                    return "❌ Target tidak valid."
                game._night_acted.add(actor)
                for w in _wolves:
                    if w != actor:
                        await self.safe_dm(w, content=f"🐺 **{actor.display_name}** memilih **{target.display_name}**.")
                return f"Kamu memilih **{target.display_name}** sebagai target."

            view = NightSelectView(actor=wolf, targets=targets, callback=wolf_cb, placeholder="Pilih target...")
            await self.safe_dm(wolf, embed=make_embed("🐺 Waktunya Berburu!", desc, discord.Color.red()), view=view)

        # ── Seer ──────────────────────────────────────────────────────────────
        seer = game.get_role_member(Role.SEER)
        if seer:
            check_targets = [p for p in game.alive if p != seer]

            async def seer_cb(actor, target):
                if actor in game._night_acted:
                    return "❌ Kamu sudah memeriksa malam ini."
                result = game.seer_check(target)
                game._night_acted.add(actor)
                label = "🐺 **WEREWOLF**" if result else "✅ **Bukan Werewolf**"
                return f"Hasil pemeriksaan **{target.display_name}**: {label}"

            view = NightSelectView(actor=seer, targets=check_targets, callback=seer_cb, placeholder="Periksa siapa?")
            await self.safe_dm(seer, embed=make_embed("🔮 Waktunya Memeriksa!", "Pilih satu pemain untuk diperiksa:", discord.Color.purple()), view=view)

        # ── Doctor ────────────────────────────────────────────────────────────
        doctor = game.get_role_member(Role.DOCTOR)
        if doctor:
            save_targets = [p for p in game.alive if p != game.doctor_last_save]
            extra = f"\n⚠️ Tidak bisa melindungi **{game.doctor_last_save.display_name}** lagi." if game.doctor_last_save else ""

            async def doctor_cb(actor, target):
                if actor in game._night_acted:
                    return "❌ Kamu sudah bertindak malam ini."
                if target == game.doctor_last_save:
                    return "❌ Tidak bisa melindungi orang yang sama dua malam berturut-turut!"
                game.doctor_save = target
                game._night_acted.add(actor)
                return f"Kamu melindungi **{target.display_name}** malam ini."

            view = NightSelectView(actor=doctor, targets=save_targets, callback=doctor_cb, placeholder="Lindungi siapa?")
            await self.safe_dm(doctor, embed=make_embed("💉 Waktunya Melindungi!", f"Pilih satu pemain untuk dilindungi:{extra}", discord.Color.green()), view=view)

        # ── Bodyguard ─────────────────────────────────────────────────────────
        bodyguard = game.get_role_member(Role.BODYGUARD)
        if bodyguard:
            bg_targets = [p for p in game.alive if p != game.bodyguard_last_save]
            extra_bg   = f"\n⚠️ Tidak bisa melindungi **{game.bodyguard_last_save.display_name}** lagi." if game.bodyguard_last_save else ""

            async def bg_cb(actor, target):
                if actor in game._night_acted:
                    return "❌ Kamu sudah bertindak malam ini."
                if target == game.bodyguard_last_save:
                    return "❌ Tidak bisa melindungi orang yang sama dua malam berturut-turut!"
                game.bodyguard_protect = target
                game._night_acted.add(actor)
                return f"Kamu melindungi **{target.display_name}** malam ini.\n⚠️ Jika diserang, **kamu yang akan mati**!"

            view = NightSelectView(actor=bodyguard, targets=bg_targets, callback=bg_cb, placeholder="Jaga siapa?")
            await self.safe_dm(bodyguard, embed=make_embed(
                "🛡️ Waktunya Berjaga!",
                f"Pilih satu pemain untuk dilindungi malam ini.{extra_bg}\n\n"
                "⚠️ Jika target diserang Werewolf, **kamu mati menggantikan mereka**!",
                discord.Color.blue(),
            ), view=view)

        # ── Witch ─────────────────────────────────────────────────────────────
        witch = game.get_role_member(Role.WITCH)
        if witch and (game.witch_heal or game.witch_poison):
            view   = WitchView(actor=witch, game=game)
            potions = []
            if game.witch_heal:   potions.append("💊 Sembuhkan korban malam ini")
            if game.witch_poison: potions.append("☠️ Racuni seseorang")
            await self.safe_dm(witch, embed=make_embed(
                "🧙 Ramuan Tersedia",
                "Kamu bisa menggunakan:\n" + "\n".join(f"• {p}" for p in potions),
                discord.Color.dark_teal(),
            ), view=view)

        await asyncio.sleep(NIGHT_ACTION_TIMEOUT)

        # ── Resolve ───────────────────────────────────────────────────────────
        result = game.resolve_night()

        lines = []

        # Cursed turned
        if result["cursed_turned"]:
            ct = result["cursed_turned"]
            lines.append(f"😈 Seseorang disentuh oleh kegelapan malam ini... *(sesuatu terjadi)*")
            # Notify the newly turned wolf
            await self.safe_dm(ct, embed=make_embed(
                "😈 Kamu Berubah!",
                "Kamu diserang Werewolf, tapi **kutukan dalam dirimu bereaksi**!\n"
                "Kamu sekarang adalah **Werewolf**! Bergabunglah dengan tim serigala.",
                discord.Color.dark_red(),
            ))
            # Notify other wolves
            for wolf in game.get_wolves():
                if wolf != ct:
                    await self.safe_dm(wolf, content=f"😈 **{ct.display_name}** (Cursed) telah berubah menjadi Werewolf dan bergabung dengan tim kalian!")

        # Bodyguard died
        elif result["bodyguard_died"]:
            bg     = result["bodyguard_died"]
            target = result["wolf_target"]
            lines.append(f"🛡️ **{bg.display_name}** tewas melindungi **{target.display_name}** dari serangan malam!")

        # Normal kill / save
        elif result["saved"] and result["wolf_target"]:
            lines.append("✨ Seseorang diselamatkan malam ini! Tidak ada yang mati.")
        elif result["killed"]:
            lines.append(f"💀 **{result['killed'].display_name}** ditemukan tewas di pagi hari!")
        else:
            lines.append("☀️ Tidak ada korban malam ini!")

        # Witch poison
        if result["poisoned"]:
            lines.append(f"☠️ **{result['poisoned'].display_name}** mati diracuni!")

        await self.announce(game, embed=discord.Embed(
            title       = "🌅 Fajar Tiba",
            description = "\n".join(lines),
            color       = discord.Color.orange(),
        ))

        # Hunter triggers
        newly_dead = [d for d in [result["killed"], result["poisoned"], result["bodyguard_died"]] if d]
        for dead in newly_dead:
            if game.roles.get(dead) == Role.HUNTER:
                await self._trigger_hunter(game, dead)

    # ══════════════════════════════════════════════════════════════════════════
    # DAY PHASE
    # ══════════════════════════════════════════════════════════════════════════

    async def run_day(self, game: WerewolfGame):
        game.phase = Phase.DAY
        alive_str  = game.alive_list_str()

        await self.announce(game, embed=discord.Embed(
            title       = f"☀️ Hari ke-{game.day_number}",
            description = (
                f"Diskusikan siapa yang Werewolf!\n\n"
                f"**Pemain hidup:**\n{alive_str}\n\n"
                f"⏱️ Diskusi selama **{DAY_DISCUSSION_TIME} detik**..."
            ),
            color=discord.Color.yellow(),
        ))
        await asyncio.sleep(DAY_DISCUSSION_TIME)

        # ── Voting ────────────────────────────────────────────────────────────
        game.phase = Phase.VOTING
        game.votes = {}

        view     = VoteView(game)
        vote_msg = await game.channel.send(embed=view.vote_embed(), view=view)

        await asyncio.sleep(VOTE_TIMEOUT)

        for child in view.children:
            child.disabled = True
        try:
            await vote_msg.edit(view=view)
        except Exception:
            pass

        # ── Resolve ───────────────────────────────────────────────────────────
        eliminated = game.resolve_vote()
        game.phase = Phase.NIGHT

        if eliminated:
            role = game.roles[eliminated]
            info = ROLE_INFO[role]

            # Jester wins!
            if role == Role.JESTER:
                await self.announce(game, embed=discord.Embed(
                    title       = "🃏 JESTER MENANG!",
                    description = (
                        f"**{eliminated.display_name}** berhasil diperdaya desa untuk mengeksekusinya!\n"
                        f"Desa tertipu oleh sang Jester! 🎭\n\n"
                        f"Game berakhir — **{eliminated.display_name}** adalah pemenangnya!"
                    ),
                    color=discord.Color.from_rgb(255, 215, 0),
                ))
                await self.end_game(game, f"Jester:{eliminated.display_name}")
                return

            await self.announce(game, embed=discord.Embed(
                title       = "⚖️ Eksekusi!",
                description = (
                    f"Desa mengeksekusi **{eliminated.display_name}**!\n"
                    f"Role-nya: {info['emoji']} **{role.value}**"
                ),
                color=discord.Color.dark_red(),
            ))
            if role == Role.HUNTER:
                await self._trigger_hunter(game, eliminated)
        else:
            await self.announce(game, embed=make_embed(
                "🤝 Seri!", "Voting seri — tidak ada yang dieksekusi.", discord.Color.greyple()
            ))

    # ══════════════════════════════════════════════════════════════════════════
    # HUNTER
    # ══════════════════════════════════════════════════════════════════════════

    async def _trigger_hunter(self, game: WerewolfGame, hunter: discord.Member):
        if not game.alive:
            return
        game._pending_hunter = hunter
        await self.announce(game, embed=make_embed(
            "🏹 Hunter Mati!",
            f"**{hunter.display_name}** adalah Hunter! Dia punya **30 detik** untuk menembak.\nCek DM kamu!",
            discord.Color.orange(),
        ))
        view = HunterView(hunter=hunter, game=game, cog=self)
        await self.safe_dm(hunter, embed=make_embed(
            "🏹 Tembak Sebelum Mati!", "Pilih satu pemain untuk ditembak sebelum kamu mati:", discord.Color.orange()
        ), view=view)
        await asyncio.sleep(30)
        game._pending_hunter = None

    # ══════════════════════════════════════════════════════════════════════════
    # END GAME
    # ══════════════════════════════════════════════════════════════════════════

    async def end_game(self, game: WerewolfGame, winner: str):
        game.phase = Phase.ENDED
        cid        = game.channel.id

        # ── Determine winners ──────────────────────────────────────────────────
        jester_win  = winner.startswith("Jester:")
        wolf_win    = winner == "Werewolves"
        jester_name = winner.split(":", 1)[1] if jester_win else None

        lines = []
        for p in game.players:
            role   = game.roles[p]
            info   = ROLE_INFO[role]
            status = "✅" if p in game.alive else "💀"
            lines.append(f"{status} {p.display_name} — {info['emoji']} **{role.value}**")

        if jester_win:
            color = discord.Color.from_rgb(255, 215, 0)
            title = f"🃏 {jester_name} (Jester) Menang!"
        elif wolf_win:
            color = discord.Color.red()
            title = "🐺 Werewolves Menang!"
        else:
            color = discord.Color.green()
            title = "🏘️ Villagers Menang!"

        embed = discord.Embed(title=title, description="\n".join(lines), color=color)
        embed.set_footer(text="Gunakan /ww_create untuk main lagi!")
        await self.announce(game, embed=embed)

        # ── WowoCash rewards ──────────────────────────────────────────────────
        try:
            from economy.wowocash import award_game_end
            first_dead = game.dead[0] if game.dead else None
            players_result = []
            for p in game.players:
                role = game.roles[p]
                is_alive = p in game.alive

                if jester_win:
                    p_won = (role == Role.JESTER and p.display_name == jester_name)
                elif wolf_win:
                    p_won = (role == Role.WEREWOLF)
                else:
                    p_won = (role != Role.WEREWOLF and role != Role.JESTER)

                players_result.append({
                    "user_id":       p.id,
                    "username":      p.display_name,
                    "won":           p_won and not jester_win,
                    "survived":      is_alive,
                    "is_jester_win": jester_win and role == Role.JESTER,
                    "is_first_blood": p == first_dead,
                })

            awards = award_game_end(players_result)

            reward_lines = []
            for a in sorted(awards, key=lambda x: x["awarded"], reverse=True):
                reward_lines.append(f"**{a['username']}** +{a['awarded']:,} 💰 ({', '.join(a['breakdown'])})")

            reward_embed = discord.Embed(
                title       = "💰 WowoCash Rewards",
                description = "\n".join(reward_lines),
                color       = discord.Color.from_rgb(255, 193, 7),
            )
            await self.announce(game, embed=reward_embed)
        except Exception as e:
            print(f"[WowoCash] Error awarding game end: {e}")

        task = self._game_tasks.pop(cid, None)
        if task and not task.done():
            task.cancel()
        self.games.pop(cid, None)


async def setup(bot: commands.Bot):
    await bot.add_cog(Werewolf(bot))