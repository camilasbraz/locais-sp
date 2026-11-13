"""Acesso aos dados: Google Sheets (locais e usuários) e Google Drive (fotos).

Tudo é gravado como texto (value_input_option="RAW"), para que o formato
regional da planilha (vírgula decimal, datas) não altere os valores e para que
nada digitado no app seja interpretado como fórmula.
"""

import datetime as dt
import io
import threading
import uuid
from zoneinfo import ZoneInfo

import gspread
import streamlit as st
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from PIL import Image, ImageOps

try:  # fotos HEIC (iPhone)
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FUSO = ZoneInfo("America/Sao_Paulo")

LOCAIS_COLS = [
    "id", "nome", "endereco", "lat", "lng", "status", "comentario", "fotos",
    "visitado_em", "criado_por", "criado_em", "atualizado_por", "atualizado_em",
]
USUARIOS_COLS = ["usuario", "nome", "senha_hash", "admin", "ativo", "criado_em"]

SECRETS_OBRIGATORIOS = [
    "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN",
    "SHEET_ID", "FOTOS_FOLDER_ID", "ADMIN_USUARIO", "ADMIN_SENHA_INICIAL",
]

FOTO_LADO_MAX = 1600
FOTO_QUALIDADE = 82


# --------------------------------------------------------------------------- #
# Conexão
# --------------------------------------------------------------------------- #
def secrets_faltando() -> list[str]:
    try:
        return [k for k in SECRETS_OBRIGATORIOS if not st.secrets.get(k)]
    except Exception:  # arquivo de secrets inexistente
        return SECRETS_OBRIGATORIOS


def agora() -> str:
    return dt.datetime.now(FUSO).strftime("%Y-%m-%d %H:%M")


@st.cache_resource
def _credenciais() -> Credentials:
    return Credentials(
        token=None,
        refresh_token=st.secrets["GOOGLE_REFRESH_TOKEN"],
        client_id=st.secrets["GOOGLE_CLIENT_ID"],
        client_secret=st.secrets["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )


@st.cache_resource
def _planilha() -> gspread.Spreadsheet:
    return gspread.authorize(_credenciais()).open_by_key(st.secrets["SHEET_ID"])


@st.cache_resource
def _aba(nome: str) -> gspread.Worksheet:
    return _planilha().worksheet(nome)


@st.cache_resource
def _drive():
    return build("drive", "v3", credentials=_credenciais(), cache_discovery=False)


@st.cache_resource
def _drive_lock() -> threading.Lock:
    # o cliente HTTP do Drive não é thread-safe e o Streamlit atende cada
    # sessão numa thread
    return threading.Lock()


def _ler(aba: str, colunas: list[str]) -> list[dict]:
    return _aba(aba).get_all_records(
        expected_headers=colunas, numericise_ignore=["all"], default_blank=""
    )


def _linha_de(aba: str, chave: str) -> int | None:
    cel = _aba(aba).find(chave, in_column=1)
    return cel.row if cel else None


def _valores(registro: dict, colunas: list[str]) -> list[str]:
    out = []
    for c in colunas:
        v = registro.get(c, "")
        if isinstance(v, list):
            v = ";".join(v)
        out.append("" if v is None else str(v))
    return out


def _gravar_linha(aba: str, linha: int, registro: dict, colunas: list[str]) -> None:
    fim = gspread.utils.rowcol_to_a1(linha, len(colunas))
    _aba(aba).update(
        range_name=f"A{linha}:{fim}",
        values=[_valores(registro, colunas)],
        value_input_option="RAW",
    )


# --------------------------------------------------------------------------- #
# Locais
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=30, show_spinner=False)
def listar_locais() -> list[dict]:
    locais = []
    for r in _ler("locais", LOCAIS_COLS):
        try:
            r["lat"] = float(str(r["lat"]).replace(",", "."))
            r["lng"] = float(str(r["lng"]).replace(",", "."))
        except ValueError:
            continue
        r["fotos"] = [f for f in str(r["fotos"]).split(";") if f]
        locais.append(r)
    return locais


def criar_local(nome: str, endereco: str, lat: float, lng: float, usuario: str) -> str:
    novo = {
        "id": uuid.uuid4().hex,
        "nome": nome.strip(),
        "endereco": endereco.strip(),
        "lat": f"{lat:.6f}",
        "lng": f"{lng:.6f}",
        "status": "quero_ir",
        "comentario": "",
        "fotos": [],
        "visitado_em": "",
        "criado_por": usuario,
        "criado_em": agora(),
        "atualizado_por": usuario,
        "atualizado_em": agora(),
    }
    _aba("locais").append_row(
        _valores(novo, LOCAIS_COLS), value_input_option="RAW", table_range="A1"
    )
    listar_locais.clear()
    return novo["id"]


def atualizar_local(local_id: str, campos: dict, usuario: str) -> None:
    linha = _linha_de("locais", local_id)
    if linha is None:
        raise LookupError("Local não encontrado (pode ter sido excluído).")
    atuais = _aba("locais").row_values(linha)
    registro = dict(zip(LOCAIS_COLS, atuais + [""] * (len(LOCAIS_COLS) - len(atuais))))
    registro.update(campos)
    registro["atualizado_por"] = usuario
    registro["atualizado_em"] = agora()
    _gravar_linha("locais", linha, registro, LOCAIS_COLS)
    listar_locais.clear()


def excluir_local(local_id: str) -> None:
    linha = _linha_de("locais", local_id)
    if linha is None:
        listar_locais.clear()
        return
    atuais = _aba("locais").row_values(linha)
    fotos = atuais[LOCAIS_COLS.index("fotos")] if len(atuais) > 7 else ""
    _aba("locais").delete_rows(linha)
    listar_locais.clear()
    for f in fotos.split(";"):
        if f:
            apagar_foto(f)


# --------------------------------------------------------------------------- #
# Usuários
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=30, show_spinner=False)
def listar_usuarios() -> list[dict]:
    return _ler("usuarios", USUARIOS_COLS)


def obter_usuario(usuario: str) -> dict | None:
    return next((u for u in listar_usuarios() if u["usuario"] == usuario), None)


def criar_usuario(usuario: str, nome: str, senha_hash: str, admin: bool) -> None:
    registro = {
        "usuario": usuario,
        "nome": nome.strip() or usuario,
        "senha_hash": senha_hash,
        "admin": "TRUE" if admin else "FALSE",
        "ativo": "TRUE",
        "criado_em": agora(),
    }
    _aba("usuarios").append_row(
        _valores(registro, USUARIOS_COLS), value_input_option="RAW", table_range="A1"
    )
    listar_usuarios.clear()


def atualizar_usuario(usuario: str, **campos) -> None:
    linha = _linha_de("usuarios", usuario)
    if linha is None:
        raise LookupError("Usuário não encontrado.")
    atuais = _aba("usuarios").row_values(linha)
    registro = dict(zip(USUARIOS_COLS, atuais + [""] * (len(USUARIOS_COLS) - len(atuais))))
    registro.update(campos)
    _gravar_linha("usuarios", linha, registro, USUARIOS_COLS)
    listar_usuarios.clear()


# --------------------------------------------------------------------------- #
# Fotos
# --------------------------------------------------------------------------- #
def preparar_foto(dados: bytes) -> bytes:
    """Corrige a rotação, reduz para no máximo 1600px e salva como JPEG."""
    img = Image.open(io.BytesIO(dados))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((FOTO_LADO_MAX, FOTO_LADO_MAX))
    saida = io.BytesIO()
    img.save(saida, format="JPEG", quality=FOTO_QUALIDADE, optimize=True)
    return saida.getvalue()


def enviar_foto(dados: bytes, nome_arquivo: str) -> str:
    media = MediaIoBaseUpload(io.BytesIO(dados), mimetype="image/jpeg")
    corpo = {"name": nome_arquivo, "parents": [st.secrets["FOTOS_FOLDER_ID"]]}
    with _drive_lock():
        arq = _drive().files().create(body=corpo, media_body=media, fields="id").execute()
    return arq["id"]


@st.cache_data(show_spinner=False, max_entries=200)
def baixar_foto(file_id: str) -> bytes:
    with _drive_lock():
        return _drive().files().get_media(fileId=file_id).execute()


def apagar_foto(file_id: str) -> None:
    try:
        with _drive_lock():
            _drive().files().delete(fileId=file_id).execute()
    except HttpError:
        pass  # já não existe
