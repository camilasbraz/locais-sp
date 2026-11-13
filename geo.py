"""Busca de lugares e geocodificação reversa (OpenStreetMap, serviços gratuitos).

- Busca: Photon (komoot), que encontra estabelecimentos (bares, restaurantes,
  museus...) pelo nome e prioriza resultados perto de um ponto. Se não achar
  nada, tenta o Nominatim.
- Clique no mapa: Nominatim (reverso), para sugerir nome e endereço.

Os resultados ficam em cache para não repetir consultas.
"""

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
    return endereco.split(",")[0].strip()


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
