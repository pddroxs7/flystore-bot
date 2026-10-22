import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import json
import re
import os

load_dotenv()

# ── config ───────────────────────────────────────────────────────────────────
BOT_TOKEN       = os.getenv("BOT_TOKEN")
GUILD_ID        = int(os.getenv("GUILD_ID"))
CANAL_PUBLICO   = int(os.getenv("CANAL_PUBLICO_ID"))
CANAL_ADM       = int(os.getenv("CANAL_ADM_ID"))
CANAL_VIDEOS    = int(os.getenv("CANAL_VIDEOS_ID"))
DIVULGADOR_ROLE = int(os.getenv("DIVULGADOR_ROLE"))
CARGOS_ADM      = [int(x) for x in os.getenv("CARGOS_ADM", "").split(",") if x]

LOJA          = "FLY Store"
COOLDOWN_DIAS = 7

COOLDOWN_FILE  = "cooldowns.json"
PENDENTES_FILE = "pendentes.json"
AVALIACOES_FILE = "avaliacoes.json"

VAGAS_COLOR    = 0x9B59B6
APROVADO_COLOR = 0x9B59B6
RECUSADO_COLOR = 0xED4245
PENDENTE_COLOR = 0x9B59B6
ADM_COLOR      = 0x9B59B6
VIDEO_COLOR    = 0x9B59B6

ESTRELAS = {1: "★☆☆☆☆", 2: "★★☆☆☆", 3: "★★★☆☆", 4: "★★★★☆", 5: "★★★★★"}

# emojis customizados FLY Store — botões
E_APROVAR    = discord.PartialEmoji(name="fly_aprovar",    id=1562539930834575431)
E_RECUSAR    = discord.PartialEmoji(name="fly_recusar",    id=1562540025604997140)
E_REVOGAR    = discord.PartialEmoji(name="fly_revogar",    id=1562540475196375161)
E_PENDENTES  = discord.PartialEmoji(name="fly_pendentes",  id=1562540566837723196)
E_CANDIDATAR = discord.PartialEmoji(name="fly_candidatar", id=1562540662740615250)
E_HISTORICO  = discord.PartialEmoji(name="fly_historico",  id=1562540782404116601)
E_LISTAR     = discord.PartialEmoji(name="fly_listar",     id=1562541006161973339)
E_STAR       = discord.PartialEmoji(name="fly_star",       id=1562541077209288844)

# emojis customizados FLY Store — texto
EM_REQ  = "<:fly_requisitos:1562642165702860811>"
EM_BEN  = "<:fly_beneficios:1562642296519004230>"
EM_CAN  = "<:fly_candidatura:1562642565688205352>"
EM_ITEM = "<:fly_item:1562642664128512010>"
EM_AVI  = "<:fly_aviso:1562642748438351883>"
EM_KEY  = "<:fly_key:1562642840222171186>"

YOUTUBE_RE = re.compile(
    r"(https?://)?(www\.)?"
    r"(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)"
    r"([\w\-]{11})"
)
TIKTOK_RE = re.compile(
    r"(https?://)?(www\.)?tiktok\.com/@[\w\.\-]+/video/\d+"
)

VAGAS_MSG = (
    f"## **Vagas de Divulgador · {LOJA}**\n\n"
    f"{EM_REQ} **REQUISITOS**\n"
    f"{EM_ITEM} **Conta no TikTok ou YouTube disponível para Live**\n"
    f"{EM_ITEM} **Postar vídeos diariamente**\n"
    f"{EM_ITEM} **Mínimo de 500 seguidores**\n"
    f"{EM_ITEM} **Ativo e comprometido com as divulgações**\n"
    f"{EM_ITEM} **Seguir o padrão de divulgação da {LOJA}**\n\n"
    f"{EM_BEN} **BENEFÍCIOS**\n"
    f"{EM_ITEM} **25% de comissão sobre cada venda realizada**\n"
    f"{EM_ITEM} **Suporte exclusivo para divulgadores**\n\n"
    f"{EM_CAN} **COMO SE CANDIDATAR**\n"
    f"{EM_ITEM} **Clique no botão abaixo e preencha o formulário**\n"
    f"{EM_ITEM} **Divulgadores: use o botão Enviar Vídeo para registrar seus vídeos**\n"
    f"{EM_ITEM} **Aguarde a análise do seu perfil**\n\n"
    "─────────────────────────────\n"
    f"{EM_AVI} **Vagas limitadas — candidate-se agora!**\n\n"
    f"{EM_KEY} **NÃO DAMOS KEY DE GRAÇA**\n"
    f"{EM_KEY} **VOCÊ PRECISA TER UMA KEY OU ADQUIRIR NA LOJA**"
)

# ── persistência ──────────────────────────────────────────────────────────────
def carregar_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)

def salvar_json(path: str, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

cooldown_map: dict[str, str] = carregar_json(COOLDOWN_FILE)
pendentes: set[int]           = set(int(k) for k in carregar_json(PENDENTES_FILE).keys())
avaliacoes: dict              = carregar_json(AVALIACOES_FILE)

# ── helpers ───────────────────────────────────────────────────────────────────
def tem_cargo_adm(membro: discord.Member) -> bool:
    return any(r.id in CARGOS_ADM for r in membro.roles)

def detectar_plataforma(texto: str) -> tuple[str | None, str | None]:
    yt = YOUTUBE_RE.search(texto)
    if yt:
        vid_id = yt.group(4)
        return "YouTube", f"https://www.youtube.com/watch?v={vid_id}"
    tt = TIKTOK_RE.search(texto)
    if tt:
        return "TikTok", tt.group(0)
    return None, None

def thumbnail_youtube(video_id: str) -> str:
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

def log_embed_base(titulo: str, cor: int) -> discord.Embed:
    embed = discord.Embed(title=titulo, color=cor)
    embed.set_footer(text=LOJA)
    embed.timestamp = datetime.now(timezone.utc)
    return embed

# ── bot ───────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members         = True
intents.message_content = True

bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ══════════════════════════════════════════════════════════════════════════════
# MODAIS
# ══════════════════════════════════════════════════════════════════════════════

class CandidaturaModal(discord.ui.Modal, title="Candidatura · Divulgador"):

    plataforma = discord.ui.TextInput(
        label="Plataforma(s)",
        placeholder="TikTok, YouTube ou ambos",
        required=True,
        max_length=50,
    )
    link_tiktok = discord.ui.TextInput(
        label="Link do TikTok (coloque — se não tiver)",
        placeholder="https://tiktok.com/@seuperfil",
        required=True,
        max_length=200,
    )
    link_youtube = discord.ui.TextInput(
        label="Link do YouTube (coloque — se não tiver)",
        placeholder="https://youtube.com/@seucanal",
        required=True,
        max_length=200,
    )
    seguidores = discord.ui.TextInput(
        label="Número de seguidores",
        placeholder="Ex: TikTok: 2.400 · YouTube: 850",
        required=True,
        max_length=100,
    )
    disponibilidade = discord.ui.TextInput(
        label="Pode fazer Live e postar diariamente?",
        placeholder="Sim ou Não — explique sua disponibilidade",
        required=True,
        max_length=300,
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild     = interaction.guild
        adm_ch    = guild.get_channel(CANAL_ADM)
        candidato = interaction.user
        agora     = datetime.now(timezone.utc)

        if adm_ch is None:
            await interaction.followup.send("Canal ADM não encontrado. Contate um administrador.", ephemeral=True)
            return

        cooldown_map[str(candidato.id)] = agora.isoformat()
        salvar_json(COOLDOWN_FILE, cooldown_map)
        pendentes.add(candidato.id)
        salvar_json(PENDENTES_FILE, {str(k): 1 for k in pendentes})

        embed = discord.Embed(title=f"Nova Candidatura · {LOJA}", color=PENDENTE_COLOR)
        embed.set_author(
            name=f"{candidato.display_name}  ·  {candidato}",
            icon_url=candidato.display_avatar.url,
        )
        embed.add_field(name="Plataforma(s)",          value=self.plataforma.value,      inline=False)
        embed.add_field(name="TikTok",                 value=self.link_tiktok.value,     inline=False)
        embed.add_field(name="YouTube",                value=self.link_youtube.value,    inline=False)
        embed.add_field(name="Seguidores",             value=self.seguidores.value,      inline=False)
        embed.add_field(name="Disponibilidade / Live", value=self.disponibilidade.value, inline=False)
        embed.set_footer(text=f"{LOJA}  ·  ID: {candidato.id}  ·  Aguardando análise")
        embed.timestamp = agora

        view = AvaliacaoCandidaturaView(candidato_id=candidato.id)
        msg  = await adm_ch.send(embed=embed, view=view)
        view.message = msg
        await msg.edit(view=view)

        await interaction.followup.send(
            f"Candidatura enviada à **{LOJA}**. Aguarde a análise dos ADMs.",
            ephemeral=True,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("Erro ao enviar candidatura. Tente novamente.", ephemeral=True)
        raise error


class RevogarModal(discord.ui.Modal, title="Revogar Divulgador"):

    user_id = discord.ui.TextInput(
        label="ID do usuário",
        placeholder="Ex: 123456789012345678",
        required=True,
        max_length=20,
    )
    motivo = discord.ui.TextInput(
        label="Motivo",
        placeholder="Descreva o motivo da revogação",
        required=True,
        max_length=300,
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not tem_cargo_adm(interaction.user):
            await interaction.followup.send("Sem permissão.", ephemeral=True)
            return

        guild = interaction.guild
        agora = datetime.now(timezone.utc)

        try:
            uid = int(self.user_id.value.strip())
        except ValueError:
            await interaction.followup.send("ID inválido.", ephemeral=True)
            return

        membro = guild.get_member(uid)
        if membro is None:
            await interaction.followup.send("Membro não encontrado no servidor.", ephemeral=True)
            return

        role = guild.get_role(DIVULGADOR_ROLE)
        if role is None or role not in membro.roles:
            await interaction.followup.send(f"{membro.mention} não possui o cargo de Divulgador.", ephemeral=True)
            return

        try:
            await membro.remove_roles(role, reason=f"Revogado por {interaction.user} · {self.motivo.value}")
        except discord.Forbidden:
            await interaction.followup.send("Sem permissão para remover o cargo. Verifique a hierarquia do bot.", ephemeral=True)
            return

        adm_ch = guild.get_channel(CANAL_ADM)
        if adm_ch:
            log = log_embed_base(f"Cargo Revogado · {LOJA}", RECUSADO_COLOR)
            log.add_field(name="Removido",     value=f"{membro.mention}  ·  `{membro.id}`",              inline=False)
            log.add_field(name="Revogado por", value=f"{interaction.user.mention}  ·  `{interaction.user.id}`", inline=False)
            log.add_field(name="Motivo",       value=self.motivo.value,                                   inline=False)
            await adm_ch.send(embed=log)

        try:
            dm = discord.Embed(
                title=f"Cargo Removido · {LOJA}",
                description=(
                    f"Seu cargo de **Divulgador** na **{LOJA}** foi removido.\n\n"
                    f"**Motivo:** {self.motivo.value}"
                ),
                color=RECUSADO_COLOR,
            )
            dm.set_footer(text=LOJA)
            dm.timestamp = agora
            await membro.send(embed=dm)
        except discord.Forbidden:
            pass

        await interaction.followup.send(f"Cargo de Divulgador removido de {membro.mention}.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("Erro ao revogar. Tente novamente.", ephemeral=True)
        raise error


# ══════════════════════════════════════════════════════════════════════════════
# VIEW — AVALIAÇÃO DE CANDIDATURA
# ══════════════════════════════════════════════════════════════════════════════

class AvaliacaoCandidaturaView(discord.ui.View):

    def __init__(self, candidato_id: int):
        super().__init__(timeout=None)
        self.candidato_id = candidato_id
        self.message: discord.Message | None = None

    @discord.ui.button(label="Aprovar", style=discord.ButtonStyle.success, custom_id="btn_aprovar", emoji=E_APROVAR)
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._avaliar(interaction, aprovado=True)

    @discord.ui.button(label="Recusar", style=discord.ButtonStyle.danger, custom_id="btn_recusar", emoji=E_RECUSAR)
    async def recusar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._avaliar(interaction, aprovado=False)

    async def _avaliar(self, interaction: discord.Interaction, aprovado: bool):
        if not tem_cargo_adm(interaction.user):
            await interaction.response.send_message("Sem permissão.", ephemeral=True)
            return

        await interaction.response.defer()

        guild     = interaction.guild
        membro    = guild.get_member(self.candidato_id)
        avaliador = interaction.user
        agora     = datetime.now(timezone.utc)
        embed     = interaction.message.embeds[0]

        if aprovado:
            embed.color = APROVADO_COLOR
            embed.title = f"Candidatura Aprovada · {LOJA}"
            rodape      = f"Aprovado por {avaliador.display_name}  ·  ID: {avaliador.id}"
        else:
            embed.color = RECUSADO_COLOR
            embed.title = f"Candidatura Recusada · {LOJA}"
            rodape      = f"Recusado por {avaliador.display_name}  ·  ID: {avaliador.id}"

        embed.set_footer(text=rodape)
        embed.timestamp = agora

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(embed=embed, view=self)

        pendentes.discard(self.candidato_id)
        salvar_json(PENDENTES_FILE, {str(k): 1 for k in pendentes})

        # log no canal ADM
        adm_ch = guild.get_channel(CANAL_ADM)
        if adm_ch:
            log = log_embed_base(
                f"{'Aprovação' if aprovado else 'Recusa'} · {LOJA}",
                APROVADO_COLOR if aprovado else RECUSADO_COLOR,
            )
            log.add_field(
                name="Candidato",
                value=f"{membro.mention if membro else self.candidato_id}  ·  `{self.candidato_id}`",
                inline=False,
            )
            log.add_field(
                name="Decisão por",
                value=f"{avaliador.mention}  ·  `{avaliador.id}`",
                inline=False,
            )
            await adm_ch.send(embed=log)

        if membro is None:
            await interaction.followup.send("Membro não encontrado — DM não enviada.", ephemeral=True)
            return

        if aprovado:
            role = guild.get_role(DIVULGADOR_ROLE)
            if role:
                try:
                    await membro.add_roles(role, reason=f"Aprovado por {avaliador}")
                except discord.Forbidden:
                    await interaction.followup.send("Sem permissão para adicionar o cargo.", ephemeral=True)

            dm = discord.Embed(
                title=f"Candidatura Aprovada · {LOJA}",
                description=(
                    f"Sua candidatura como **Divulgador** na **{LOJA}** foi aprovada.\n\n"
                    "O cargo já foi atribuído no servidor.\n"
                    "Entre em contato com um ADM para os próximos passos."
                ),
                color=APROVADO_COLOR,
            )
        else:
            dm = discord.Embed(
                title=f"Candidatura não aprovada · {LOJA}",
                description=(
                    f"Sua candidatura na **{LOJA}** não foi aprovada desta vez.\n\n"
                    "Continue crescendo suas redes e candidate-se novamente quando atingir os requisitos."
                ),
                color=RECUSADO_COLOR,
            )

        dm.set_footer(text=LOJA)
        dm.timestamp = agora

        try:
            await membro.send(embed=dm)
        except discord.Forbidden:
            await interaction.followup.send(f"DM não enviada para {membro.mention} — DMs desativadas.", ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW — AVALIAÇÃO DE VÍDEO (ESTRELAS)
# ══════════════════════════════════════════════════════════════════════════════

class AvaliacaoVideoView(discord.ui.View):

    def __init__(self, autor_id: int, link: str, plataforma: str):
        super().__init__(timeout=None)
        self.autor_id   = autor_id
        self.link       = link
        self.plataforma = plataforma

        for nota in range(1, 6):
            self.add_item(EstrelaButton(nota=nota, autor_id=autor_id))


class EstrelaButton(discord.ui.Button):

    def __init__(self, nota: int, autor_id: int):
        super().__init__(
            label=ESTRELAS[nota],
            style=discord.ButtonStyle.secondary,
            custom_id=f"estrela_{autor_id}_{nota}",
            emoji=E_STAR,
            row=0,
        )
        self.nota     = nota
        self.autor_id = autor_id

    async def callback(self, interaction: discord.Interaction):
        if not tem_cargo_adm(interaction.user):
            await interaction.response.send_message("Sem permissão.", ephemeral=True)
            return

        await interaction.response.defer()

        agora     = datetime.now(timezone.utc)
        avaliador = interaction.user
        guild     = interaction.guild
        autor     = guild.get_member(self.autor_id)

        chave = f"{self.autor_id}_{int(agora.timestamp())}"
        avaliacoes[chave] = {
            "autor_id":  self.autor_id,
            "nota":      self.nota,
            "avaliador": avaliador.id,
            "timestamp": agora.isoformat(),
        }
        salvar_json(AVALIACOES_FILE, avaliacoes)

        embed = interaction.message.embeds[0]
        embed.color = APROVADO_COLOR

        embed.fields = [f for f in embed.fields if f.name != "Avaliação"]
        embed.add_field(
            name="Avaliação",
            value=f"{ESTRELAS[self.nota]}  **{self.nota}/5**\npor {avaliador.mention}",
            inline=False,
        )
        embed.set_footer(text=f"{LOJA}  ·  Avaliado em {agora.strftime('%d/%m/%Y %H:%M')} UTC")

        for child in self.view.children:
            child.disabled = True
            if isinstance(child, EstrelaButton) and child.nota == self.nota:
                child.style = discord.ButtonStyle.success

        await interaction.message.edit(embed=embed, view=self.view)

        # log no canal ADM
        adm_ch = guild.get_channel(CANAL_ADM)
        if adm_ch:
            log = log_embed_base(f"Vídeo Avaliado · {LOJA}", APROVADO_COLOR)
            log.add_field(
                name="Divulgador",
                value=f"{autor.mention if autor else self.autor_id}  ·  `{self.autor_id}`",
                inline=False,
            )
            log.add_field(name="Nota",        value=f"{ESTRELAS[self.nota]}  **{self.nota}/5**", inline=True)
            log.add_field(name="Avaliado por", value=avaliador.mention,                          inline=True)
            await adm_ch.send(embed=log)

        if autor:
            try:
                dm = discord.Embed(
                    title=f"Seu vídeo foi avaliado · {LOJA}",
                    description=(
                        f"**Nota:** {ESTRELAS[self.nota]}  **{self.nota}/5**\n"
                        f"**Avaliado por:** {avaliador.display_name}"
                    ),
                    color=APROVADO_COLOR,
                )
                dm.set_footer(text=LOJA)
                dm.timestamp = agora
                await autor.send(embed=dm)
            except discord.Forbidden:
                pass


# ══════════════════════════════════════════════════════════════════════════════
# VIEW — PAINEL PÚBLICO
# ══════════════════════════════════════════════════════════════════════════════

class PainelPublicoView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Candidatar-se",
        style=discord.ButtonStyle.primary,
        custom_id="btn_candidatar",
        emoji=E_CANDIDATAR,
    )
    async def candidatar(self, interaction: discord.Interaction, button: discord.ui.Button):
        membro = interaction.guild.get_member(interaction.user.id)
        role   = interaction.guild.get_role(DIVULGADOR_ROLE)

        if role and role in membro.roles:
            await interaction.response.send_message("Você já possui o cargo de Divulgador.", ephemeral=True)
            return

        if interaction.user.id in pendentes:
            await interaction.response.send_message(
                "Você já possui uma candidatura em análise. Aguarde a decisão dos ADMs.",
                ephemeral=True,
            )
            return

        ultima_str = cooldown_map.get(str(interaction.user.id))
        if ultima_str:
            ultima     = datetime.fromisoformat(ultima_str)
            disponivel = ultima + timedelta(days=COOLDOWN_DIAS)
            agora      = datetime.now(timezone.utc)
            if agora < disponivel:
                restante = disponivel - agora
                dias     = restante.days
                horas    = restante.seconds // 3600
                await interaction.response.send_message(
                    f"Tente novamente em **{dias}d {horas}h**.",
                    ephemeral=True,
                )
                return

        await interaction.response.send_modal(CandidaturaModal())

    @discord.ui.button(
        label="Enviar Vídeo",
        style=discord.ButtonStyle.secondary,
        custom_id="btn_enviar_video",
        emoji=E_STAR,
        row=0,
    )
    async def enviar_video(self, interaction: discord.Interaction, button: discord.ui.Button):
        membro = interaction.guild.get_member(interaction.user.id)
        role   = interaction.guild.get_role(DIVULGADOR_ROLE)

        if role not in (membro.roles if membro else []):
            await interaction.response.send_message(
                "Apenas Divulgadores podem enviar vídeos.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(EnviarVideoModal())


class EnviarVideoModal(discord.ui.Modal, title="Enviar Vídeo · FLY Store"):

    link = discord.ui.TextInput(
        label="Link do vídeo",
        placeholder="https://tiktok.com/@seuperfil/video/... ou https://youtu.be/...",
        required=True,
        max_length=300,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild  = interaction.guild
        membro = guild.get_member(interaction.user.id)
        agora  = datetime.now(timezone.utc)

        plataforma, url = detectar_plataforma(self.link.value)

        if plataforma is None:
            await interaction.followup.send(
                "Link inválido. Envie um link válido do **YouTube** ou **TikTok**.",
                ephemeral=True,
            )
            return

        # confirmação silenciosa pro divulgador
        await interaction.followup.send(
            f"**Vídeo enviado com sucesso.** Link registrado no {plataforma}.",
            ephemeral=True,
        )

        # embed pro canal de vídeos
        videos_ch = guild.get_channel(CANAL_VIDEOS)
        if videos_ch:
            registro = discord.Embed(
                title=f"**Novo Vídeo · {LOJA}**",
                description=f"**{membro.display_name}** postou no **{plataforma}**",
                color=VIDEO_COLOR,
            )
            registro.set_author(
                name=f"{membro.display_name}  ·  {membro}",
                icon_url=membro.display_avatar.url,
            )
            registro.add_field(name="**Plataforma**", value=f"**{plataforma}**", inline=True)
            registro.add_field(name="**Link**",       value=url,                 inline=False)
            if plataforma == "YouTube":
                yt_match = YOUTUBE_RE.search(url)
                if yt_match:
                    registro.set_image(url=thumbnail_youtube(yt_match.group(4)))
            registro.set_footer(text=f"{LOJA}  ·  {agora.strftime('%d/%m/%Y %H:%M')} UTC")
            registro.timestamp = agora
            await videos_ch.send(embed=registro)

        # embed pro canal ADM com estrelas
        adm_ch = guild.get_channel(CANAL_ADM)
        if adm_ch:
            adm_embed = discord.Embed(
                title=f"**Novo Vídeo para Avaliar · {LOJA}**",
                color=PENDENTE_COLOR,
            )
            adm_embed.set_author(
                name=f"{membro.display_name}  ·  {membro}",
                icon_url=membro.display_avatar.url,
            )
            adm_embed.add_field(name="**Plataforma**", value=f"**{plataforma}**", inline=True)
            adm_embed.add_field(name="**Link**",       value=url,                 inline=False)
            if plataforma == "YouTube":
                yt_match = YOUTUBE_RE.search(url)
                if yt_match:
                    adm_embed.set_image(url=thumbnail_youtube(yt_match.group(4)))
            adm_embed.set_footer(text=f"{LOJA}  ·  ID: {membro.id}  ·  Aguardando avaliação")
            adm_embed.timestamp = agora
            view = AvaliacaoVideoView(autor_id=membro.id, link=url, plataforma=plataforma)
            await adm_ch.send(embed=adm_embed, view=view)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("Erro ao enviar vídeo. Tente novamente.", ephemeral=True)
        raise error


# ══════════════════════════════════════════════════════════════════════════════
# VIEW — PAINEL ADM
# ══════════════════════════════════════════════════════════════════════════════

class PainelAdmView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Listar Divulgadores", style=discord.ButtonStyle.secondary, custom_id="btn_listar", emoji=E_LISTAR, row=0)
    async def listar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not tem_cargo_adm(interaction.user):
            await interaction.response.send_message("Sem permissão.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        role  = guild.get_role(DIVULGADOR_ROLE)

        if role is None:
            await interaction.followup.send("Cargo de Divulgador não encontrado.", ephemeral=True)
            return

        membros = [m for m in guild.members if role in m.roles]

        if not membros:
            await interaction.followup.send("Nenhum divulgador ativo no momento.", ephemeral=True)
            return

        paginas = [membros[i:i+20] for i in range(0, len(membros), 20)]

        for idx, pagina in enumerate(paginas):
            embed = discord.Embed(title=f"Divulgadores Ativos · {LOJA}", color=ADM_COLOR)
            embed.description = "\n".join(f"◈  {m.mention}  ·  `{m.id}`" for m in pagina)
            embed.set_footer(text=f"Página {idx+1}/{len(paginas)}  ·  Total: {len(membros)}")
            embed.timestamp = datetime.now(timezone.utc)
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Revogar Divulgador", style=discord.ButtonStyle.danger, custom_id="btn_revogar", emoji=E_REVOGAR, row=0)
    async def revogar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not tem_cargo_adm(interaction.user):
            await interaction.response.send_message("Sem permissão.", ephemeral=True)
            return
        await interaction.response.send_modal(RevogarModal())

    @discord.ui.button(label="Candidaturas Pendentes", style=discord.ButtonStyle.primary, custom_id="btn_pendentes", emoji=E_PENDENTES, row=1)
    async def ver_pendentes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not tem_cargo_adm(interaction.user):
            await interaction.response.send_message("Sem permissão.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        if not pendentes:
            await interaction.followup.send("Nenhuma candidatura pendente.", ephemeral=True)
            return

        guild = interaction.guild
        embed = discord.Embed(title=f"Candidaturas Pendentes · {LOJA}", color=PENDENTE_COLOR)
        linhas = []
        for uid in pendentes:
            m = guild.get_member(uid)
            linhas.append(f"◈  {m.mention if m else uid}  ·  `{uid}`")

        embed.description = "\n".join(linhas)
        embed.set_footer(text=f"Total: {len(pendentes)}  ·  {LOJA}")
        embed.timestamp = datetime.now(timezone.utc)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Histórico de Avaliações", style=discord.ButtonStyle.secondary, custom_id="btn_historico", emoji=E_HISTORICO, row=1)
    async def historico(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not tem_cargo_adm(interaction.user):
            await interaction.response.send_message("Sem permissão.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        if not avaliacoes:
            await interaction.followup.send("Nenhuma avaliação registrada.", ephemeral=True)
            return

        guild   = interaction.guild
        recentes = sorted(avaliacoes.values(), key=lambda x: x["timestamp"], reverse=True)[:20]

        embed = discord.Embed(title=f"Avaliações Recentes · {LOJA}", color=ADM_COLOR)
        linhas = []
        for av in recentes:
            membro    = guild.get_member(av["autor_id"])
            avaliador = guild.get_member(av["avaliador"])
            ts        = datetime.fromisoformat(av["timestamp"]).strftime("%d/%m %H:%M")
            nome      = membro.display_name if membro else f"`{av['autor_id']}`"
            quem      = avaliador.display_name if avaliador else f"`{av['avaliador']}`"
            linhas.append(f"◈  **{nome}** — {ESTRELAS[av['nota']]} por {quem} · {ts}")

        embed.description = "\n".join(linhas)
        embed.set_footer(text=f"Últimas {len(recentes)} avaliações  ·  {LOJA}")
        embed.timestamp = datetime.now(timezone.utc)
        await interaction.followup.send(embed=embed, ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
# DETECÇÃO DE VÍDEO NO CANAL PÚBLICO
# ══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.channel.id == CANAL_PUBLICO:
        guild  = message.guild
        membro = guild.get_member(message.author.id)
        role   = guild.get_role(DIVULGADOR_ROLE)

        # ignora mensagens de quem não é divulgador
        if role not in (membro.roles if membro else []):
            await message.delete()
            try:
                await message.author.send(
                    "Apenas Divulgadores podem enviar links de vídeo neste canal."
                )
            except discord.Forbidden:
                pass
            return

        plataforma, url = detectar_plataforma(message.content)

        if plataforma is None:
            await message.delete()
            try:
                await message.author.send(
                    "Link inválido. Envie um link válido do **YouTube** ou **TikTok** neste canal."
                )
            except discord.Forbidden:
                pass
            return

        agora = datetime.now(timezone.utc)

        # confirmação no canal público
        confirmacao = discord.Embed(
            title=f"Vídeo Registrado · {LOJA}",
            description=f"◈  **{membro.display_name}** enviou um novo vídeo no **{plataforma}**",
            color=VIDEO_COLOR,
        )
        confirmacao.add_field(name="Link", value=url, inline=False)
        confirmacao.set_author(
            name=f"{membro.display_name}  ·  {membro}",
            icon_url=membro.display_avatar.url,
        )

        if plataforma == "YouTube":
            yt_match = YOUTUBE_RE.search(url)
            if yt_match:
                confirmacao.set_image(url=thumbnail_youtube(yt_match.group(4)))

        confirmacao.set_footer(text=f"{LOJA}  ·  {agora.strftime('%d/%m/%Y %H:%M')} UTC")
        confirmacao.timestamp = agora

        await message.delete()
        await message.channel.send(embed=confirmacao)

        # embed de avaliação no canal ADM
        adm_ch = guild.get_channel(CANAL_ADM)
        if adm_ch:
            adm_embed = discord.Embed(
                title=f"Novo Vídeo para Avaliar · {LOJA}",
                color=PENDENTE_COLOR,
            )
            adm_embed.set_author(
                name=f"{membro.display_name}  ·  {membro}",
                icon_url=membro.display_avatar.url,
            )
            adm_embed.add_field(name="Plataforma", value=plataforma, inline=True)
            adm_embed.add_field(name="Link",       value=url,        inline=False)

            if plataforma == "YouTube":
                yt_match = YOUTUBE_RE.search(url)
                if yt_match:
                    adm_embed.set_image(url=thumbnail_youtube(yt_match.group(4)))

            adm_embed.set_footer(text=f"{LOJA}  ·  ID: {membro.id}  ·  Aguardando avaliação")
            adm_embed.timestamp = agora

            view = AvaliacaoVideoView(autor_id=membro.id, link=url, plataforma=plataforma)
            await adm_ch.send(embed=adm_embed, view=view)

        # encaminhamento pro canal de vídeos
        videos_ch = guild.get_channel(CANAL_VIDEOS)
        if videos_ch:
            registro = discord.Embed(
                title=f"Novo Vídeo · {LOJA}",
                description=f"◈  **{membro.display_name}** postou no **{plataforma}**",
                color=VIDEO_COLOR,
            )
            registro.set_author(
                name=f"{membro.display_name}  ·  {membro}",
                icon_url=membro.display_avatar.url,
            )
            registro.add_field(name="Plataforma", value=plataforma, inline=True)
            registro.add_field(name="Link",       value=url,        inline=False)

            if plataforma == "YouTube":
                yt_match = YOUTUBE_RE.search(url)
                if yt_match:
                    registro.set_image(url=thumbnail_youtube(yt_match.group(4)))

            registro.set_footer(text=f"{LOJA}  ·  {agora.strftime('%d/%m/%Y %H:%M')} UTC")
            registro.timestamp = agora
            await videos_ch.send(embed=registro)

        return

    await bot.process_commands(message)


# ══════════════════════════════════════════════════════════════════════════════
# COMANDOS DE SETUP
# ══════════════════════════════════════════════════════════════════════════════

@tree.command(
    name="postar_vagas",
    description="Posta o painel público de vagas no canal atual.",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def postar_vagas(interaction: discord.Interaction):
    embed = discord.Embed(description=VAGAS_MSG, color=VAGAS_COLOR)
    embed.set_footer(text=f"{LOJA}  ·  Clique para se candidatar")
    await interaction.channel.send(embed=embed, view=PainelPublicoView())
    await interaction.response.send_message("Painel público postado.", ephemeral=True)


@tree.command(
    name="postar_painel_adm",
    description="Posta o painel de controle ADM no canal atual.",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def postar_painel_adm(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"**Painel de Controle · {LOJA}**",
        description=(
            f"{EM_REQ} **AÇÕES DISPONÍVEIS**\n\n"
            f"{EM_ITEM} **Listar Divulgadores** — membros com cargo ativo\n"
            f"{EM_ITEM} **Revogar Divulgador** — remove cargo e notifica por DM\n"
            f"{EM_ITEM} **Candidaturas Pendentes** — aguardando análise\n"
            f"{EM_ITEM} **Histórico de Avaliações** — últimas 20 avaliações de vídeo\n\n"
            "─────────────────────────────\n"
            f"{EM_AVI} **Acesso restrito a ADMs e Owner**\n"
            f"{EM_KEY} **Candidaturas e vídeos chegam neste canal automaticamente**"
        ),
        color=ADM_COLOR,
    )
    embed.set_footer(text=f"{LOJA}  ·  Painel de Controle")
    embed.timestamp = datetime.now(timezone.utc)
    await interaction.channel.send(embed=embed, view=PainelAdmView())
    await interaction.response.send_message("Painel ADM postado.", ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
# READY
# ══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    bot.add_view(PainelPublicoView())
    bot.add_view(PainelAdmView())

    try:
        synced = await tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"[OK] {len(synced)} comando(s) sincronizado(s)")
    except Exception as e:
        print(f"[ERRO] sync: {e}")

    print(f"[OK] {bot.user}  ·  {bot.user.id}  ·  {LOJA}")


bot.run(BOT_TOKEN)
