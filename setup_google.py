"""Configuração única: autoriza o app na sua conta Google e cria a planilha e a
pasta de fotos no seu Drive.

Uso (no seu computador, uma vez só):
    1. Coloque o arquivo client_secret.json (baixado do Google Cloud) nesta pasta.
    2. python setup_google.py
    3. Copie o bloco impresso no final para os Secrets do Streamlit Cloud.

O script também grava .streamlit/secrets.toml para você rodar o app localmente.
"""

import getpass
import json
import sys
from pathlib import Path

import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from storage import LOCAIS_COLS, SCOPES, USUARIOS_COLS

PASTA = Path(__file__).parent
CLIENT_SECRET = PASTA / "client_secret.json"
SECRETS_LOCAL = PASTA / ".streamlit" / "secrets.toml"


def main() -> None:
    if not CLIENT_SECRET.exists():
        sys.exit(
            "Não achei o client_secret.json nesta pasta. Baixe-o no Google Cloud "
            "Console (Credenciais > ID do cliente OAuth > Desktop) e tente de novo."
        )

    print("Abrindo o navegador para você autorizar o app na sua conta Google…")
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        sys.exit("O Google não devolveu um refresh token. Rode o script de novo.")

    print("Criando a planilha 'locais-app'…")
    gc = gspread.authorize(creds)
    planilha = gc.create("locais-app")
    aba_locais = planilha.sheet1
    aba_locais.update_title("locais")
    aba_locais.update(range_name="A1", values=[LOCAIS_COLS], value_input_option="RAW")
    aba_locais.freeze(rows=1)
    aba_usuarios = planilha.add_worksheet("usuarios", rows=100, cols=len(USUARIOS_COLS))
    aba_usuarios.update(range_name="A1", values=[USUARIOS_COLS], value_input_option="RAW")
    aba_usuarios.freeze(rows=1)

    print("Criando a pasta 'locais-app-fotos'…")
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    pasta = drive.files().create(
        body={"name": "locais-app-fotos", "mimeType": "application/vnd.google-apps.folder"},
        fields="id",
    ).execute()

    print()
    admin_usuario = input("Escolha seu usuário de admin no app (ex.: camila): ").strip().lower()
    while True:
        senha = getpass.getpass("Senha inicial do admin (mín. 8 caracteres, não aparece ao digitar): ")
        if len(senha) >= 8:
            break
        print("Muito curta, tente de novo.")

    valores = {
        "GOOGLE_CLIENT_ID": creds.client_id,
        "GOOGLE_CLIENT_SECRET": creds.client_secret,
        "GOOGLE_REFRESH_TOKEN": creds.refresh_token,
        "SHEET_ID": planilha.id,
        "FOTOS_FOLDER_ID": pasta["id"],
        "ADMIN_USUARIO": admin_usuario,
        "ADMIN_SENHA_INICIAL": senha,
    }
    # strings JSON são strings TOML válidas
    bloco = "\n".join(f"{k} = {json.dumps(v)}" for k, v in valores.items())

    SECRETS_LOCAL.parent.mkdir(exist_ok=True)
    SECRETS_LOCAL.write_text(bloco + "\n", encoding="utf-8")

    print("\n" + "=" * 70)
    print("Pronto! Planilha e pasta criadas no seu Drive.")
    print(f"Gravei {SECRETS_LOCAL} (para rodar localmente; NÃO suba esse arquivo).")
    print("Cole o bloco abaixo em Streamlit Cloud > seu app > Settings > Secrets:")
    print("=" * 70)
    print(bloco)
    print("=" * 70)


if __name__ == "__main__":
    main()
