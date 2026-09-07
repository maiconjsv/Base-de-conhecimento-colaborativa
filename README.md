# Base de Conhecimento

Aplicação web interna (Python + Flask) para documentar coisas do trabalho.
Você só **anexa ou arrasta** o(s) arquivo(s); o sistema lê cada um e monta o
registro sozinho — título, resumo e palavras-chave — e o documento fica
localizável por **busca full-text** (qualquer palavra do conteúdo, além de
título, descrição e tags).

- **Envio:** botão de anexar + arrastar e soltar, vários arquivos de uma vez.
  Nada para digitar no upload — ao anexar, o envio começa na hora, com tela de
  progresso, e a página recarrega no resultado.
- **Visualização no sistema (sem baixar):** PDF abre embutido no navegador;
  Markdown é renderizado; CSV vira tabela; TXT aparece formatado; DOCX/XLSX/PPTX
  mostram a prévia de texto + a galeria de imagens. O botão *Baixar* continua
  disponível, mas é opcional.
- **Metadados automáticos:** título vem dos metadados embutidos do arquivo, ou
  do primeiro cabeçalho do texto, ou do nome do arquivo higienizado; o resumo
  vem do assunto embutido ou das primeiras frases; as tags são os termos mais
  frequentes do conteúdo (sem palavras vazias PT/EN). Tudo editável depois na
  página do documento.
- **Imagens:** as imagens embutidas em PDF, DOCX, PPTX e XLSX são extraídas,
  miniaturizadas e exibidas numa galeria na página do documento (ícones e
  espaçadores minúsculos e duplicatas são descartados). Desligue com
  `EXTRACT_IMAGES=0`.
- **Busca:** SQLite FTS5 (nativo, sem serviço externo) com ranking por relevância
  (`bm25`) e trechos destacados (`snippet`). Cada resultado abre um **localizador**
  in-loco (sem recarregar): clica no documento e ele expande mostrando *todas* as
  ocorrências do termo dentro dele, com o termo marcado — casamento por prefixo e
  sem acento, igual ao índice. Endpoint `GET /search/hits/<id>?q=…` (JSON),
  lógica em `app/locator.py`.
- **Formatos com extração de texto:** PDF, DOCX, TXT/Markdown, XLSX, PPTX, CSV.
- **Acesso:** login simples por usuário/senha (Flask-Login). Todo usuário logado
  vê todos os documentos e pode enviar, editar e remover.
- **Erros tratados:** senha errada, campos inválidos, arquivo grande demais (413),
  página inexistente (404) e falhas de processamento têm mensagem clara — nunca a
  tela crua do Flask. Num envio em lote, um arquivo com erro não derruba os outros.
- **Armazenamento:** SQLite em `instance/kb.sqlite`, arquivos em `uploads/`
  (imagens extraídas em `uploads/images/`). No executável, tudo fica na pasta
  `dados/` ao lado do `.exe`.
- **Programa Windows:** empacotável como `BaseConhecimento.exe` (pasta única, sem
  instalar nada). A pasta `dados/` carrega todo o estado — zipar a pasta do
  programa e compartilhar leva os documentos junto. Ver *Gerar o executável*.

## Instalação (desenvolvimento)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env   # edite SECRET_KEY

flask --app run.py init-db
flask --app run.py create-user master
```

## Rodar

```powershell
flask --app run.py run          # desenvolvimento
# ou
python run.py                   # host 0.0.0.0:5000 (acesso pela rede interna)
```

Para o modo debug do Flask no desenvolvimento: `$env:FLASK_DEBUG = "1"` antes de
`python run.py` (fica desligado por padrão).

Acesse http://localhost:5000 e faça login.

## Comandos

| Comando | Descrição |
|---|---|
| `flask --app run.py init-db` | Cria tabelas, índice FTS5 e triggers |
| `flask --app run.py create-user <usuario>` | Cria um usuário (senha via prompt) |
| `flask --app run.py reindex` | Reprocessa os arquivos (texto + imagens) e reconstrói o índice |

## Estrutura

```
app/
  __init__.py     app factory, comandos CLI
  db.py           SQLAlchemy + tabela/triggers FTS5
  models.py       User, Document
  extract.py      extração de texto + metadados embutidos por formato
  images.py       extração das imagens embutidas + miniaturas (Pillow)
  search.py       consulta FTS5 (bm25 + snippet) + contagem de ocorrências
  locator.py      acha todas as ocorrências dos termos dentro de um documento
  errors.py       páginas de erro 403/404/413/500
  auth/           blueprint de login/registro
  documents/      blueprint de upload/listagem/busca/detalhe
    analyze.py    deriva título, resumo e palavras-chave do arquivo
    service.py    salva o arquivo e cria o registro
    preview.py    decide como visualizar (PDF/Markdown/CSV/texto)
    sanitize.py   sanitizador de HTML (Markdown seguro), sem dependências
  templates/  static/
config.py         configuração (SECRET_KEY, limites, extensões, KB_DATA_DIR)
run.py            ponto de entrada web (desenvolvimento / servidor)
desktop.py        ponto de entrada do programa Windows (janela + servidor local)
BaseConhecimento.spec / build.ps1   empacotamento com PyInstaller
```

## Gerar o executável (programa Windows)

> Passo a passo completo (com distribuição, atualização, backup e solução de
> problemas): **[COMPILAR-E-DISTRIBUIR.md](COMPILAR-E-DISTRIBUIR.md)**.

```powershell
.\build.ps1 -Clean
```

Isso gera `dist\BaseConhecimento\` com:

- `BaseConhecimento.exe` — abre o servidor local (waitress) e uma janela
  dedicada (modo `--app` do Edge/Chrome; se falhar, cai para o navegador padrão).
- `_internal\` — bibliotecas (não mexer).
- `dados\` — banco, arquivos enviados, imagens e a chave de sessão.
- `LEIA-ME.txt` — instruções para quem receber.
- `versao.txt` — carimbo da versão (usado pelo atualizador).

Além da pasta, o build gera `dist\AtualizarBaseConhecimento.exe`: um executável
único com a versão nova embutida. Para atualizar uma cópia já instalada, a pessoa
copia esse `.exe` para dentro da pasta do programa e executa — ele para o app,
faz backup de `dados\` em `_backup\`, troca só `BaseConhecimento.exe` e
`_internal\`, e **não toca** em `dados\`, `.env` nem `secret.key` (rollback
automático se falhar).

**Primeiro uso:** o programa abre a tela *Configuração inicial* para criar o
usuário administrador. Depois vai direto para o login.

**Instalação nova:** zipe a pasta `dist\BaseConhecimento` inteira e envie. Quem
receber extrai e abre o `.exe` — com todos os documentos já dentro (eles moram
em `dados\`).

**Atualizar quem já usa:** envie só o `dist\AtualizarBaseConhecimento.exe`
(ver acima). Cada cópia é independente; defina quem é o "dono" da base e
redistribua/atualize quando houver mudanças.

**Backup:** copiar a pasta `dados\`.

### Rodar como servidor de um PC (opcional)

```powershell
$env:KB_NO_WINDOW = "1"
.\BaseConhecimento.exe        # sobe sem janela; outras máquinas acessam por http://IP-do-PC:5000
```

## Produção sem empacotar (rede interna)

```powershell
pip install waitress
$env:KB_DATA_DIR = "C:\dados-base-conhecimento"   # opcional: dados fora do projeto
waitress-serve --port=5000 --call app:create_app
```

Defina `SECRET_KEY` no `.env` e faça backup periódico de `instance/` e `uploads/`
(ou da pasta `KB_DATA_DIR`).
