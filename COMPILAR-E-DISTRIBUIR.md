# Compilar e distribuir a Base de Conhecimento

Guia passo a passo para gerar o programa Windows (`BaseConhecimento.exe`) e
entregá-lo para a empresa.

- **Compilar** = transformar o código em um programa que roda sem instalar Python.
- **Distribuir** = zipar a pasta do programa e mandar para as pessoas.

Quem só vai *usar* o programa não precisa deste guia — basta o `LEIA-ME.txt` que
acompanha o zip.

---

## Parte 1 — Compilar

### 1.1. Pré-requisitos (uma vez por máquina de build)

| Item | Como obter |
|---|---|
| Windows 10 ou 11 (64 bits) | — |
| Python 3.12 (64 bits) | https://www.python.org/downloads/ — na instalação, marque **"Add python.exe to PATH"** |
| O código do projeto | esta pasta (`base-de-conhecimento-semantix`) |

Confirme o Python no PowerShell:

```powershell
python --version      # deve mostrar Python 3.12.x
```

### 1.2. Preparar o ambiente (uma vez)

No PowerShell, **dentro da pasta do projeto**:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-build.txt
```

- `requirements-build.txt` instala tudo o que o programa usa **mais** o
  PyInstaller (a ferramenta que gera o `.exe`).
- Se `Activate.ps1` for bloqueado pela política de execução:

  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  ```

### 1.3. Gerar o executável

```powershell
.\build.ps1 -Clean
```

O `-Clean` apaga builds anteriores. Para builds seguintes pode usar só
`.\build.ps1` (mais rápido).

Se o `.\build.ps1` for bloqueado:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1 -Clean
```

O build leva ~1 a 3 minutos. No fim aparece:

```
OK -> dist\BaseConhecimento
```

### 1.4. O que foi gerado

```
dist\BaseConhecimento\
├─ BaseConhecimento.exe     ← o programa
├─ _internal\               ← bibliotecas (NÃO mexer, NÃO apagar)
├─ dados\                   ← banco, arquivos enviados, imagens, chave de sessão
│   └─ uploads\images\
└─ LEIA-ME.txt              ← instruções para quem receber
```

A pasta `dados\` é o coração da coisa: **todo o conteúdo da base vive ali**.

### 1.5. Testar antes de distribuir

```powershell
dist\BaseConhecimento\BaseConhecimento.exe
```

- Na primeira vez abre a tela **"Configuração inicial"** — crie um usuário
  administrador de teste.
- Suba um documento qualquer, faça uma busca, veja a visualização.
- Feche a janela para encerrar.

Para começar do zero de novo, apague o conteúdo de
`dist\BaseConhecimento\dados\` (deixe só a pasta `uploads\images\` vazia).

---

## Parte 2 — Distribuir

### 2.1. Decidir o que vai dentro da pasta `dados\`

| Situação | O que fazer |
|---|---|
| **Base nova, vazia** | Deixe `dados\` como o build criou. Quem abrir primeiro cria o admin e começa a subir documentos. |
| **Já quero mandar com conteúdo** | Copie a sua pasta `dados\` (a que tem o banco populado) para dentro de `dist\BaseConhecimento\`, substituindo a vazia. Os documentos e usuários vão junto; o programa abre direto no login. |

> A pasta `dados\` de uso normal fica ao lado do `BaseConhecimento.exe` que você
> executa no dia a dia. É essa que você copia quando quer distribuir com conteúdo.

### 2.2. Zipar

Clique com o botão direito na pasta **`BaseConhecimento`** (a pasta inteira, não
só o `.exe`) → **Enviar para → Pasta compactada**.

Ou no PowerShell:

```powershell
Compress-Archive -Path dist\BaseConhecimento -DestinationPath BaseConhecimento.zip -Force
```

### 2.3. Entregar

Mande o `.zip` por e-mail, rede, pen drive — como for.

Instrução para quem recebe (já está no `LEIA-ME.txt`):

1. Extrair a pasta inteira para algum lugar fixo (ex.: `C:\BaseConhecimento`).
2. Abrir `BaseConhecimento.exe`.
3. Se for uma base nova: criar o usuário administrador na primeira tela.
4. Uma janela do programa abre sozinha. Para sair, feche essa janela.

Nada de instalar Python nem nada. Requer só Windows 10/11.

---

## Parte 3 — Atualizar uma distribuição

### Atualizou o **código** (novas telas, correções)

1. `git pull` (ou copie o código novo).
2. `pip install -r requirements-build.txt` (caso tenham mudado dependências).
3. `.\build.ps1 -Clean -Version 2026.09.07` (o `-Version` é opcional; sem ele
   entra a data/hora atual).

O build gera **duas coisas** em `dist\`:

| Arquivo | Para quem | Como usar |
|---|---|---|
| `dist\BaseConhecimento\` (pasta) | **instalação nova** | zipe a pasta inteira e mande (item 2.2) |
| `dist\AtualizarBaseConhecimento.exe` | **quem já usa** | mande só esse arquivo |

**Atualizar quem já usa — mande só o `AtualizarBaseConhecimento.exe`.** A versão
nova do programa vai *embutida* nesse `.exe`. Instrução para a pessoa (também no
`COMO-ATUALIZAR.txt`):

1. Fechar o programa.
2. Copiar `AtualizarBaseConhecimento.exe` para **dentro da pasta do programa**
   (a que tem `BaseConhecimento.exe` e `dados\`).
3. Dar duplo clique nele.

O atualizador:

- encerra o programa se estiver aberto;
- copia a pasta `dados\` para `_backup\dados-<data>` (guarda as 2 mais recentes);
- troca **só** `BaseConhecimento.exe`, `_internal\`, `LEIA-ME.txt` e `versao.txt`;
- **nunca toca** em `dados\`, `.env` nem `secret.key`;
- se falhar no meio da troca, desfaz sozinho;
- reabre o programa no fim.

O `versao.txt` serve só para o atualizador avisar se você tentar aplicar uma
versão igual ou mais antiga do que a instalada.

> Ainda vale reunir os dados de todos numa base só e redistribuir a pasta
> completa quando quiser consolidar — o atualizador resolve o *código*, não a
> *fusão de conteúdo* entre cópias.

### Atualizou só o **conteúdo** (novos documentos)

Não precisa recompilar nem usar o atualizador. Copie a pasta `dados\` atualizada
por cima da antiga na máquina de cada pessoa, ou redistribua o zip completo.

> **Importante:** cada cópia é independente. Se duas pessoas editam cópias
> diferentes, as mudanças **não se juntam sozinhas**. Defina quem é o "dono" da
> base (quem centraliza e redistribui) e combine que os outros não sobem
> documentos nas próprias cópias — ou aceite que a cópia do dono é a oficial.

---

## Parte 4 — Backup e restauração

- **Backup:** copie a pasta `dados\` para um lugar seguro. É só isso.
- **Restaurar:** substitua a pasta `dados\` do programa pela do backup.
- **Migrar de máquina:** leve a pasta `BaseConhecimento` inteira (ou só `dados\`
  se a outra máquina já tem o programa).

---

## Parte 5 — Modo servidor (opcional)

Para um PC servir a base para outros pela rede local, sem janela:

```powershell
$env:KB_NO_WINDOW = "1"
dist\BaseConhecimento\BaseConhecimento.exe
```

O programa sobe em `http://127.0.0.1:5000` e escuta a rede. As outras máquinas
acessam por `http://IP-DO-PC:5000` no navegador. Feche pelo Gerenciador de
Tarefas ou `Ctrl+C` se rodar num terminal visível.

Nesse modo a base é **compartilhada de verdade** (todos veem as mesmas
alterações), mas depende do PC servidor estar ligado.

---

## Parte 6 — Solução de problemas

| Sintoma | Causa / solução |
|---|---|
| **A janela não abre**, só um aviso com um endereço | O programa não achou o Edge/Chrome. Ele abriu no navegador padrão — use o endereço mostrado (`http://127.0.0.1:5000`). O sistema está funcionando normal. |
| **"O Windows protegeu o seu PC" (SmartScreen)** | Normal em `.exe` sem assinatura digital. Clique em **Mais informações → Executar assim mesmo**. Para evitar isso na empresa, seria preciso assinar o executável (certificado de code signing). |
| **Antivírus bloqueia / apaga o `.exe`** | Falso positivo comum com PyInstaller. Adicione a pasta às exceções do antivírus, ou peça ao TI para liberar. |
| **"O servidor local não respondeu a tempo"** | Antivírus/firewall barrando o `127.0.0.1`, ou a porta 5000 ocupada. O programa tenta as portas 5000–5050 automaticamente; se todas falharem, feche o que estiver usando a porta. |
| **Abre sempre na tela de configuração inicial** | A pasta `dados\` está vazia ou não está junto do `.exe`. Confirme que `dados\kb.sqlite` existe ao lado do `BaseConhecimento.exe`. |
| **Perdi documentos depois de atualizar** | Só acontece se alguém substituiu a pasta inteira em vez de usar o `AtualizarBaseConhecimento.exe`. Restaure de `_backup\dados-<data>` (renomeie para `dados`) ou do seu backup. Use sempre o atualizador. |
| **O atualizador diz "falhou e foi desfeita"** | Programa em `C:\Program Files` (sem permissão de escrita). Mova a pasta para `C:\BaseConhecimento` ou rode o atualizador como administrador. Os dados não foram tocados. |
| **O atualizador diz "precisa estar DENTRO da pasta do programa"** | O `.exe` foi executado de fora. Copie-o para junto do `BaseConhecimento.exe`. |
| **`build.ps1` falha com erro de política de execução** | `powershell -ExecutionPolicy Bypass -File .\build.ps1 -Clean` |
| **`pip install` falha** | Confirme que a venv está ativa (`.\.venv\Scripts\Activate.ps1`) e que há internet. |
| **PyInstaller não encontrado** | `pip install -r requirements-build.txt` dentro da venv. |

---

## Referência rápida

```powershell
# preparar (uma vez)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-build.txt

# compilar (gera a pasta do programa E o AtualizarBaseConhecimento.exe)
.\build.ps1 -Clean

# testar
dist\BaseConhecimento\BaseConhecimento.exe

# empacotar instalacao nova
Compress-Archive -Path dist\BaseConhecimento -DestinationPath BaseConhecimento.zip -Force

# atualizar quem ja usa: mande so este arquivo
dist\AtualizarBaseConhecimento.exe
```

| Variável de ambiente | Efeito |
|---|---|
| `KB_NO_WINDOW=1` | Roda sem janela (modo servidor) |
| `KB_DATA_DIR=<pasta>` | Usa outra pasta de dados em vez de `dados\` ao lado do exe |
