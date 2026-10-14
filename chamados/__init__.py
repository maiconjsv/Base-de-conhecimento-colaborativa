"""Acompanhamento de Chamados: programa a parte (AcompanhamentoChamados.exe).

Lista compacta dos chamados que a pessoa acompanha (numero, titulo, status,
prioridade, prazo) e alertas que cobram o acompanhamento:
- cadencia: "sem atualizacao ha X" a cada N minutos (padrao por prioridade,
  ajustavel por chamado);
- prazo: avisos antes de vencer e repetidos depois de estourado;
- horario de trabalho: fora dele, os alertas esperam.

Modulos:
- store.py   banco SQLite (dados\\chamados.sqlite), configuracoes, historico;
- alertas.py regras dos alertas (funcoes puras, testaveis sem interface);
- app.py     interface (tkinter, nativa do Windows, sem navegador).
"""
