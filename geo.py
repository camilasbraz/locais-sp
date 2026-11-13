"""Busca de lugares e geocodificação reversa via Nominatim (OpenStreetMap).

O serviço é gratuito, com limite de 1 requisição por segundo; os resultados
ficam em cache para não repetir consultas.
"""

import streamlit as st
from geopy.exc import GeopyError
from geopy.geocoders import Nominatim


@st.cache_resource
def _geocoder() -> Nominatim:
    return Nominatim(user_agent="locais-app", timeout=10)


def _nome_curto(endereco: str) -> str:
    return endereco.split(",")[0].strip()


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def buscar(texto: str) -> list[dict]:
    try:
        resultados = _geocoder().geocode(
            texto, exactly_one=False, limit=5, language="pt-BR"
        )
    except GeopyError:
        return []
    return [
        {
            "nome": _nome_curto(r.address),
            "endereco": r.address,
            "lat": r.latitude,
            "lng": r.longitude,
        }
        for r in (resultados or [])
    ]


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def reverso(lat: float, lng: float) -> tuple[str, str]:
    """Retorna (nome sugerido, endereço) para um ponto clicado no mapa."""
    try:
        r = _geocoder().reverse((lat, lng), language="pt-BR", exactly_one=True)
    except GeopyError:
        return "", ""
    if not r:
        return "", ""
    raw = r.raw or {}
    nome = raw.get("name") or _nome_curto(r.address)
    return nome, r.address
