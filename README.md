# 📍 Locais para visitar

Mapa compartilhado de lugares para conhecer, feito em Streamlit.

- **Pino cinza**: quero ir.
- **Pino verde**: fui e gostei.
- **Pino vermelho**: fui e não gostei.

Depois de visitar, dá para colocar comentário e fotos (os dois são opcionais).

- **Para adicionar um local:** pesquise o nome no sidebar ou clique direto no mapa.
- **Para avaliar:** clique no pino e depois em **"Já visitei"**.
- **Onde ficam os dados:** os locais numa planilha e as fotos numa pasta privada, as duas no seu Google Drive.
- **Quem acessa:** só quem tem usuário e senha, criados por você na área **⚙️ Usuários**.

---

## Configuração (uma vez só, ~20 min)

### 1. Google Cloud: autorizar o app a usar o seu Drive

1. Entre em <https://console.cloud.google.com/> com a sua conta Google e crie um projeto (ex.: `locais-app`).
2. Vá em **APIs e serviços → Biblioteca** e ative a **Google Drive API** e a **Google Sheets API**.
3. Vá em **APIs e serviços → Tela de permissão OAuth** (pode aparecer como "Google Auth Platform"):
   - Tipo de usuário: **Externo**.
   - Preencha o nome do app e o seu e-mail de contato.
   - Em escopos, não precisa adicionar nada.
   - Em **Público-alvo**, clique em **Publicar app** para mudar o status para **"Em produção"**.

   > ⚠️ **Importante:** se o app ficar em "Teste", o acesso ao Drive expira a cada 7 dias e o app para de funcionar. O app pede só a permissão `drive.file` (acesso apenas aos arquivos que ele mesmo cria), que não exige verificação do Google. Na hora de autorizar, vai aparecer o aviso "O Google não verificou este app": clique em **Avançado → Acessar locais-app**.

4. Vá em **Credenciais → Criar credenciais → ID do cliente OAuth**:
   - Tipo de aplicativo: **App para computador**.
   - Baixe o JSON, renomeie para `client_secret.json` e coloque nesta pasta.

### 2. Criar a planilha e a pasta de fotos

No terminal, dentro desta pasta:

```bash
pip install -r requirements.txt
python setup_google.py
```

O script vai:

- abrir o navegador para você autorizar;
- criar a planilha `locais-app` e a pasta `locais-app-fotos` no seu Drive;
- perguntar seu usuário e senha inicial de admin do app;
- gravar `.streamlit/secrets.toml`, que serve para rodar o app no seu computador;
- imprimir um bloco de texto para colar no Streamlit Cloud.

Depois disso, pode apagar o `client_secret.json`.

### 3. Subir o código para o GitHub

Crie um repositório **privado** no GitHub e suba os arquivos desta pasta. O `.gitignore` já impede que `secrets.toml` e `client_secret.json` sejam enviados.

### 4. Publicar no Streamlit Community Cloud (grátis)

1. Entre em <https://share.streamlit.io/> com o GitHub e clique em **Create app**.
2. Escolha o repositório e use `app.py` como arquivo principal.
3. Em **Advanced settings → Secrets**, cole o bloco impresso pelo `setup_google.py`.
4. Clique em **Deploy**.

### 5. Primeiro acesso

1. Entre com o usuário e a senha de admin que você escolheu.
2. Troque a senha em **🔑 Trocar minha senha**. A senha inicial fica nos Secrets, então troque logo.
3. Em **⚙️ Usuários**, crie o usuário e a senha de cada pessoa e passe para ela.

> Dica: ative a verificação em duas etapas na sua conta Google.

---

## Rodar no seu computador

```bash
streamlit run app.py
```

O app usa o `.streamlit/secrets.toml` gravado pelo `setup_google.py` e os mesmos dados do Drive da versão online.

> Se o Windows bloquear o app com a mensagem "Uma política de Controle de Aplicativo bloqueou este arquivo" (erro do `pyarrow`), é o **Controle de Aplicativo Inteligente** do Windows 11 barrando uma biblioteca. A versão online no Streamlit Cloud não é afetada.

---

## Perguntas frequentes

- **Alguém precisa do meu login do Google?** Não. Só o app usa sua conta, por trás, com a chave guardada nos Secrets. As outras pessoas entram com o usuário e a senha que você cria.
- **Quem pode ver a planilha e as fotos no Drive?** Só você, desde que não compartilhe a pasta ou a planilha. O app também não enxerga o resto do seu Drive.
- **Espaço:** as fotos são reduzidas para no máximo 1600px (~200–400 KB cada) e ocupam o seu espaço de 15 GB do Google.
- **Esqueci a senha de admin:** abra a planilha `locais-app`, apague a sua linha na aba `usuarios` e recarregue o app. Se a aba ficar vazia, o admin é recriado com `ADMIN_USUARIO` / `ADMIN_SENHA_INICIAL` dos Secrets.
- **Busca de lugares:** usa o OpenStreetMap (Nominatim), que é gratuito. Se um lugar não aparecer, tente o endereço ou clique no mapa.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `app.py` | Mapa, sidebar e fluxos de adicionar, avaliar, editar e excluir |
| `auth.py` | Login, hash de senha (bcrypt) e bloqueio após 5 tentativas erradas |
| `admin.py` | Trocar a própria senha e gerenciar usuários |
| `storage.py` | Leitura e gravação na planilha e no Drive |
| `geo.py` | Busca de lugares e endereço de um ponto clicado |
| `setup_google.py` | Configuração inicial (rodar uma vez) |
