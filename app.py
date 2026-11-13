"""Locais para visitar: mapa compartilhado de lugares para conhecer."""

import datetime as dt
import uuid

import folium
import streamlit as st
from streamlit_folium import st_folium

import admin
import auth
import geo
import storage

st.set_page_config(page_title="Locais para visitar", page_icon="📍", layout="wide")
st.markdown(
    "<style>.block-container{padding-top:1rem;padding-bottom:0.5rem;}</style>",
    unsafe_allow_html=True,
)

# status -> (rótulo, cor do pino, emoji)
STATUS = {
    "quero_ir": ("Quero ir", "gray", "⚪"),
    "gostei": ("Gostei", "green", "🟢"),
    "nao_gostei": ("Não gostei", "red", "🔴"),
}
SAO_PAULO = [-23.5505, -46.6333]
ALTURA_MAPA = 720
TIPOS_FOTO = ["jpg", "jpeg", "png", "webp", "heic", "heif"]

_ESRI_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/{}/MapServer/tile/{{z}}/{{y}}/{{x}}"
_ESRI = "Tiles &copy; Esri"
_OSM = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
_HOT = _OSM + ", tiles: Humanitarian OSM Team / OSM France"
# Estilos gratuitos e sem chave. Cada estilo tem uma ou mais camadas
# (url, atribuição, zoom máximo com imagem própria); o primeiro é o padrão.
ESTILOS_MAPA = [
    ("Claro com detalhes", [(_ESRI_URL.format("World_Topo_Map"), _ESRI, 18)]),
    ("Minimalista cinza", [
        (_ESRI_URL.format("Canvas/World_Light_Gray_Base"), _ESRI, 16),
        (_ESRI_URL.format("Canvas/World_Light_Gray_Reference"), _ESRI, 16),
    ]),
    ("Escuro", [
        (_ESRI_URL.format("Canvas/World_Dark_Gray_Base"), _ESRI, 16),
        (_ESRI_URL.format("Canvas/World_Dark_Gray_Reference"), _ESRI, 16),
    ]),
    ("Satélite", [
        (_ESRI_URL.format("World_Imagery"), _ESRI, 19),
        (_ESRI_URL.format("Reference/World_Boundaries_and_Places"), _ESRI, 19),
    ]),
    ("Colorido (OpenStreetMap)", [("https://tile.openstreetmap.org/{z}/{x}/{y}.png", _OSM, 19)]),
    ("Pastel (OSM Humanitário)", [("https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png", _HOT, 18)]),
    ("Ruas estilo GPS", [(_ESRI_URL.format("World_Street_Map"), _ESRI, 18)]),
]

# --------------------------------------------------------------------------- #
# Configuração e login
# --------------------------------------------------------------------------- #
faltando = storage.secrets_faltando()
if faltando:
    st.error(
        "O app ainda não está configurado. Faltam estes Secrets: "
        + ", ".join(faltando)
        + ". Veja o README."
    )
    st.stop()

auth.garantir_admin_inicial()
user = auth.exigir_login()

ss = st.session_state
for chave, valor in {
    "modo": "padrao",  # padrao | novo | selecionado | visita | editar
    "sel_id": None,
    "novo": None,
    "centro": SAO_PAULO,
    "zoom": 12,
    "prev_clk": None,
    "prev_obj": None,
    "confirmar_exclusao": False,
    "f_quero_ir": True,
    "f_gostei": True,
    "f_nao_gostei": True,
}.items():
    ss.setdefault(chave, valor)

if "flash" in ss:
    st.toast(ss.pop("flash"))

locais = storage.listar_locais()
por_id = {loc["id"]: loc for loc in locais}


# --------------------------------------------------------------------------- #
# Ações (usadas como callbacks dos botões)
# --------------------------------------------------------------------------- #
def ir_para(lat: float, lng: float, zoom: int = 16) -> None:
    ss.centro = [lat, lng]
    ss.zoom = zoom


def voltar() -> None:
    ss.modo = "padrao"
    ss.sel_id = None
    ss.novo = None
    ss.confirmar_exclusao = False


def selecionar(local_id: str, centralizar: bool = False) -> None:
    ss.modo = "selecionado"
    ss.sel_id = local_id
    ss.novo = None
    ss.confirmar_exclusao = False
    if centralizar and local_id in por_id:
        ir_para(por_id[local_id]["lat"], por_id[local_id]["lng"])


def novo_rascunho(lat: float, lng: float, nome: str = "", endereco: str = "") -> None:
    ss.novo = {"k": uuid.uuid4().hex[:8], "lat": lat, "lng": lng, "nome": nome, "endereco": endereco}
    ss.modo = "novo"
    ss.sel_id = None


def escolher_resultado(r: dict) -> None:
    novo_rascunho(r["lat"], r["lng"], r["nome"], r["endereco"])
    ir_para(r["lat"], r["lng"])
    ss.busca = ""


def mudar_modo(modo: str) -> None:
    ss.modo = modo
    ss.confirmar_exclusao = False


def visivel(loc: dict) -> bool:
    return ss.get(f"f_{loc['status']}", True)


def formatar_data(texto: str) -> str:
    try:
        return dt.date.fromisoformat(texto[:10]).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return texto


def ler_data(texto: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(texto[:10])
    except (ValueError, TypeError):
        return None


def local_no_ponto(lat: float, lng: float) -> dict | None:
    candidatos = [
        (abs(loc["lat"] - lat) + abs(loc["lng"] - lng), loc)
        for loc in locais
        if visivel(loc)
    ]
    if not candidatos:
        return None
    dist, loc = min(candidatos, key=lambda c: c[0])
    return loc if dist < 1e-4 else None


# --------------------------------------------------------------------------- #
# Mapa (área principal)
# --------------------------------------------------------------------------- #
mapa = folium.Map(location=SAO_PAULO, zoom_start=12, control_scale=True, tiles=None, max_zoom=19)
for i, (nome_estilo, camadas) in enumerate(ESTILOS_MAPA):
    # cada estilo é um grupo "base" (overlay=False): o seletor troca o grupo inteiro
    grupo = folium.FeatureGroup(name=nome_estilo, overlay=False, show=(i == 0))
    for url, atribuicao, zoom_nativo in camadas:
        folium.TileLayer(
            tiles=url, attr=atribuicao, max_zoom=19, max_native_zoom=zoom_nativo
        ).add_to(grupo)
    grupo.add_to(mapa)
folium.LayerControl(position="topright", collapsed=True).add_to(mapa)
pinos = folium.FeatureGroup(name="locais")
for loc in locais:
    if not visivel(loc):
        continue
    _, cor, _ = STATUS.get(loc["status"], STATUS["quero_ir"])
    folium.Marker(
        [loc["lat"], loc["lng"]],
        tooltip=f"{loc['nome']} · por {loc['criado_por']}",
        icon=folium.Icon(color=cor, icon="map-marker", prefix="fa"),
    ).add_to(pinos)
if ss.modo == "novo" and ss.novo:
    folium.Marker(
        [ss.novo["lat"], ss.novo["lng"]],
        tooltip="Novo local (ainda não salvo)",
        icon=folium.Icon(color="blue", icon="plus", prefix="fa"),
    ).add_to(pinos)

saida = st_folium(
    mapa,
    key="mapa",
    feature_group_to_add=pinos,
    center=ss.centro,
    zoom=ss.zoom,
    height=ALTURA_MAPA,
    use_container_width=True,
    returned_objects=["last_clicked", "last_object_clicked", "last_object_clicked_count"],
) or {}


def _ponto(p: dict | None) -> tuple[float, float] | None:
    if not p or p.get("lat") is None:
        return None
    return round(p["lat"], 6), round(p["lng"], 6)


clique_pino = _ponto(saida.get("last_object_clicked"))
clique_mapa = _ponto(saida.get("last_clicked"))
# o contador muda a cada clique em pino, mesmo que seja o mesmo pino de novo
assinatura_pino = (saida.get("last_object_clicked_count"), clique_pino)

if clique_pino and assinatura_pino != ss.prev_obj:
    # clicou num pino: seleciona o local
    ss.prev_obj = assinatura_pino
    ss.prev_clk = clique_mapa
    alvo = local_no_ponto(*clique_pino)
    if alvo:
        selecionar(alvo["id"])
        st.rerun()
elif clique_mapa and clique_mapa != ss.prev_clk:
    # clicou numa área vazia: começa um novo local ali
    ss.prev_clk = clique_mapa
    with st.spinner("Buscando o endereço…"):
        nome, endereco = geo.reverso(*clique_mapa)
    novo_rascunho(clique_mapa[0], clique_mapa[1], nome, endereco)
    st.rerun()


# --------------------------------------------------------------------------- #
# Painéis do sidebar
# --------------------------------------------------------------------------- #
def painel_padrao() -> None:
    busca = st.text_input(
        "🔎 Buscar lugar",
        key="busca",
        placeholder="Ex.: Bar Brahma, Pinacoteca, Torre Eiffel",
    )
    if busca.strip():
        lat, lng = ss.centro
        with st.spinner("Buscando…"):
            # prioriza resultados perto da última região vista no mapa
            resultados = geo.buscar(busca.strip(), round(lat, 2), round(lng, 2))
        if not resultados:
            st.info("Nada encontrado. Tente outro nome, o nome + bairro, ou clique no mapa.")
        for i, r in enumerate(resultados):
            rotulo = f"{r['emoji']} {r['nome']}" + (f" · {r['regiao']}" if r["regiao"] else "")
            st.button(
                rotulo,
                key=f"res_{i}",
                help=r["endereco"],
                on_click=escolher_resultado,
                args=(r,),
            )
    st.caption("Dica: nome + bairro ajuda (ex.: \"Bar Pinheiros\"). Ou clique direto no mapa.")

    st.divider()
    contagem = {s: sum(1 for loc in locais if loc["status"] == s) for s in STATUS}
    for s, (rotulo, _, emoji) in STATUS.items():
        st.checkbox(f"{emoji} {rotulo} ({contagem[s]})", key=f"f_{s}")

    lista = sorted((loc for loc in locais if visivel(loc)), key=lambda x: x["nome"].lower())
    with st.expander(f"Lista de locais ({len(lista)})"):
        if not lista:
            st.caption("Nenhum local ainda.")
        for loc in lista:
            emoji = STATUS.get(loc["status"], STATUS["quero_ir"])[2]
            st.button(
                f"{emoji} {loc['nome']}",
                key=f"lista_{loc['id']}",
                on_click=selecionar,
                args=(loc["id"], True),
            )


def painel_novo() -> None:
    n = ss.novo
    st.subheader("Novo local")
    with st.form(f"form_novo_{n['k']}"):
        nome = st.text_input("Nome", value=n["nome"], key=f"nome_{n['k']}")
        endereco = st.text_area(
            "Endereço / observação", value=n["endereco"], height=90, key=f"end_{n['k']}"
        )
        salvar = st.form_submit_button("💾 Salvar", type="primary")
    if salvar:
        if not nome.strip():
            st.error("Dê um nome para o local.")
        else:
            novo_id = storage.criar_local(nome, endereco, n["lat"], n["lng"], user["usuario"])
            selecionar(novo_id)
            ss.flash = "Local salvo!"
            st.rerun()
    st.button("Cancelar", on_click=voltar)
    st.caption(f"Coordenadas: {n['lat']:.5f}, {n['lng']:.5f}")


def galeria(fotos: list[str]) -> None:
    colunas = st.columns(2)
    for i, foto_id in enumerate(fotos):
        with colunas[i % 2]:
            try:
                st.image(storage.baixar_foto(foto_id))
            except Exception:
                st.caption("Foto indisponível")


def form_avaliacao(loc: dict, edicao: bool) -> None:
    k = f"{loc['id']}_{ss.modo}"
    opcoes = ["gostei", "nao_gostei"] + (["quero_ir"] if edicao else [])
    indice = opcoes.index(loc["status"]) if edicao and loc["status"] in opcoes else None
    data_atual = ler_data(loc["visitado_em"])
    if data_atual is None and not edicao:
        data_atual = dt.date.today()

    with st.form(f"form_av_{k}"):
        if edicao:
            nome = st.text_input("Nome", value=loc["nome"], key=f"n_{k}")
            endereco = st.text_area("Endereço / observação", value=loc["endereco"], height=90, key=f"e_{k}")
        status = st.radio(
            "Como foi?",
            opcoes,
            index=indice,
            format_func=lambda s: f"{STATUS[s][2]} {STATUS[s][0]}",
            horizontal=True,
            key=f"s_{k}",
        )
        comentario = st.text_area("Comentário (opcional)", value=loc["comentario"], key=f"c_{k}")
        visitado_em = st.date_input(
            "Quando você foi? (opcional)", value=data_atual, format="DD/MM/YYYY", key=f"d_{k}"
        )
        remover = []
        if edicao and loc["fotos"]:
            remover = st.multiselect(
                "Remover fotos",
                loc["fotos"],
                format_func=lambda f: f"Foto {loc['fotos'].index(f) + 1}",
                key=f"r_{k}",
            )
        novas = st.file_uploader(
            "Adicionar fotos (opcional)", type=TIPOS_FOTO, accept_multiple_files=True, key=f"f_{k}"
        )
        salvar = st.form_submit_button("💾 Salvar", type="primary")
    st.button("Cancelar", on_click=mudar_modo, args=("selecionado",), key=f"cancel_{k}")

    if not salvar:
        return
    if status is None:
        st.error("Escolha se você gostou ou não.")
        return
    if edicao and not nome.strip():
        st.error("O nome não pode ficar vazio.")
        return

    with st.spinner("Salvando…"):
        fotos = [f for f in loc["fotos"] if f not in remover]
        for arq in novas or []:
            try:
                dados = storage.preparar_foto(arq.getvalue())
            except Exception:
                st.warning(f"Não consegui abrir a imagem {arq.name}; ela foi ignorada.")
                continue
            fotos.append(storage.enviar_foto(dados, f"{loc['id']}_{uuid.uuid4().hex[:8]}.jpg"))

        campos = {
            "status": status,
            "comentario": comentario.strip(),
            "visitado_em": visitado_em.isoformat() if visitado_em and status != "quero_ir" else "",
            "fotos": fotos,
        }
        if edicao:
            campos["nome"] = nome.strip()
            campos["endereco"] = endereco.strip()
        storage.atualizar_local(loc["id"], campos, user["usuario"])
        for f in remover:
            storage.apagar_foto(f)

    ss.modo = "selecionado"
    ss.flash = "Salvo!"
    st.rerun()


def painel_local() -> None:
    loc = por_id.get(ss.sel_id)
    if not loc:
        voltar()
        st.rerun()
    rotulo, _, emoji = STATUS.get(loc["status"], STATUS["quero_ir"])

    st.button("← Voltar", on_click=voltar)
    st.subheader(loc["nome"])
    st.markdown(f"{emoji} **{rotulo}**")
    if loc["endereco"]:
        st.caption(loc["endereco"])
    st.caption(f"Adicionado por {loc['criado_por']} em {formatar_data(loc['criado_em'])}")

    if ss.modo == "visita":
        form_avaliacao(loc, edicao=False)
        return
    if ss.modo == "editar":
        form_avaliacao(loc, edicao=True)
        return

    if loc["status"] == "quero_ir":
        st.button("✅ Já visitei", type="primary", on_click=mudar_modo, args=("visita",))
    else:
        if loc["visitado_em"]:
            st.write(f"Visitado em {formatar_data(loc['visitado_em'])}")
        if loc["comentario"]:
            st.info(loc["comentario"], icon="💬")
        if loc["fotos"]:
            galeria(loc["fotos"])
        st.caption(f"Avaliado por {loc['atualizado_por']}")

    c1, c2 = st.columns(2)
    c1.button("✏️ Editar", on_click=mudar_modo, args=("editar",))
    if c2.button("🗑️ Excluir"):
        ss.confirmar_exclusao = True
    if ss.confirmar_exclusao:
        st.warning(f"Excluir **{loc['nome']}** e as fotos dele? Isso não pode ser desfeito.")
        a, b = st.columns(2)
        if a.button("Sim, excluir", type="primary"):
            with st.spinner("Excluindo…"):
                storage.excluir_local(loc["id"])
            voltar()
            ss.flash = "Local excluído."
            st.rerun()
        if b.button("Não"):
            ss.confirmar_exclusao = False
            st.rerun()


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown("### 📍 Locais para visitar")
    c1, c2 = st.columns([3, 1])
    c1.caption(f"Olá, **{user['nome']}**")
    c2.button("Sair", on_click=auth.sair)

    if ss.modo == "novo" and ss.novo:
        painel_novo()
    elif ss.modo in ("selecionado", "visita", "editar") and ss.sel_id:
        painel_local()
    else:
        painel_padrao()

    st.divider()
    admin.secao_minha_senha(user)
    admin.secao_admin(user)
