"""Busca de lugares e geocodificação reversa (OpenStreetMap, serviços gratuitos).

- Busca: Photon (komoot), que encontra estabelecimentos (bares, restaurantes,
  museus...) pelo nome e prioriza resultados perto de um ponto. Se não achar
  nada, tenta o Nominatim.
- Clique no mapa: Nominatim (reverso), para sugerir nome e endereço.

Os resultados ficam em cache para não repetir consultas.
"""

import re
import urllib.parse
import urllib.request

import streamlit as st
from geopy.exc import GeopyError
from geopy.geocoders import Nominatim, Photon

USER_AGENT = "locais-app"

EMOJI_TIPO = {
    "bar": "🍺", "pub": "🍺", "biergarten": "🍺",
    "restaurant": "🍽️", "fast_food": "🍔", "food_court": "🍽️",
    "cafe": "☕", "ice_cream": "🍦", "bakery": "🥐", "pastry": "🥐",
    "nightclub": "🪩", "theatre": "🎭", "cinema": "🎬", "arts_centre": "🎨",
    "museum": "🏛️", "gallery": "🖼️", "attraction": "📸", "viewpoint": "📸",
    "park": "🌳", "garden": "🌳", "beach": "🏖️",
    "hotel": "🏨", "hostel": "🏨",
    "marketplace": "🛍️", "mall": "🛍️",
}


@st.cache_resource
def _photon() -> Photon:
    return Photon(user_agent=USER_AGENT, timeout=10)


@st.cache_resource
def _nominatim() -> Nominatim:
    return Nominatim(user_agent=USER_AGENT, timeout=10)


def _nome_curto(endereco: str) -> str:
    """Primeira parte do endereço que não seja só o número do prédio."""
    partes = [p.strip() for p in endereco.split(",") if p.strip()]
    for p in partes:
        if not p.replace("-", "").isdigit():
            return p
    return partes[0] if partes else ""


def _do_photon(loc) -> dict:
    p = loc.raw.get("properties", {})
    rua = " ".join(x for x in [p.get("street"), p.get("housenumber")] if x)
    partes = [rua, p.get("district") or p.get("locality"), p.get("city"), p.get("state"), p.get("country")]
    vistos, endereco = set(), []
    for parte in partes:
        if parte and parte not in vistos:
            vistos.add(parte)
            endereco.append(parte)
    nome = p.get("name") or (endereco[0] if endereco else "Local")
    regiao = ", ".join(x for x in [p.get("district"), p.get("city")] if x)
    return {
        "nome": nome,
        "endereco": ", ".join(endereco),
        "regiao": regiao or p.get("country", ""),
        "emoji": EMOJI_TIPO.get(p.get("osm_value", ""), "📍"),
        "lat": loc.latitude,
        "lng": loc.longitude,
    }


def _do_nominatim(loc) -> dict:
    raw = loc.raw or {}
    end = raw.get("address", {})
    cidade = end.get("city") or end.get("town") or end.get("village") or end.get("state")
    regiao = ", ".join(x for x in [cidade, end.get("country")] if x)
    return {
        "nome": raw.get("name") or _nome_curto(loc.address),
        "endereco": loc.address,
        "regiao": regiao,
        "emoji": EMOJI_TIPO.get(raw.get("type", ""), "📍"),
        "lat": loc.latitude,
        "lng": loc.longitude,
        "importancia": float(raw.get("importance") or 0),
    }


# acima disso, um resultado do Nominatim é um lugar famoso (Torre Eiffel, Coliseu…)
IMPORTANCIA_FAMOSO = 0.55


def _mesmo_lugar(a: dict, b: dict) -> bool:
    return abs(a["lat"] - b["lat"]) < 0.002 and abs(a["lng"] - b["lng"]) < 0.002


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def buscar(texto: str, perto_lat: float, perto_lng: float) -> list[dict]:
    """Busca lugares combinando dois serviços gratuitos:

    - Photon, com prioridade para perto de (perto_lat, perto_lng): bom para
      bares, restaurantes e estabelecimentos em geral.
    - Nominatim, em português: bom para lugares famosos no mundo todo.
    """
    try:
        photon = [
            _do_photon(r)
            for r in _photon().geocode(
                texto, exactly_one=False, limit=8, location_bias=(perto_lat, perto_lng)
            ) or []
        ]
    except GeopyError:
        photon = []
    try:
        nominatim = [
            _do_nominatim(r)
            for r in _nominatim().geocode(
                texto, exactly_one=False, limit=3, language="pt-BR", addressdetails=True
            ) or []
        ]
    except GeopyError:
        nominatim = []

    famosos = [r for r in nominatim if r["importancia"] >= IMPORTANCIA_FAMOSO][:2]
    outros = [r for r in nominatim if r not in famosos]
    resultado: list[dict] = []
    for r in famosos + photon + outros:
        if not any(_mesmo_lugar(r, x) for x in resultado):
            resultado.append(r)
    return resultado[:8]


# --------------------------------------------------------------------------- #
# Links do Google Maps (para lugares que não estão no OpenStreetMap)
# --------------------------------------------------------------------------- #
_RE_URL = re.compile(r"https?://[^\s<>\"']+")
_HOSTS_GOOGLE = re.compile(r"^(maps\.app\.goo\.gl|goo\.gl|(www\.|maps\.)?google\.[a-z.]+)$")
_NAVEGADOR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
_NUM = r"(-?\d{1,3}\.\d+)"


def link_google(texto: str) -> str | None:
    """Devolve o link do Google Maps contido no texto, se houver."""
    for url in _RE_URL.findall(texto):
        host = urllib.parse.urlparse(url).hostname or ""
        if _HOSTS_GOOGLE.match(host):
            return url
    return None


def _resolver(url: str) -> str:
    """Segue os redirecionamentos de links curtos (maps.app.goo.gl)."""
    req = urllib.request.Request(url, headers={"User-Agent": _NAVEGADOR, "Accept-Language": "pt-BR"})
    with urllib.request.urlopen(req, timeout=15) as r:
        final = r.geturl()
    # página de consentimento de cookies: o destino real vem em ?continue=
    if "consent.google" in final:
        cont = urllib.parse.parse_qs(urllib.parse.urlparse(final).query).get("continue")
        if cont:
            final = cont[0]
    return final


def _coordenadas(url: str) -> tuple[float, float] | None:
    url = urllib.parse.unquote(url)
    for padrao in (rf"!3d{_NUM}!4d{_NUM}", rf"@{_NUM},{_NUM}", rf"[?&](?:q|query|ll|center)={_NUM},\s*{_NUM}"):
        m = re.search(padrao, url)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def de_link_google(url: str, perto_lat: float, perto_lng: float) -> dict | None:
    """Tenta extrair nome e posição de um link do Google Maps.

    Devolve um resultado no mesmo formato de `buscar`, com lat/lng = None se
    só der para descobrir o nome. Devolve None se o link não puder ser lido.
    """
    try:
        final = _resolver(url) if "goo.gl" in url else url
    except Exception:
        return None

    caminho = urllib.parse.urlparse(final)
    m = re.search(r"/maps/place/([^/]+)", caminho.path)
    nome = urllib.parse.unquote_plus(m.group(1)) if m else ""
    q = urllib.parse.parse_qs(caminho.query).get("q", [""])[0].strip()
    if re.fullmatch(rf"{_NUM},\s*{_NUM}", q):
        q = ""  # só coordenadas: elas são lidas abaixo
    if q and not nome:
        # links do app costumam vir como ?q=Nome, Rua X, 123 - Bairro, Cidade...
        nome = q.split(",")[0].strip()
    endereco = q[len(nome):].lstrip(" ,") if nome and q.startswith(nome) else q

    resultado = {"nome": nome or "Local do Google Maps", "endereco": endereco,
                 "regiao": "do Google Maps", "emoji": "📌", "lat": None, "lng": None}

    pos = _coordenadas(final)
    if pos is None:
        # sem coordenadas no link: procura pelo endereço (ou pelo nome)
        for consulta in [c for c in (endereco, q, nome) if c]:
            try:
                achado = _photon().geocode(consulta, exactly_one=True, location_bias=(perto_lat, perto_lng))
            except GeopyError:
                achado = None
            if achado:
                pos = (achado.latitude, achado.longitude)
                break
    if pos:
        resultado["lat"], resultado["lng"] = pos
        if not endereco:
            nome_sugerido, resultado["endereco"] = reverso(*pos)
            if not nome:
                resultado["nome"] = nome_sugerido or resultado["nome"]
    return resultado


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def reverso(lat: float, lng: float) -> tuple[str, str]:
    """Retorna (nome sugerido, endereço) para um ponto clicado no mapa."""
    try:
        r = _nominatim().reverse((lat, lng), language="pt-BR", exactly_one=True)
    except GeopyError:
        return "", ""
    if not r:
        return "", ""
    raw = r.raw or {}
    nome = raw.get("name") or _nome_curto(r.address)
    return nome, r.address
