# Base de Conhecimento

Aplicação web interna (Python + Flask) para documentar coisas do trabalho.
Você só **anexa ou arrasta** o(s) arquivo(s); o sistema lê cada um e monta o
registro sozinho — título, resumo e palavras-chave — e o documento fica
localizável por **busca full-text** (qualquer palavra do conteúdo, além de
título, descrição e tags).

> **Quer ajudar?** O projeto é colaborativo. Veja [Como contribuir](#como-contribuir):
> lá estão o passo a passo, as receitas para as mudanças mais comuns e o checklist
> do Pull Request. Para manter o sistema, veja [Manutenção](#manutenção) e a
> [documentação de cada tecnologia](#documentação-das-tecnologias). Suporte: **maicon.vieira@atos.ai** · GitHub: **[@maiconjsv](https://github.com/maiconjsv)**.

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
- **Barra de pesquisa abaixo das abas:** como a barra de endereço do navegador, ela
  age **na aba aberta** e mostra a pesquisa daquela aba ao trocar de aba. *Buscar*
  (Enter) faz a busca por palavra-chave; **✦ Perguntar à IA** (Ctrl+Enter) abre o
  chat, ou continua a conversa se a aba já for o chat. Alt+Enter abre o resultado numa
  aba nova; Ctrl+L ou F6 levam o cursor para a barra.
- **Bloco de notas para cruzar dados entre abas:** o botão **Notas** da barra (ou
  Alt+N) abre um painel lateral que continua aberto enquanto você troca de aba. Ao
  **selecionar um texto em qualquer aba**, aparece o botão **+ Notas** (ou Alt+S), e o
  trecho entra como **recorte com a fonte**: título da página e link que reabre de onde
  veio. Numa linha da pseudoplanilha, a fonte guarda a aba e a linha exatas. Embaixo dos
  recortes há um campo livre de **anotações** para cruzar e concluir. Dá para ter várias
  notas (criar, renomear, apagar), copiar tudo ou exportar em `.txt`. As notas são
  salvas automaticamente no banco, uma por usuário, e entram no backup. Código em
  `app/notes.py` (API `/notas/api`; alterações exigem o cabeçalho `X-KB-Notas`, que um
  site de fora não consegue enviar), `static/notes.js` (painel) e `static/in_tab.js`
  (botão sobre a seleção).
- **Abas como num navegador:** o sistema abre numa moldura (`/`) com uma barra de
  abas abaixo do menu. Cada aba é uma página independente do sistema (pesquisa,
  documento, planilha filtrada, Perguntar…), com sua própria rolagem e estado. A
  busca do menu abre o resultado numa **aba nova**, e o **+** abre uma aba na lista de
  recentes (`/inicio`). Ctrl+clique ou clique do meio num link abrem em outra aba, e
  o clique do meio numa aba a fecha. Os botões **Em nova aba** (busca) e **Filtrar em
  nova aba** (planilha) mantêm a aba atual como está. As abas abertas voltam ao
  reabrir o programa. Técnica: cada aba é um `<iframe>` (`static/tabs.js`); dentro
  dela, a página esconde o próprio menu e repassa os cliques de "nova aba" para a
  moldura (`static/in_tab.js`). Sem a moldura, as páginas funcionam sozinhas.
- **Modo escuro:** o botão de lua/sol no menu alterna entre claro e escuro, e a
  escolha vale para todas as abas abertas. Sem escolha salva, o sistema segue o tema
  do Windows. Técnica: `data-theme` no `<html>`, aplicado por um script no `<head>`
  antes de pintar (`base.html`) e alternado pelo `static/theme.js`. No `style.css`, a
  escala `--brand-*` (textos e fundos claros) se inverte no escuro, enquanto
  `--solid-*` (menu, botões, barra de abas) fica igual.
- **Pesquisas em abas, com cruzamento:** a tela `/pesquisas` mantém várias pesquisas
  abertas ao mesmo tempo, uma por aba, cada uma com sua cor. A aba **Cruzar** combina
  os resultados de duas ou mais abas: documentos que aparecem **em todas** (∩), **em
  qualquer uma** (∪, os que estão em mais pesquisas primeiro) ou **só em uma e em
  nenhuma outra** (−). No cruzamento, cada documento mostra em quais pesquisas aparece
  e quantas ocorrências tem em cada uma, e os termos marcados usam a cor da aba de
  origem. As abas ficam guardadas no navegador. A combinação é feita no servidor
  (`cross_documents` em `app/search.py`, endpoint `GET /pesquisas/cruzar?q=…&q=…&op=and|or|not`).
  A tela de busca tem um link para abrir a pesquisa atual numa aba.
- **Documentos duplicados são ignorados:** cada envio é comparado com a base por
  impressão digital (SHA-256) do **arquivo** (cópia idêntica, mesmo renomeada) e do
  **texto extraído** normalizado (o mesmo documento salvo ou exportado de novo). Textos
  com menos de 200 caracteres só são comparados pelo arquivo. O duplicado não é gravado
  e o aviso diz qual documento já existia. Lógica em `app/dedup.py`, tabela
  `document_fingerprint`. Documentos antigos recebem a impressão na inicialização.
- **IA local no Perguntar (Gemma 3 4B):** com o modelo instalado, a resposta do
  Perguntar é escrita por uma IA que roda **no próprio computador** (nada vai para a
  internet). A busca local escolhe os trechos, a IA lê só esses trechos e responde
  citando as fontes ([1], [2]… clicáveis), e diz quando a informação não está na
  documentação. A resposta aparece aos poucos (streaming), e uma chave na tela liga ou
  desliga a IA. O motor é o `llama-server` do llama.cpp: liga na primeira pergunta,
  desliga sozinho após 10 min sem uso e morre junto com o programa (job object do
  Windows). Arquivos: motor em `llama\`, modelo `.gguf` em `modelos\` (o atualizador
  nunca mexe nessa pasta). O sistema lê a RAM total e a livre da máquina e avisa quando
  está curta. Para preparar: `scripts\baixar_ia.py`. Código em `app/llm.py`, endpoints
  `GET /perguntar/ia?q=` (NDJSON em streaming) e `/perguntar/ia/status`. Sem modelo, o
  Perguntar funciona como antes, e o aviso "não instalada — por quê?" explica onde pôr o
  arquivo. **Conversa:** a IA vê as 2 últimas perguntas e respostas (parâmetro `ctx`),
  então entende continuações como "e o email?". Continuação curta (até 2 palavras-chave)
  é buscada junto com a pergunta anterior; "Nova conversa" zera a memória. **Modelo
  fora do OneDrive:** além de `modelos\`, o sistema procura em
  `%LOCALAPPDATA%\BaseConhecimento\modelos`, uma pasta local que não sincroniza.
- **Acompanhamento de Chamados (programa à parte):** `AcompanhamentoChamados.exe`, na
  mesma pasta do programa, é uma janela nativa (tkinter, sem navegador) para acompanhar
  chamados e ser cobrado por eles. A lista compacta mostra número, título, cliente,
  status, prioridade, **próxima cobrança** e **prazo**, colorida por urgência. Há
  ações rápidas: registrar acompanhamento (com anotação), mudar status, adiar, copiar o
  número e abrir o link, e cada chamado guarda um histórico. **Notificar cobrança a cada
  X**: no cadastro há uma seção própria (🔔) com "A cada [N] [minuto(s)/hora(s)/dia(s)]",
  atalhos (15 min a 1 dia), "Padrão da prioridade" ou "Não notificar (só prazo)", e uma
  frase que confirma o próximo aviso. Na lista, a coluna **Notificar** e o botão
  **🔔 Notificar a cada ▾** (também no botão direito) trocam o intervalo sem abrir o
  cadastro. No alerta, **"Vi, lembrar em X"** adia pelo próprio intervalo. Os **alertas
  são parametrizáveis** (botão ⚙):
  - cadência "sem acompanhamento há X" por prioridade (padrão P1 30 min, P2 1 h,
    P3 4 h, P4 8 h) ou por chamado;
  - avisos antes do prazo (padrão 60 e 15 min) e repetição com o prazo estourado
    (15 min);
  - horário de trabalho e dias úteis (fora deles os alertas esperam, exceto P1 se
    configurado);
  - status que não cobram, tempo de adiamento padrão, som e abrir junto com o Windows.

  O alerta abre uma janela por cima de tudo, com som e a barra de tarefas piscando, e
  cada motivo fica no cartão até a pessoa agir. Também exporta para CSV. Os dados ficam
  em `dados\chamados.sqlite`. Código em `chamados/` (`store.py` banco, `alertas.py`
  regras puras e testáveis, `app.py` interface), entrada `chamados_main.py`, build
  `Chamados.spec` (arquivo único). O `build.ps1` coloca o exe na pasta do programa, e o
  atualizador o fecha antes de trocar os arquivos e o reabre depois. Para rodar em
  desenvolvimento: `.\.venv\Scripts\python.exe chamados_main.py`.
- **Perguntar (assistente sem IA):** tela de chat em `/perguntar`. A pergunta em
  linguagem natural vira palavras-chave (sem palavras vazias, reduzidas a radical:
  "senhas" → `senh`, "configuração" → `configur`), o FTS5 acha todo documento que
  cita algum termo, e o texto dos melhores é varrido em janelas de ~350
  caracteres, pontuadas por peso do termo (idf) × frequência × cobertura ×
  proximidade. Mostra os melhores trechos e a lista completa de documentos que
  mencionam os termos (os que têm todos primeiro), com as ocorrências de cada um.
  Lógica em `app/ask.py`, endpoint `GET /perguntar/api?q=…` (JSON).
- **Planilhas no banco:** XLSX, XLSM, XLS (Excel antigo, via `xlrd`) e CSV são lidas
  de forma estruturada (`app/sheets.py`): cada aba vira um `DocumentSheet`, com o
  cabeçalho detectado, e cada linha não vazia vira um `SheetRow`, com o **número real
  da linha no Excel** e as células formatadas (datas dd/mm/aaaa, decimais com vírgula).
  As linhas têm índice FTS5 próprio (`sheet_row_fts`). Na página do documento a
  planilha aparece como **pseudoplanilha**: abas, letras de coluna, números de linha,
  filtro por palavra-chave e paginação de 200 linhas, sempre com a fonte
  (arquivo › aba › linhas). Na busca e no assistente, os resultados de planilha
  aparecem com **uma aba por aba da planilha** (com a contagem de linhas, abrindo na
  aba com mais resultados), até 10 linhas por aba e o link "Abrir esta aba na
  planilha", já filtrada. O número de cada linha
  abre a pseudoplanilha naquele ponto (`?sheet=<id>&row=<n>`). Um termo que aparece
  no cabeçalho ou no nome da aba conta para todas as linhas daquela aba. Planilhas
  enviadas antes desse recurso são estruturadas automaticamente na inicialização
  (`backfill_sheets`). Limites: 50 abas, 20 mil linhas por aba, 80 colunas.
  No XLSX de até 25 MB, o **destino dos links** entra no texto pesquisável quando o
  texto visível não o mostra, e células **mescladas na vertical** repetem o valor nas
  linhas cobertas. **CSV guarda uma aba só:** ao enviar um CSV, o sistema avisa que,
  se a planilha original tem várias abas, o certo é enviar o `.xlsx`.
- **Formatos com extração de texto:** PDF, DOCX, TXT/Markdown, XLSX/XLSM/XLS, PPTX, CSV.
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
  __init__.py     app factory, comandos CLI, contato do mantenedor nos templates
  db.py           SQLAlchemy + tabelas/triggers FTS5 (documentos e linhas de planilha)
  models.py       User, Document, DocumentImage, DocumentSheet, SheetRow, DocumentFingerprint, Note
  notes.py        bloco de notas (API JSON do painel lateral)
  extract.py      extração de texto + metadados embutidos por formato
  images.py       extração das imagens embutidas + miniaturas (Pillow)
  sheets.py       planilhas estruturadas: leitura, gravação, pseudoplanilha
  search.py       consulta FTS5 (bm25 + snippet) + contagem de ocorrências
  locator.py      acha todas as ocorrências dos termos dentro de um documento
  ask.py          assistente "Perguntar": palavras-chave, pontuação de trechos
  llm.py          IA local: liga/desliga o llama-server, prompt, streaming
  dedup.py        verificador de duplicados (impressão do arquivo e do texto)
  errors.py       páginas de erro 403/404/413/500
  auth/           blueprint de login/registro/configuração inicial
  documents/      blueprint de upload/listagem/busca/detalhe/perguntar/contribuir
    analyze.py    deriva título, resumo e palavras-chave do arquivo
    service.py    salva o arquivo e cria o registro (texto, imagens, abas)
    preview.py    decide como visualizar (PDF/Markdown/CSV/texto)
    sanitize.py   sanitizador de HTML (Markdown seguro), sem dependências
  templates/      telas Jinja (base.html tem navbar e rodapé)
  static/         style.css (tema Semantix), tabs.js + in_tab.js (abas de navegador),
                  workspace.js (tela Pesquisas), imagens da marca
chamados/         Acompanhamento de Chamados (exe à parte): store.py, alertas.py, app.py
chamados_main.py  ponto de entrada do AcompanhamentoChamados.exe (Chamados.spec)
config.py         configuração (SECRET_KEY, limites, extensões, KB_DATA_DIR, contato)
run.py            ponto de entrada web (desenvolvimento / servidor)
desktop.py        ponto de entrada do programa Windows (janela + servidor local)
updater.py        AtualizarBaseConhecimento.exe (troca o programa, preserva dados\)
BaseConhecimento.spec / Atualizador.spec / build.ps1   empacotamento com PyInstaller
scripts/make_zip.py   gera o payload.zip do atualizador (usado pelo build.ps1)
scripts/baixar_ia.py  baixa o motor llama.cpp e o modelo Gemma para vendor/ (não versionado)
CONTRIBUTING.md   atalho para a seção "Como contribuir" (o GitHub mostra em issues/PRs)
```

## Gerar o executável (programa Windows)

> Passo a passo completo (com distribuição, atualização, backup e solução de
> problemas): **[COMPILAR-E-DISTRIBUIR.md](COMPILAR-E-DISTRIBUIR.md)**.

```powershell
.\.venv\Scripts\python.exe scripts\baixar_ia.py   # uma vez: motor + modelo da IA local em vendor\
.\build.ps1 -Clean                                # ou -ComModelo para incluir o modelo no zip
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

---

## Manutenção

Guia para quem mantém o sistema no dia a dia. Para entender o código antes de mexer,
leia as seções [Estrutura](#estrutura) e [Como o sistema funciona](#como-o-sistema-funciona-visão-para-quem-vai-mexer).

### Ciclo de uma mudança

```powershell
# 1. ambiente (uma vez por máquina)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\baixar_ia.py          # motor + modelo da IA (opcional)

# 2. desenvolver e testar
$env:FLASK_DEBUG = "1"                                    # recarrega ao salvar e mostra o erro detalhado
.\.venv\Scripts\python.exe run.py                         # sistema web em http://127.0.0.1:5000
.\.venv\Scripts\python.exe chamados_main.py               # módulo de chamados

# 3. gerar e distribuir
.\build.ps1                                               # dist\BaseConhecimento\ + dist\AtualizarBaseConhecimento.exe
```

Antes de distribuir, teste o executável **numa cópia** da pasta `dist\BaseConhecimento`.
O build recria essa pasta, e o que você testar dentro dela é apagado no build seguinte.
Para quem já usa, mande só o `AtualizarBaseConhecimento.exe` (ver
[COMPILAR-E-DISTRIBUIR.md](COMPILAR-E-DISTRIBUIR.md)).

### Tarefas periódicas

| Tarefa | Como fazer | Cuidado |
|---|---|---|
| **Atualizar bibliotecas Python** | `.\.venv\Scripts\python.exe -m pip list --outdated`. Suba **uma de cada vez** no `requirements.txt`, rode o [checklist de testes](#testando-sua-mudança) e gere o build | Versões novas do PyInstaller, Flask ou SQLAlchemy podem mudar comportamento. Confira o changelog nos links abaixo |
| **Atualizar o motor da IA (llama.cpp)** | Troque `LLAMA_BUILD` em `scripts\baixar_ia.py` por um build mais novo ([releases](https://github.com/ggml-org/llama.cpp/releases)), apague `vendor\llama\`, rode o script de novo, teste o Perguntar e gere o build | O llama.cpp muda rápido. Se os parâmetros de `llm.py` (`-c`, `-np`, `--port`) mudarem de nome, o motor não sobe; veja `dados\ia.log` |
| **Trocar o modelo de IA** | Coloque o `.gguf` em `vendor\modelos\` (ou `modelos\`) e ajuste `PREFERRED_MODEL` em `app/llm.py` | Modelo maior = mais RAM e mais lento. Ajuste `MAX_CONTEXT_CHARS` e meça o tempo de resposta |
| **Mudar o banco de dados** | Prefira **tabela nova**; coluna nova exige um passo em `ensure_database` (`desktop.py`) | Não há migrações. Leia a receita [Alterar o banco de dados](#receitas-para-mudanças-comuns) |
| **Trocar a versão do Python** | Instale a nova, apague `.venv\`, recrie e reinstale as dependências | O build usa o Python da `.venv`. Teste o executável depois |
| **Backup** | Copie a pasta `dados\` da instalação | O atualizador já guarda as 2 últimas cópias em `_backup\` |

### Onde olhar quando algo dá errado

| Sintoma | Onde investigar |
|---|---|
| Erro numa página do sistema | Rode `run.py` com `FLASK_DEBUG=1` e reproduza: o erro completo aparece no terminal e no navegador |
| O executável não abre ou fecha sozinho | Rode `run.py` no projeto; o executável não tem console. Para ver o servidor do exe: `$env:KB_NO_WINDOW="1"; .\BaseConhecimento.exe` |
| IA "não instalada" ou não responde | Clique em "não instalada — por quê?"; veja `dados\ia.log` (saída do motor); confira `llama\llama-server.exe` e o `.gguf` |
| IA lenta | Pouca RAM livre (o aviso aparece no Perguntar) ou trechos demais. Reduza `MAX_CONTEXT_CHARS` / `MAX_AI_PASSAGES` em `app/llm.py` |
| Planilha sem todas as abas | Provavelmente foi enviada como CSV, que guarda só uma aba. Envie o `.xlsx` |
| Busca não acha algo que existe | Confira o texto extraído na página do documento ("Ver texto extraído"). Se estiver vazio, a extração falhou (PDF escaneado, por exemplo) |
| Build falha com "arquivo em uso" | Feche o programa aberto a partir de `dist\` (o `build.ps1` já tenta). O antivírus pode estar lendo arquivos; rode de novo |
| Atualização desfeita | Leia a mensagem: costuma ser OneDrive ou Program Files. Restos `.old-*` são apagados na próxima atualização |
| Módulo de chamados com erro | Rode `chamados_main.py` no terminal para ver o erro; os dados ficam em `dados\chamados.sqlite` |

### Dicas para manter com ajuda de IA (Claude Code, Copilot)

- Peça para ler **este README primeiro**: ele tem a arquitetura, as receitas e as regras do projeto.
- Mudanças pequenas e testadas uma de cada vez são mais seguras do que pedir várias coisas juntas.
- Sempre teste o **executável gerado**, não só o `run.py`: o empacotamento esconde problemas (arquivo não incluído, caminho diferente).

---

## Documentação das tecnologias

Links oficiais de cada peça usada no projeto, agrupados pela parte do sistema onde aparecem.

### Base

| Tecnologia | Para que usamos | Documentação |
|---|---|---|
| Python 3.12 | linguagem de todo o projeto | [docs.python.org/3.12](https://docs.python.org/3.12/) |
| Bibliotecas padrão do Python | `sqlite3` (módulo de chamados), `ctypes` (APIs do Windows), `zipfile`, `urllib`, `winsound` | [sqlite3](https://docs.python.org/3/library/sqlite3.html) · [ctypes](https://docs.python.org/3/library/ctypes.html) · [winsound](https://docs.python.org/3/library/winsound.html) |
| PowerShell | `build.ps1`, scripts de apoio | [learn.microsoft.com/powershell](https://learn.microsoft.com/en-us/powershell/) |
| Git e GitHub | versionamento, issues e Pull Requests | [docs.github.com/pt/pull-requests](https://docs.github.com/pt/pull-requests) |

### Sistema web (servidor)

| Tecnologia | Para que usamos | Documentação |
|---|---|---|
| Flask 3 | rotas, páginas, app factory (`app/`) | [flask.palletsprojects.com](https://flask.palletsprojects.com/en/stable/) |
| Jinja2 | templates HTML (`app/templates/`) | [jinja.palletsprojects.com](https://jinja.palletsprojects.com/en/stable/) |
| Werkzeug | base HTTP do Flask (uploads, respostas em streaming) | [werkzeug.palletsprojects.com](https://werkzeug.palletsprojects.com/en/stable/) |
| Flask-SQLAlchemy / SQLAlchemy | modelos e consultas ao banco (`app/models.py`) | [flask-sqlalchemy.readthedocs.io](https://flask-sqlalchemy.readthedocs.io/en/stable/) · [docs.sqlalchemy.org](https://docs.sqlalchemy.org/en/21/) |
| Flask-Login | login e sessão dos usuários | [flask-login.readthedocs.io](https://flask-login.readthedocs.io/en/latest/) |
| Flask-WTF / WTForms | formulários com proteção CSRF | [flask-wtf.readthedocs.io](https://flask-wtf.readthedocs.io/en/latest/) · [wtforms.readthedocs.io](https://wtforms.readthedocs.io/en/stable/) |
| SQLite + FTS5 | banco local e busca full-text (`app/db.py`, `app/search.py`) | [sqlite.org/docs](https://www.sqlite.org/docs.html) · [FTS5](https://www.sqlite.org/fts5.html) |
| waitress | servidor web do executável | [docs.pylonsproject.org/projects/waitress](https://docs.pylonsproject.org/projects/waitress/en/stable/) |
| python-dotenv | ler o `.env` | [saurabh-kumar.com/python-dotenv](https://saurabh-kumar.com/python-dotenv/) |

### Leitura de documentos

| Tecnologia | Para que usamos | Documentação |
|---|---|---|
| pypdf | texto, metadados e imagens de PDF | [pypdf.readthedocs.io](https://pypdf.readthedocs.io/en/stable/) |
| python-docx | Word (.docx) | [python-docx.readthedocs.io](https://python-docx.readthedocs.io/en/latest/) |
| python-pptx | PowerPoint (.pptx) | [python-pptx.readthedocs.io](https://python-pptx.readthedocs.io/en/latest/) |
| openpyxl | Excel .xlsx/.xlsm (abas, links, células mescladas) | [openpyxl.readthedocs.io](https://openpyxl.readthedocs.io/en/stable/) |
| xlrd | Excel antigo (.xls) | [xlrd.readthedocs.io](https://xlrd.readthedocs.io/en/latest/) |
| Pillow | miniaturas das imagens extraídas | [pillow.readthedocs.io](https://pillow.readthedocs.io/en/stable/) |
| Python-Markdown | renderizar arquivos .md | [python-markdown.github.io](https://python-markdown.github.io/) |

### Interface (navegador)

| Tecnologia | Para que usamos | Documentação |
|---|---|---|
| Bootstrap 5.3 | base visual, modo escuro (`data-bs-theme`) | [getbootstrap.com/docs/5.3](https://getbootstrap.com/docs/5.3/) |
| APIs web (MDN) | resposta da IA em streaming (`fetch` + `ReadableStream`), seleção de texto para as notas, sincronizar tema entre abas (evento `storage`) | [Streams](https://developer.mozilla.org/en-US/docs/Web/API/Streams_API/Using_readable_streams) · [Selection](https://developer.mozilla.org/en-US/docs/Web/API/Selection) · [storage event](https://developer.mozilla.org/en-US/docs/Web/API/Window/storage_event) |

### Programa Windows

| Tecnologia | Para que usamos | Documentação |
|---|---|---|
| PyInstaller | gerar os `.exe` (`*.spec`) | [pyinstaller.org](https://pyinstaller.org/en/stable/) |
| Microsoft Edge (modo `--app`) | janela dedicada do programa (`desktop.py`) | [políticas do Edge](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies) · [lista de parâmetros do Chromium](https://peter.sh/experiments/chromium-command-line-switches/) (não oficial) |
| tkinter / ttk | interface nativa do módulo de chamados | [tkinter](https://docs.python.org/3/library/tkinter.html) · [tkinter.ttk](https://docs.python.org/3/library/tkinter.ttk.html) |
| APIs do Windows (via `ctypes`) | motor da IA morre junto com o programa, RAM da máquina, piscar na barra de tarefas, uma cópia só aberta | [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) · [GlobalMemoryStatusEx](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-globalmemorystatusex) · [FlashWindowEx](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-flashwindowex) · [CreateMutexW](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-createmutexw) |

### Inteligência artificial local

| Tecnologia | Para que usamos | Documentação |
|---|---|---|
| llama.cpp (`llama-server`) | motor que roda o modelo no processador | [repositório](https://github.com/ggml-org/llama.cpp) · [servidor e parâmetros](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) · [releases](https://github.com/ggml-org/llama.cpp/releases) |
| Formato GGUF | arquivo do modelo (`modelos\*.gguf`) | [especificação GGUF](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md) |
| Gemma 3 4B (Google) | o modelo de linguagem | [documentação do Gemma](https://ai.google.dev/gemma/docs) · [termos de uso](https://ai.google.dev/gemma/terms) · [arquivo usado (Hugging Face)](https://huggingface.co/ggml-org/gemma-3-4b-it-GGUF) |
| API de chat compatível com OpenAI | formato das mensagens trocadas com o motor (`/v1/chat/completions`) | [referência da API de chat](https://platform.openai.com/docs/api-reference/chat) |

---

## Como contribuir

A Base de Conhecimento é um projeto colaborativo: qualquer pessoa pode reportar um
problema, sugerir uma ideia ou programar uma feature. O mantenedor é **Maicon Vieira**
([@maiconjsv](https://github.com/maiconjsv), maicon.vieira@atos.ai), que revisa e
publica as contribuições.

Dentro do programa, o rodapé tem os mesmos contatos e a página **Como contribuir**
(`/contribuir`, abre sem login).

### Formas de contribuir

| Você quer… | Faça isto |
|---|---|
| Pedir ajuda (erro, dúvida de uso) | E-mail para **maicon.vieira@atos.ai** |
| Reportar um bug | Abra uma [issue](https://github.com/maiconjsv/Base-de-conhecimento-colaborativa/issues/new) seguindo o [modelo de bug](#reportando-um-bug) |
| Sugerir uma funcionalidade (sem programar) | Abra uma [issue](https://github.com/maiconjsv/Base-de-conhecimento-colaborativa/issues/new) seguindo o [modelo de feature](#sugerindo-uma-feature) |
| Programar uma feature ou correção | Siga o [passo a passo](#passo-a-passo-para-contribuir-com-código) |
| Melhorar a documentação | Pull Request alterando este README ou os `.txt` de `distrib/` |

### Reportando um bug

Uma boa issue de bug permite reproduzir o problema sem precisar perguntar nada.
Copie este modelo:

```markdown
**O que eu fiz**
1. Abri o documento X / enviei o arquivo Y (tipo: PDF, XLSX…)
2. Cliquei em …

**O que eu esperava**
…

**O que aconteceu**
… (mensagem de erro, print da tela)

**Versão**: conteúdo do arquivo versao.txt, na pasta do programa
**Windows**: 10 / 11
```

Se o problema acontece com um arquivo específico e ele puder ser compartilhado,
anexe uma cópia **sem dados sensíveis**. Arquivos confidenciais nunca devem ir para
issues públicas: mande por e-mail.

### Sugerindo uma feature

```markdown
**Problema**: o que hoje é difícil ou impossível de fazer?
**Proposta**: como você imagina que deveria funcionar?
**Exemplo**: uma situação real em que isso ajudaria.
**Alternativas**: outras formas de resolver que você considerou (opcional).
```

Para mudanças grandes, como uma tela nova, mudança no banco ou dependência nova,
**espere o retorno do mantenedor na issue antes de programar**. Assim ninguém
perde tempo com uma abordagem que não vai ser aceita.

### Passo a passo para contribuir com código

1. **Combine na issue.** Comente na issue (ou abra uma) dizendo que vai trabalhar nela.
2. **Faça um fork** do repositório no GitHub (botão *Fork*).
3. **Clone o seu fork** e aponte para o repositório original:

   ```powershell
   git clone https://github.com/SEU-USUARIO/Base-de-conhecimento-colaborativa.git
   cd Base-de-conhecimento-colaborativa
   git remote add upstream https://github.com/maiconjsv/Base-de-conhecimento-colaborativa.git
   ```

4. **Prepare o ambiente** ([detalhes abaixo](#ambiente-de-desenvolvimento)):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe run.py
   ```

5. **Crie uma branch** a partir da `main` atualizada:

   ```powershell
   git fetch upstream
   git checkout -b feature/nome-curto upstream/main     # ou fix/nome-curto para correções
   ```

6. **Implemente** seguindo os [padrões do projeto](#padrões-de-código) e as
   [receitas](#receitas-para-mudanças-comuns).
7. **Teste** com o [checklist](#testando-sua-mudança).
8. **Faça commit e envie**:

   ```powershell
   git add -A
   git commit -m "Adiciona filtro por data na busca"
   git fetch upstream
   git rebase upstream/main          # traz o que entrou na main enquanto você trabalhava
   git push -u origin feature/nome-curto
   ```

9. **Abra o Pull Request** no GitHub (*Compare & pull request*), com destino à
   `main` de `maiconjsv/Base-de-conhecimento-colaborativa`, preenchendo o
   [checklist do PR](#checklist-do-pull-request).
10. **Acompanhe a revisão.** Responda aos comentários com novos commits na mesma
    branch, sem abrir outro PR. Depois de aprovado, o mantenedor faz o merge e
    inclui a mudança na próxima versão distribuída.

### Ambiente de desenvolvimento

**Pré-requisitos:** Windows 10/11, [Python 3.12](https://www.python.org/downloads/)
(a mesma versão usada no build), [Git](https://git-scm.com/) e um editor (VS Code
recomendado).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py          # http://127.0.0.1:5000
```

- No primeiro acesso, a tela **Configuração inicial** cria o usuário administrador.
- O `run.py` prepara o banco sozinho (tabelas, índices de busca e planilhas antigas),
  igual ao executável.
- Em desenvolvimento, os dados ficam em `instance\kb.sqlite` e `uploads\`, separados
  da sua instalação real. Para **começar do zero**, apague essas duas pastas.
- Se preferir ativar a venv (`.\.venv\Scripts\Activate.ps1`) e o PowerShell bloquear
  o script, use os caminhos completos como acima. Não precisa mudar a política de
  execução.

Variáveis de ambiente úteis (no `.env` ou no terminal com `$env:NOME = "valor"`):

| Variável | Para quê |
|---|---|
| `FLASK_DEBUG=1` | Recarrega ao salvar e mostra o erro detalhado no navegador |
| `KB_DATA_DIR=C:\pasta` | Usa outra pasta de dados (banco, uploads), como no executável |
| `EXTRACT_IMAGES=0` | Desliga a extração de imagens (uploads mais rápidos ao testar) |
| `MAX_CONTENT_LENGTH` | Limite do envio em bytes (padrão 50 MB) |
| `KB_NO_WINDOW=1` | No executável: sobe só o servidor, sem abrir a janela |

### Como o sistema funciona (visão para quem vai mexer)

```
Upload ─► documents/service.py: ingest_file
            ├─ dedup.py .............. arquivo/texto já existe? ignora (DuplicateDocument)
            ├─ extract.py ............ texto (PDF, DOCX, PPTX, TXT/MD)
            ├─ sheets.py ............. planilhas: abas + linhas (XLSX/XLSM/XLS/CSV)
            ├─ documents/analyze.py .. título, resumo e tags automáticos
            ├─ images.py ............. imagens embutidas + miniaturas
            └─ grava Document (+ DocumentImage, DocumentSheet, SheetRow)
                 └─ triggers SQLite atualizam document_fts e sheet_row_fts

Moldura /  ─► shell.html + tabs.js: cada aba é um iframe com uma página do sistema
Busca      ─► search.py (FTS5 + bm25) ─► locator.py (todas as ocorrências no doc)
Pesquisas  ─► workspace.js (abas) ─► /pesquisas/api e /pesquisas/cruzar (search.py)
Perguntar  ─► ask.py: palavras-chave + radicais ─► FTS5 (OR) ─► pontua trechos/linhas
Documento  ─► preview.py (PDF, Markdown, CSV, texto) ou pseudoplanilha (sheets.py)

Inicialização (run.py / desktop.py) ─► ensure_database: create_all + FTS
                                       + backfill_sheets + backfill_fingerprints
```

Princípios que guiam as decisões:

- **Tudo local.** Cada pessoa roda sua própria cópia do `.exe`. Nada de serviços
  externos, APIs na nuvem ou envio de conteúdo para fora da máquina.
- **Nunca perder dados.** Atualizações trocam o programa e preservam `dados\`.
  Falha ao ler um arquivo não impede o upload: o documento fica salvo sem texto
  (`extraction_ok=False`).
- **Sem digitação no upload.** O sistema deduz título, resumo e tags. A pessoa só
  ajusta depois, se quiser.

### Receitas para mudanças comuns

**Adicionar um formato de arquivo**
1. Escreva a função de extração em `app/extract.py` e registre em `_HANDLERS`
   (e em `_META_HANDLERS`, se o formato tiver título/assunto embutidos).
2. Libere a extensão em `ALLOWED` (`app/documents/forms.py`) e em
   `ALLOWED_EXTENSIONS` (`config.py`). Mantenha as duas listas iguais.
3. Se o formato tiver imagens embutidas, registre em `_ITERATORS` (`app/images.py`).
4. Se puder ser visualizado de um jeito melhor que a prévia de texto, ajuste
   `preview_kind` em `app/documents/preview.py` e o `document_detail.html`.
5. Teste com um arquivo bom, um corrompido e um vazio.

**Criar uma tela ou rota**
- Rotas ficam no blueprint `app/documents/__init__.py` (ou `app/auth/` para
  autenticação). Use `@login_required`, a menos que a página precise abrir sem login.
- O template estende `base.html` (`{% extends "base.html" %}`) para herdar navbar,
  rodapé e tema. A página também abre dentro de uma aba da moldura (iframe), então
  não use `window.top` nem dependa do menu do topo. Para um link ou botão abrir uma
  aba nova da moldura, marque com `data-newtab`.
- Use as cores do tema (`var(--brand-600)`, `var(--line)` etc., definidas no topo
  do `style.css`). Não use cores soltas, porque elas quebram o modo escuro. Para
  fundo roxo forte com texto branco, use `--solid-*`. Teste a tela nos dois temas.
- JavaScript: vanilla, inline no template quando é curto. Quando cresce, vai para um
  arquivo em `app/static/`, como o `workspace.js`. Ao montar HTML com dados do usuário,
  escape sempre (veja a função `esc` em `search.html`).

**Alterar o banco de dados**
- O projeto **não tem migrações**. Na inicialização, `db.create_all()` cria
  **tabelas novas**, mas **não altera tabelas existentes**.
- Prefira criar uma tabela nova ligada a `document` (foi assim com `DocumentSheet`
  e `SheetRow`).
- Se for inevitável adicionar ou alterar uma coluna, inclua em `ensure_database`
  (`desktop.py`) um passo idempotente (`ALTER TABLE … ADD COLUMN`, só se a coluna
  não existir) e teste com um banco de uma versão anterior.
- Dados que precisam ser gerados para documentos já existentes seguem o modelo do
  `backfill_sheets` em `app/sheets.py`.

**Ajustar a relevância do Perguntar**
- Os pesos ficam em constantes no topo de `app/ask.py` (`WINDOW`, `MIN_RELATIVE_SCORE`,
  `CONTEXT_WEIGHT`…). Palavras ignoradas ficam em `_QUESTION_WORDS`, e os sufixos
  removidos em `_SUFFIXES`.
- No PR, mostre perguntas de exemplo com o resultado **antes e depois** da mudança.

**Adicionar uma dependência**
- Só se não der para resolver com a biblioteca padrão ou com o que já existe.
- Fixe a versão no `requirements.txt` (`pacote==x.y.z`).
- Se ela for importada só dentro de uma função, inclua em `hiddenimports` no
  `BaseConhecimento.spec`.
- Rode o `.\build.ps1` e abra o executável gerado para confirmar que funciona.

### Padrões de código

- **Idioma:** textos da interface em português, com acentos. Comentários e
  docstrings em português, seguindo o estilo dos arquivos vizinhos.
- **Cada módulo começa com uma docstring** explicando o que faz e as decisões não
  óbvias (veja `app/locator.py` ou `app/ask.py`).
- **Funções pequenas e com nome descritivo.** Evite abstrações para um uso só.
- **Best effort na extração:** erro ao ler um arquivo é registrado no log
  (`logger.exception`) e não interrompe o upload.
- **Segurança:** nunca coloque texto do usuário em HTML sem escapar. O Jinja escapa
  sozinho; `| safe` e `Markup` só para HTML gerado pelo próprio sistema
  (ex.: `locator.render_window`). Consultas SQL sempre com parâmetros (`:nome`),
  nunca com f-string.
- **Visual:** Bootstrap 5.3 (já incluído) + tokens do `style.css`. Não adicione
  frameworks de CSS/JS nem novos CDNs.

### Testando sua mudança

O projeto ainda não tem testes automatizados, e um PR que adicionar os primeiros
(com `pytest`) é muito bem-vindo. Até lá, antes de abrir o PR, confira:

- [ ] `run.py` sobe sem erro, com um banco novo **e** com um banco que já tinha documentos
- [ ] Upload de PDF, DOCX, XLSX e um arquivo inválido (o inválido deve dar mensagem, não erro)
- [ ] Busca: resultados, contagem de ocorrências e expansão de um resultado
- [ ] Abas do topo: abrir pelo +, pela busca do menu e por clique do meio; fechar; reabrir o programa e ver as abas voltarem
- [ ] Notas: selecionar texto numa aba → "+ Notas"; o recorte abre a fonte; anotação salva sozinha e volta ao reabrir
- [ ] Pesquisas: abrir, fechar e trocar abas; cruzar duas abas nas três operações
- [ ] Enviar o mesmo arquivo duas vezes: o segundo deve ser ignorado com aviso
- [ ] Perguntar: uma pergunta com resposta, uma sem resposta e uma só com palavras vazias
- [ ] Página do documento: visualização, edição de título/tags e remoção
- [ ] Planilha: abas, filtro e link "número da linha" vindo da busca
- [ ] A tela continua usável numa janela estreita (~400 px)
- [ ] Se mexeu em dependências, `build.ps1` ou `desktop.py`: `.\build.ps1` termina com
      **OK** e o `dist\BaseConhecimento\BaseConhecimento.exe` abre
- [ ] Se mexeu no atualizador: instale a versão anterior numa pasta de teste, rode o
      `AtualizarBaseConhecimento.exe` novo e confirme que os documentos continuam lá

### Commits, branches e Pull Request

- **Branch:** `feature/descricao-curta` para novidades, `fix/descricao-curta` para
  correções, `docs/…` para documentação.
- **Commits:** em português, no imperativo, dizendo o que muda
  ("Adiciona filtro por data na busca", "Corrige título de planilhas CSV").
  Um assunto por commit, quando possível.
- **Um PR por assunto.** PRs pequenos são revisados mais rápido.
- **Nunca inclua** a pasta `dados\`, `instance\`, `uploads\`, `.env`, `secret.key`,
  `build\`, `dist\` nem documentos reais da empresa.

#### Checklist do Pull Request

Copie para a descrição do PR:

```markdown
## O que muda
Resumo em 1–3 frases. Closes #N

## Como testar
1. …
2. …

## Prints
(antes / depois, se mexeu em tela)

## Checklist
- [ ] Testei com o checklist do README
- [ ] Funciona com um banco que já tinha documentos
- [ ] Não adicionei serviços externos nem envio de dados para fora
- [ ] Dependência nova (se houver) está com versão fixa e testei o build
- [ ] Atualizei o README se o comportamento mudou
```

### Revisão e publicação

1. O mantenedor revisa o PR, podendo pedir ajustes, e faz o merge na `main`.
2. Para publicar, o mantenedor gera a versão com `.\build.ps1 -Version AAAA.MM.DD`.
3. Quem já usa recebe só o `dist\AtualizarBaseConhecimento.exe`, que atualiza o
   programa preservando os documentos (ver
   [COMPILAR-E-DISTRIBUIR.md](COMPILAR-E-DISTRIBUIR.md)).

Dúvidas sobre como contribuir: **maicon.vieira@atos.ai**.
