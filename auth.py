"""Login por usuário e senha (senhas guardadas com hash bcrypt)."""

import time

import bcrypt
import streamlit as st

import storage

MAX_TENTATIVAS = 5
BLOQUEIO_SEG = 5 * 60
SENHA_MIN = 8

# hash qualquer, usado para gastar o mesmo tempo quando o usuário não existe
_HASH_FALSO = bcrypt.hashpw(b"x", bcrypt.gensalt()).decode()


@st.cache_resource
def _tentativas() -> dict:
    """Falhas de login por usuário, compartilhadas entre todas as sessões."""
    return {}


def normalizar(usuario: str) -> str:
    return usuario.strip().lower()


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def senha_confere(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), senha_hash.encode())
    except ValueError:
        return False


def problema_na_senha(senha: str) -> str | None:
    if len(senha) < SENHA_MIN:
        return f"A senha precisa ter pelo menos {SENHA_MIN} caracteres."
    if len(senha.encode()) > 72:  # limite do bcrypt
        return "A senha é longa demais (máximo de 72 caracteres)."
    return None


def garantir_admin_inicial() -> None:
    if storage.listar_usuarios():
        return
    usuario = normalizar(st.secrets["ADMIN_USUARIO"])
    storage.criar_usuario(
        usuario, usuario, hash_senha(st.secrets["ADMIN_SENHA_INICIAL"]), admin=True
    )


def usuario_logado() -> dict | None:
    usuario = st.session_state.get("usuario")
    if not usuario:
        return None
    registro = storage.obter_usuario(usuario)
    if not registro or registro["ativo"] != "TRUE":
        st.session_state.pop("usuario", None)
        return None
    return registro


def _tela_login() -> None:
    _, meio, _ = st.columns([1, 1.2, 1])
    with meio:
        st.title("📍 Locais para visitar")
        with st.form("login"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Entrar", type="primary")
        if not entrar:
            return

        usuario = normalizar(usuario)
        falhas, bloqueado_ate = _tentativas().get(usuario, (0, 0.0))
        if time.time() < bloqueado_ate:
            minutos = int((bloqueado_ate - time.time()) // 60) + 1
            st.error(f"Muitas tentativas erradas. Tente de novo em {minutos} min.")
            return

        registro = storage.obter_usuario(usuario)
        ok = senha_confere(senha, registro["senha_hash"] if registro else _HASH_FALSO)
        if ok and registro and registro["ativo"] == "TRUE":
            _tentativas().pop(usuario, None)
            st.session_state["usuario"] = usuario
            st.rerun()

        time.sleep(1)
        falhas += 1
        if falhas >= MAX_TENTATIVAS:
            _tentativas()[usuario] = (0, time.time() + BLOQUEIO_SEG)
        else:
            _tentativas()[usuario] = (falhas, 0.0)
        st.error("Usuário ou senha incorretos.")


def exigir_login() -> dict:
    """Devolve o usuário logado ou mostra a tela de login e para o script."""
    registro = usuario_logado()
    if registro:
        return registro
    _tela_login()
    st.stop()


def sair() -> None:
    for chave in list(st.session_state.keys()):
        del st.session_state[chave]
