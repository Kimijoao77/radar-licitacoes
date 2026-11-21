#!/usr/bin/env python3
"""Gera registros FICTÍCIOS no mesmo formato que a API do PNCP devolve.

Servem só para testar o robô e mostrar a página sem internet. Nenhuma destas
compras existe: os órgãos se chamam "Órgão de exemplo" de propósito.
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# (cidade, uf, objeto, valor, encerra, modalidade)
LINHAS = [
    ("Cascavel", "PR", "Aquisição de pneus novos para a frota de veículos leves e caminhões", 58400.00, "2026-11-27T09:00:00", "Pregão - Eletrônico"),
    ("Cascavel", "PR", "Registro de preços para gêneros alimentícios destinados à merenda escolar", 412300.50, "2026-12-03T08:30:00", "Pregão - Eletrônico"),
    ("Toledo", "PR", "Contratação de empresa para fornecimento de materiais de limpeza e higiene", 31750.00, "2026-11-24T14:00:00", "Dispensa"),
    ("Toledo", "PR", "Aquisição de computadores, notebooks e impressoras para as secretarias", 189900.00, "2026-12-09T09:00:00", "Pregão - Eletrônico"),
    ("Corbélia", "PR", "Aquisição de material de expediente e papelaria", 12480.00, "2026-11-23T17:00:00", "Dispensa"),
    ("Cafelândia", "PR", "Contratação de empresa de engenharia para reforma da unidade básica de saúde", 640000.00, "2026-12-15T09:00:00", "Concorrência - Eletrônica"),
    ("Céu Azul", "PR", "Aquisição de medicamentos para a farmácia básica municipal", 96200.00, "2026-12-01T08:00:00", "Pregão - Eletrônico"),
    ("Santa Tereza do Oeste", "PR", "Aquisição de uniformes e camisetas para servidores", 22900.00, "2026-11-26T10:00:00", "Dispensa"),
    ("Medianeira", "PR", "Prestação de serviço de manutenção preventiva e corretiva de ar condicionado", 47300.00, "2026-12-04T09:30:00", "Pregão - Eletrônico"),
    ("Palotina", "PR", "Aquisição de sementes, mudas e adubo para o viveiro municipal", 18650.00, "2026-11-30T16:00:00", "Dispensa"),
    ("Assis Chateaubriand", "PR", "Aquisição de peças automotivas e lubrificantes para máquinas pesadas", 133000.00, "2026-12-11T09:00:00", "Pregão - Eletrônico"),
    ("Nova Aurora", "PR", "Confecção de impressos gráficos e banners para eventos da secretaria de cultura", 9800.00, "2026-11-25T12:00:00", "Dispensa"),
    ("Cascavel", "PR", "Aquisição de mobiliário escolar: carteiras, mesas e armários", 274500.00, "2026-12-18T09:00:00", "Pregão - Eletrônico"),
    ("Guaraniaçu", "PR", "Credenciamento de leiloeiro oficial", None, "2026-12-20T17:00:00", "Credenciamento"),
    # Os de baixo existem para provar que o filtro próprio funciona:
    ("Curitiba", "PR", "Aquisição de pneus (fora da região, deve ser descartado)", 80000.00, "2026-12-02T09:00:00", "Pregão - Eletrônico"),
    ("Cascavel", "CE", "Aquisição de gêneros alimentícios (homônima no Ceará, deve ser descartado)", 50000.00, "2026-12-02T09:00:00", "Pregão - Eletrônico"),
    ("Toledo", "PR", "Aquisição de material de limpeza (prazo vencido, deve ser descartado)", 15000.00, "2026-11-18T09:00:00", "Dispensa"),
]


def registros():
    saida = []
    for n, (cidade, uf, objeto, valor, encerra, modalidade) in enumerate(LINHAS, start=1):
        cnpj = f"{n:02d}000000000100"
        saida.append({
            "numeroControlePNCP": f"{cnpj}-1-{n:06d}/2026",
            "anoCompra": 2026,
            "sequencialCompra": n,
            "objetoCompra": objeto,
            "valorTotalEstimado": valor,
            "dataPublicacaoPncp": "2026-11-17T10:00:00",
            "dataEncerramentoProposta": encerra,
            "modalidadeNome": modalidade,
            "orgaoEntidade": {"cnpj": cnpj, "razaoSocial": f"Órgão de exemplo {n} (fictício)"},
            "unidadeOrgao": {"municipioNome": cidade, "ufSigla": uf},
        })
    saida.append(dict(saida[0]))  # repetido de propósito
    return saida


if __name__ == "__main__":
    destino = RAIZ / "robo" / "exemplo_bruto.json"
    destino.write_text(json.dumps(registros(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(registros())} registros fictícios em {destino}")
