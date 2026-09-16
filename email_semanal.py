# email_semanal.py — AWR Capital
# =============================================================================
# Email semanal com link pro dashboard interativo.
# Carrega os dados gerados pelo build_data.py, calcula 3 destaques (AWR
# acumulado, AWR semana, Ibovespa acumulado) e dispara email via Graph API.
#
# Rodar manualmente:
#   python email_semanal.py
# =============================================================================

from __future__ import annotations
import logging, sys
from datetime import datetime, date
from pathlib import Path

import numpy as np
import pandas as pd

# Imports locais (config, data_loader)
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

# email_sender.py vive em VD_codigos/ (2 níveis acima)
_VD_DIR = _SCRIPT_DIR.parent
if str(_VD_DIR) not in sys.path:
    sys.path.insert(0, str(_VD_DIR))

from config import NOME_AWR, LINK_DASHBOARD
from data_loader import filtrar_periodo
from email_sender import send_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _fmt(v: float) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    sinal = "+" if v >= 0 else ""
    return f"{sinal}{v*100:.2f}%"


def main() -> int:
    hoje = date.today()
    print(f"\n[AWR] Email semanal · {hoje.strftime('%d/%m/%Y')}")

    # Carrega dados pré-processados (build_data.py já rodou hoje cedo)
    dados = filtrar_periodo(data_busca=date(2024, 1, 1), data_fim=hoje)
    df_cotas = dados["df_cotas"].join(dados["ibov"], how="outer")

    # Retorno acumulado base na primeira observação
    df_filled = df_cotas.ffill()
    df_rent = (df_filled / df_filled.bfill().iloc[0]) - 1

    # Retorno da última semana (7 dias corridos)
    hoje_ts = df_rent.index[-1]
    uma_sem = hoje_ts - pd.Timedelta(days=7)
    idx_ini = df_rent.index.searchsorted(uma_sem)
    rent_semana = ((1 + df_rent.iloc[-1]) / (1 + df_rent.iloc[idx_ini])) - 1

    # Destaques
    awr_acum = df_rent[NOME_AWR].iloc[-1] if NOME_AWR in df_rent.columns else np.nan
    awr_sem  = rent_semana.get(NOME_AWR, np.nan)
    ibov_ac  = df_rent["Ibovespa"].iloc[-1] if "Ibovespa" in df_rent.columns else np.nan
    ibov_sem = rent_semana.get("Ibovespa", np.nan)

    # Datas de referência (período da semana usado na conta)
    data_ultimo_pregao = hoje_ts.strftime("%d/%m/%Y")
    data_ini_sem = df_rent.index[idx_ini].strftime("%d/%m/%Y")
    data_fim_sem = hoje.strftime("%d/%m/%Y")
    data_base    = df_rent.index[0].strftime("%d/%m/%Y")

    print(f"  Último pregão nos dados: {data_ultimo_pregao}")
    print(f"  Período semanal: {data_ini_sem} → {data_fim_sem}")
    print(f"  {NOME_AWR}: {_fmt(awr_acum)} acumulado · {_fmt(awr_sem)} na semana")
    print(f"  Ibovespa: {_fmt(ibov_ac)} acumulado · {_fmt(ibov_sem)} na semana")

    destaques = {
        "top":      f"{NOME_AWR}: {_fmt(awr_acum)} acumulado · {_fmt(awr_sem)} na semana",
        "bottom":   f"Ibovespa: {_fmt(ibov_ac)} acumulado · {_fmt(ibov_sem)} na semana",
        "universo": (
            f"Semana: {data_ini_sem} → {data_fim_sem} · "
            f"Acumulado desde {data_base} · "
            f"{len(df_cotas.columns) - 1} fundos comparáveis"
        ),
    }

    ok = send_report(
        tipo       = "dashboard",   # tipo "dashboard" já está configurado p/ botão CTA grande
        dt         = datetime.now(),
        destaques  = destaques,
        link_nuvem = LINK_DASHBOARD,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())