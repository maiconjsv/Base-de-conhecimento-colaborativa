# Base de Conhecimento

Aplicação web interna (Python + Flask) para documentar coisas do trabalho.
Você só **anexa ou arrasta** o(s) arquivo(s); o sistema lê cada um e monta o
registro sozinho — título, resumo e palavras-chave — e o documento fica
localizável por **busca full-text** (qualquer palavra do conteúdo, além de
título, descrição e tags).

> **Quer ajudar?** O projeto é colaborativo. Veja [Como contribuir](#como-contribuir):
> lá estão o passo a passo, as receitas para as mudanças mais comuns e o checklist
> do Pull Request. Suporte: **maicon.vieira@atos.ai** · GitHub: **[@maiconjsv](https://github.com/maiconjsv)**.

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
  aparecem como tabela com as linhas que citam os termos. O número de cada linha
  abre a pseudoplanilha naquele ponto (`?sheet=<id>&row=<n>`). Um termo que aparece
  no cabeçalho ou no nome da aba conta para todas as linhas daquela aba. Planilhas
  enviadas antes desse recurso são estruturadas automaticamente na inicialização
  (`backfill_sheets`). Limites: 50 abas, 20 mil linhas por aba, 80 colunas.
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
  models.py       User, Document, DocumentImage, DocumentSheet, SheetRow, DocumentFingerprint
  extract.py      extração de texto + metadados embutidos por formato
  images.py       extração das imagens embutidas + miniaturas (Pillow)
  sheets.py       planilhas estruturadas: leitura, gravação, pseudoplanilha
  search.py       consulta FTS5 (bm25 + snippet) + contagem de ocorrências
  locator.py      acha todas as ocorrências dos termos dentro de um documento
  ask.py          assistente "Perguntar": palavras-chave, pontuação de trechos
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
config.py         configuração (SECRET_KEY, limites, extensões, KB_DATA_DIR, contato)
run.py            ponto de entrada web (desenvolvimento / servidor)
desktop.py        ponto de entrada do programa Windows (janela + servidor local)
updater.py        AtualizarBaseConhecimento.exe (troca o programa, preserva dados\)
BaseConhecimento.spec / Atualizador.spec / build.ps1   empacotamento com PyInstaller
scripts/make_zip.py   gera o payload.zip do atualizador (usado pelo build.ps1)
CONTRIBUTING.md   atalho para a seção "Como contribuir" (o GitHub mostra em issues/PRs)
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
  do `style.css`). Não use cores soltas.
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
