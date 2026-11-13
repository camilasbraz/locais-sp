"""Seções do sidebar: trocar a própria senha e gerenciar usuários (admin)."""

import re

import streamlit as st

import auth
import storage

PADRAO_USUARIO = re.compile(r"^[a-z0-9._-]{3,30}$")


def _avisar(msg: str) -> None:
    """Mensagem mostrada como toast depois do próximo rerun."""
    st.session_state["flash"] = msg


def secao_minha_senha(user: dict) -> None:
    with st.expander("🔑 Trocar minha senha"):
        with st.form("minha_senha", clear_on_submit=True):
            atual = st.text_input("Senha atual", type="password")
            nova = st.text_input("Nova senha", type="password")
            confirma = st.text_input("Repita a nova senha", type="password")
            enviar = st.form_submit_button("Trocar senha")
        if not enviar:
            return
        if not auth.senha_confere(atual, user["senha_hash"]):
            st.error("Senha atual incorreta.")
        elif nova != confirma:
            st.error("As senhas novas não são iguais.")
        elif erro := auth.problema_na_senha(nova):
            st.error(erro)
        else:
            storage.atualizar_usuario(user["usuario"], senha_hash=auth.hash_senha(nova))
            st.success("Senha alterada!")


def secao_admin(user: dict) -> None:
    if user["admin"] != "TRUE":
        return
    with st.expander("⚙️ Usuários"):
        usuarios = storage.listar_usuarios()
        for u in usuarios:
            marcas = []
            if u["admin"] == "TRUE":
                marcas.append("admin")
            if u["ativo"] != "TRUE":
                marcas.append("🚫 desativado")
            extra = f" · {' · '.join(marcas)}" if marcas else ""
            st.markdown(f"**{u['nome']}** (`{u['usuario']}`){extra}")

        st.divider()
        st.markdown("**Criar usuário**")
        with st.form("novo_usuario", clear_on_submit=True):
            usuario = st.text_input("Usuário (login)", help="Letras minúsculas, números, ponto, hífen ou _")
            nome = st.text_input("Nome para exibir")
            senha = st.text_input("Senha", type="password")
            eh_admin = st.checkbox("É admin (pode gerenciar usuários)")
            criar = st.form_submit_button("Criar")
        if criar:
            usuario = auth.normalizar(usuario)
            if not PADRAO_USUARIO.match(usuario):
                st.error("Usuário inválido: use 3 a 30 letras minúsculas, números, '.', '-' ou '_'.")
            elif storage.obter_usuario(usuario):
                st.error("Esse usuário já existe.")
            elif erro := auth.problema_na_senha(senha):
                st.error(erro)
            else:
                storage.criar_usuario(usuario, nome, auth.hash_senha(senha), eh_admin)
                _avisar(f"Usuário {usuario} criado.")
                st.rerun()

        st.divider()
        st.markdown("**Gerenciar usuário**")
        escolhido = st.selectbox(
            "Usuário",
            [u["usuario"] for u in usuarios],
            format_func=lambda x: f"{storage.obter_usuario(x)['nome']} ({x})",
            key="admin_escolhido",
        )
        alvo = storage.obter_usuario(escolhido) if escolhido else None
        if not alvo:
            return
        eu_mesmo = alvo["usuario"] == user["usuario"]

        with st.form("redefinir_senha", clear_on_submit=True):
            nova = st.text_input("Nova senha para esse usuário", type="password")
            redefinir = st.form_submit_button("Redefinir senha")
        if redefinir:
            if erro := auth.problema_na_senha(nova):
                st.error(erro)
            else:
                storage.atualizar_usuario(alvo["usuario"], senha_hash=auth.hash_senha(nova))
                _avisar(f"Senha de {alvo['usuario']} redefinida.")
                st.rerun()

        ativo = alvo["ativo"] == "TRUE"
        admin = alvo["admin"] == "TRUE"
        c1, c2 = st.columns(2)
        if c1.button(
            "Desativar" if ativo else "Reativar",
            disabled=eu_mesmo,
            help="Você não pode desativar a si mesma(o)." if eu_mesmo else None,
        ):
            storage.atualizar_usuario(alvo["usuario"], ativo="FALSE" if ativo else "TRUE")
            _avisar(f"{alvo['usuario']} {'desativado' if ativo else 'reativado'}.")
            st.rerun()
        if c2.button(
            "Tirar admin" if admin else "Tornar admin",
            disabled=eu_mesmo,
            help="Você não pode tirar seu próprio acesso de admin." if eu_mesmo else None,
        ):
            storage.atualizar_usuario(alvo["usuario"], admin="FALSE" if admin else "TRUE")
            _avisar(f"Permissões de {alvo['usuario']} atualizadas.")
            st.rerun()
