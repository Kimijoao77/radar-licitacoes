# Radar de Licitações Oeste PR (protótipo)

Robô que lista as compras públicas de Cascavel e região que ainda recebem
propostas, separa por ramo e monta o aviso de WhatsApp de cada uma.

## Estado atual

- A página (`docs/index.html`) funciona e hoje mostra **dados de exemplo inventados**.
- O robô (`robo/coletar.py`) foi testado com um servidor falso (paginação,
  erro 429, API exigindo modalidade) mas **ainda não rodou contra o portal de
  verdade**. A primeira execução real pode pedir ajuste em nome de campo.

## Como rodar

    python robo/coletar.py

Precisa só de Python 3.10+ e internet. Leva alguns minutos, porque o robô
espera 5 segundos entre as chamadas para o portal não bloquear. No fim ele
grava `docs/dados.json` e `docs/dados.js`; abra `docs/index.html` para ver.

## Rodar sozinho todo dia (GitHub Actions)

1. Crie um repositório no GitHub e envie esta pasta inteira.
2. Em Settings > Pages, escolha a branch `main` e a pasta `/docs`.
3. Em Actions, abra "Coletar licitações" e clique em "Run workflow".

Depois disso ele roda todo dia às 06h17 e a página fica em
`https://SEU-USUARIO.github.io/NOME-DO-REPO/`.

## O que ajustar

- `robo/config.json`: lista de cidades e palavras-chave de cada ramo.
  `pneu*` casa pneu, pneus, pneumático; sem asterisco casa só a palavra exata.

## Arquivos

- `robo/coletar.py`: coleta, filtra, classifica e grava o resultado.
- `robo/gerar_exemplo.py`: cria os registros fictícios usados no teste.
- `docs/`: a página e os dados que ela lê.
- `.github/workflows/coletar.yml`: agendamento diário.
