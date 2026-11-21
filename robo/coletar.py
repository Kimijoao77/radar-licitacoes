#!/usr/bin/env python3
"""Radar de Licitações — coleta as compras públicas com propostas abertas.

Fonte: API de consultas do PNCP (Portal Nacional de Contratações Públicas),
pública e sem cadastro: https://pncp.gov.br/api/consulta

O que o robô faz:
  1. baixa todas as contratações do estado que ainda recebem propostas;
  2. filtra POR CONTA PRÓPRIA as cidades da região (a API pode ignorar filtros
     sem avisar, então nada do que ela devolve é aceito sem conferir);
  3. classifica cada compra por ramo, pelas palavras do objeto;
  4. grava docs/dados.json, que a página docs/index.html mostra.

Só usa a biblioteca padrão do Python. Uso:
    python robo/coletar.py                  # coleta de verdade
    python robo/coletar.py --entrada X.json # usa páginas salvas (teste, sem internet)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
API = "https://pncp.gov.br/api/consulta/v1/contratacoes/proposta"
TAMANHO_PAGINA = 50          # a API aceita de 10 a 50 nas contratações
PAUSA_ENTRE_CHAMADAS = 5.0   # ~12 chamadas por minuto; rajadas levam HTTP 429
MAX_PAGINAS = 400            # trava de segurança
MODALIDADES = range(1, 14)   # 1 a 13, usadas só se a API exigir modalidade
BRT = timezone(timedelta(hours=-3))


# ---------------------------------------------------------------- texto ----
def normalizar(texto: str) -> str:
    """minúsculas, sem acento, só letras/números e espaços simples."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _regex_da_palavra_chave(chave: str) -> re.Pattern:
    """'pneu*' casa pneu, pneus, pneumatico; 'obra' casa só a palavra inteira."""
    padrao = []
    for tok in chave.lower().split():
        base = normalizar(tok.replace("*", ""))
        if not base:
            continue
        padrao.append(re.escape(base) + (r"[a-z0-9]*" if tok.endswith("*") else ""))
    return re.compile(r"\b" + r"\s+".join(padrao) + r"\b")


def preparar_ramos(ramos: dict[str, list[str]]) -> list[tuple[str, list[re.Pattern]]]:
    return [(nome, [_regex_da_palavra_chave(c) for c in chaves]) for nome, chaves in ramos.items()]


def classificar(objeto: str, ramos_prontos) -> str:
    """Ramo com mais palavras-chave encontradas; empate fica com o que vem antes."""
    texto = normalizar(objeto).replace("mao de obra", " ")
    melhor, pontos = "Outros", 0
    for nome, padroes in ramos_prontos:
        n = sum(1 for p in padroes if p.search(texto))
        if n > pontos:
            melhor, pontos = nome, n
    return melhor


# ------------------------------------------------------------------ API ----
def chamar(params: dict) -> tuple[int, dict | None]:
    """GET com novas tentativas. Devolve (status, json). 204 = nenhum registro."""
    url = API + "?" + urllib.parse.urlencode(params)
    espera = 20.0
    for tentativa in range(5):
        req = urllib.request.Request(url, headers={"accept": "application/json",
                                                   "user-agent": "radar-licitacoes/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                if r.status == 204:
                    return 204, None
                corpo = r.read().decode("utf-8", "replace")
                try:
                    return r.status, json.loads(corpo)
                except json.JSONDecodeError:
                    status = 502  # veio HTML ou lixo: trata como falha temporária
        except urllib.error.HTTPError as e:
            status = e.code
            if status in (400, 404, 422):
                return status, None
        except (urllib.error.URLError, TimeoutError, OSError):
            status = 0
        print(f"  tentativa {tentativa + 1} falhou (HTTP {status}); aguardando {espera:.0f}s",
              file=sys.stderr)
        time.sleep(espera)
        espera = min(espera * 2, 180)
    return status, None


def _paginar(base: dict, estado: dict) -> list[dict]:
    brutos, pagina = [], 1
    while pagina <= MAX_PAGINAS:
        status, corpo = chamar({**base, "pagina": pagina, "tamanhoPagina": TAMANHO_PAGINA})
        estado["chamadas"] += 1
        if status == 204:
            break
        if status != 200 or corpo is None:
            estado["erros"].append(f"página {pagina} ({base.get('codigoModalidadeContratacao', 'todas')}): HTTP {status}")
            if status in (400, 404, 422):
                raise ValueError(status)
            break
        itens = corpo.get("data") or []
        brutos.extend(itens)
        total = corpo.get("totalPaginas") or 0
        print(f"  página {pagina}/{total or '?'}: {len(itens)} registros", file=sys.stderr)
        if not itens or (total and pagina >= total):
            break
        pagina += 1
        time.sleep(PAUSA_ENTRE_CHAMADAS)
    return brutos


def coletar(uf: str, data_final: str) -> tuple[list[dict], dict]:
    estado = {"chamadas": 0, "erros": [], "modo": "todas as modalidades de uma vez"}
    base = {"dataFinal": data_final, "uf": uf}
    try:
        return _paginar(base, estado), estado
    except ValueError:
        # Algumas versões da API exigem a modalidade: uma varredura por modalidade.
        estado["modo"] = "uma varredura por modalidade (1 a 13)"
        estado["erros"].clear()
    brutos = []
    for m in MODALIDADES:
        print(f"modalidade {m}", file=sys.stderr)
        try:
            brutos.extend(_paginar({**base, "codigoModalidadeContratacao": m}, estado))
        except ValueError:
            pass
        time.sleep(PAUSA_ENTRE_CHAMADAS)
    return brutos, estado


# ------------------------------------------------------------- registros ----
def _data(valor) -> datetime | None:
    if not valor:
        return None
    try:
        d = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=BRT)   # o PNCP publica em horário de Brasília


def _link(bruto: dict) -> str:
    cnpj = (bruto.get("orgaoEntidade") or {}).get("cnpj")
    ano, seq = bruto.get("anoCompra"), bruto.get("sequencialCompra")
    if not (cnpj and ano and seq):
        m = re.match(r"(\d{14})-\d+-0*(\d+)/(\d{4})", bruto.get("numeroControlePNCP") or "")
        if not m:
            return bruto.get("linkSistemaOrigem") or ""
        cnpj, seq, ano = m.group(1), m.group(2), m.group(3)
    return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}"


def organizar(bruto: dict, ramos_prontos) -> dict:
    orgao = bruto.get("orgaoEntidade") or {}
    unidade = bruto.get("unidadeOrgao") or {}
    objeto = (bruto.get("objetoCompra") or "").strip()
    fim = _data(bruto.get("dataEncerramentoProposta"))
    publicado = _data(bruto.get("dataPublicacaoPncp")) or _data(bruto.get("dataInclusao"))
    valor = bruto.get("valorTotalEstimado")
    return {
        "id": bruto.get("numeroControlePNCP") or "",
        "orgao": (orgao.get("razaoSocial") or unidade.get("nomeUnidade") or "").strip(),
        "cidade": (unidade.get("municipioNome") or "").strip(),
        "uf": (unidade.get("ufSigla") or "").strip(),
        "objeto": objeto,
        "modalidade": (bruto.get("modalidadeNome") or "").strip(),
        "valor": float(valor) if isinstance(valor, (int, float)) and valor > 0 else None,
        "encerra": fim.isoformat() if fim else None,
        "publicado": publicado.isoformat() if publicado else None,
        "ramo": classificar(objeto, ramos_prontos),
        "link": _link(bruto),
    }


def filtrar(brutos: list[dict], cfg: dict, agora: datetime) -> tuple[list[dict], dict]:
    """Confere cidade, estado e prazo aqui, sem confiar nos filtros da API."""
    cidades = {normalizar(c) for c in cfg["cidades"]}
    ramos_prontos = preparar_ramos(cfg["ramos"])
    vistos, saida = set(), []
    conta = {"recebidos": len(brutos), "fora_do_estado": 0, "fora_da_regiao": 0,
             "prazo_encerrado": 0, "repetidos": 0}
    for b in brutos:
        item = organizar(b, ramos_prontos)
        if item["uf"].upper() != cfg["uf"].upper():
            conta["fora_do_estado"] += 1
            continue
        if normalizar(item["cidade"]) not in cidades:
            conta["fora_da_regiao"] += 1
            continue
        fim = _data(item["encerra"])
        if fim is not None and fim <= agora:
            conta["prazo_encerrado"] += 1
            continue
        if item["id"] in vistos:
            conta["repetidos"] += 1
            continue
        vistos.add(item["id"])
        saida.append(item)
    saida.sort(key=lambda i: i["encerra"] or "9999")
    return saida, conta


def mensagem_whatsapp(item: dict) -> str:
    """Texto do aviso que o cliente receberia."""
    linhas = ["🔔 *Nova oportunidade para você*", f"{item['orgao']} ({item['cidade']}/{item['uf']})",
              "", item["objeto"][:280] + ("…" if len(item["objeto"]) > 280 else "")]
    if item["valor"]:
        inteiro = f"{item['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        linhas.append(f"Valor estimado: R$ {inteiro}")
    fim = _data(item["encerra"])
    if fim:
        linhas.append(f"Propostas até: {fim.astimezone(BRT):%d/%m/%Y às %Hh%M}")
    if item["modalidade"]:
        linhas.append(f"Tipo: {item['modalidade']}")
    if item["link"]:
        linhas += ["", f"Edital: {item['link']}"]
    return "\n".join(linhas)


# ----------------------------------------------------------------- main ----
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(RAIZ / "robo" / "config.json"))
    ap.add_argument("--saida", default=str(RAIZ / "docs" / "dados.json"))
    ap.add_argument("--entrada", help="arquivo com registros brutos já baixados (teste sem internet)")
    ap.add_argument("--agora", help="data de referência ISO, só para testes")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    agora = _data(args.agora) if args.agora else datetime.now(BRT)

    if args.entrada:
        brutos = json.loads(Path(args.entrada).read_text(encoding="utf-8"))
        estado = {"chamadas": 0, "erros": [], "modo": "arquivo local (teste)"}
    else:
        data_final = (agora + timedelta(days=cfg.get("dias_a_frente", 60))).strftime("%Y%m%d")
        print(f"Coletando {cfg['uf']} com propostas abertas até {data_final}…", file=sys.stderr)
        brutos, estado = coletar(cfg["uf"], data_final)

    itens, conta = filtrar(brutos, cfg, agora)
    for i in itens:
        if args.entrada:
            i["link"] = ""   # registros de teste não têm edital de verdade
        i["mensagem"] = mensagem_whatsapp(i)

    # Lista vazia só é confiável se a coleta terminou sem erro.
    if not args.entrada and not brutos and estado["erros"]:
        print("Coleta falhou; dados.json anterior foi mantido.", file=sys.stderr)
        for e in estado["erros"]:
            print("  -", e, file=sys.stderr)
        return 1

    por_ramo: dict[str, int] = {}
    for i in itens:
        por_ramo[i["ramo"]] = por_ramo.get(i["ramo"], 0) + 1

    dados = {
        "exemplo": bool(args.entrada),
        "gerado_em": agora.isoformat(timespec="seconds"),
        "fonte": "PNCP — API de consultas (contratações com propostas abertas)",
        "regiao": {"uf": cfg["uf"], "cidades": cfg["cidades"]},
        "coleta": {**estado, **conta},
        "por_ramo": dict(sorted(por_ramo.items(), key=lambda kv: -kv[1])),
        "itens": itens,
    }
    Path(args.saida).parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(dados, ensure_ascii=False, indent=1)
    Path(args.saida).write_text(texto, encoding="utf-8")
    # Mesma coisa em .js, para a página abrir até com dois cliques no arquivo.
    Path(args.saida).with_suffix(".js").write_text(
        "window.DADOS = " + texto.replace("</", "<\\/") + ";\n", encoding="utf-8")
    print(f"{len(itens)} oportunidades na região (de {conta['recebidos']} recebidas). "
          f"Gravado em {args.saida}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
