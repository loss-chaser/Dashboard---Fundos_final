# _cvm_downloader.py — Funções de download da CVM/Ibov/CDI
#
# Esse módulo SÓ é usado pelo build_data.py (que roda offline 1x/dia).
# O app.py em runtime NÃO importa nada daqui.

from __future__ import annotations
import json
import logging
import zipfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from config import (
    PASTA_DADOS, PASTA_CACHE, URL_CVM, URL_CVM_HIST, URL_BCB_CDI,
    TODOS_CNPJS,
)

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# DOWNLOAD CVM
# ─────────────────────────────────────────────────────────────────────────────
def _baixar_zip(url: str, destino: Path) -> bool:
    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 200:
            destino.write_bytes(r.content)
            return True
    except Exception as e:
        log.warning("Erro ao baixar %s: %s", url, e)
    return False


def garantir_cache(data_ini: date, data_fim: date) -> list[Path]:
    zips_ok: list[Path] = []
    cur_ano, cur_mes = data_ini.year, data_ini.month
    while (cur_ano, cur_mes) <= (data_fim.year, data_fim.month):
        nome = f"inf_diario_fi_{cur_ano}{cur_mes:02d}.zip"
        dest = PASTA_DADOS / nome
        if not dest.exists():
            log.info("Baixando %s/%02d...", cur_ano, cur_mes)
            ok = _baixar_zip(URL_CVM.format(ano=cur_ano, mes=cur_mes), dest)
            if not ok:
                ok = _baixar_zip(URL_CVM_HIST.format(ano=cur_ano, mes=cur_mes), dest)
            if not ok:
                dest.unlink(missing_ok=True)
        if dest.exists():
            zips_ok.append(dest)
        cur_mes += 1
        if cur_mes > 12:
            cur_mes = 1
            cur_ano += 1
    return zips_ok


# ─────────────────────────────────────────────────────────────────────────────
# LEITURA DOS ZIPS
# ─────────────────────────────────────────────────────────────────────────────
def carregar_cotas(zips: list[Path]):
    partes: list[pd.DataFrame] = []
    for caminho in zips:
        try:
            with zipfile.ZipFile(caminho, "r") as z:
                for arq in z.namelist():
                    if not (arq.endswith(".csv") and "inf_diario_fi_" in arq):
                        continue
                    with z.open(arq) as f:
                        df = pd.read_csv(
                            f, sep=";", encoding="latin1",
                            low_memory=False, dtype=str,
                        )
                    col_cnpj = (
                        "CNPJ_FUNDO"
                        if "CNPJ_FUNDO" in df.columns
                        else "CNPJ_FUNDO_CLASSE"
                    )
                    if col_cnpj not in df.columns:
                        continue
                    df["CNPJ"] = (
                        df[col_cnpj].astype(str)
                        .str.replace(r"\D", "", regex=True)
                        .str.zfill(14)
                    )
                    df = df[df["CNPJ"].isin(TODOS_CNPJS)].copy()
                    if df.empty:
                        continue
                    cols_out = ["CNPJ", "DT_COMPTC", "VL_QUOTA"]
                    if "VL_PATRIM_LIQ" in df.columns:
                        cols_out.append("VL_PATRIM_LIQ")
                    df = df[cols_out].copy()
                    df.rename(columns={
                        "DT_COMPTC": "Data",
                        "VL_QUOTA": "Cota",
                        "VL_PATRIM_LIQ": "PL",
                    }, inplace=True)
                    df["Cota"] = pd.to_numeric(
                        df["Cota"].str.replace(",", ".", regex=False),
                        errors="coerce",
                    )
                    if "PL" in df.columns:
                        df["PL"] = pd.to_numeric(
                            df["PL"].str.replace(",", ".", regex=False),
                            errors="coerce",
                        )
                    partes.append(df)
        except Exception as e:
            log.warning("Erro no ZIP %s: %s", caminho.name, e)

    if not partes:
        return pd.DataFrame()

    df_all = pd.concat(partes, ignore_index=True)
    df_all["Data"] = pd.to_datetime(df_all["Data"])
    df_all = (
        df_all.sort_values(
            ["CNPJ", "Data"] + (["PL"] if "PL" in df_all.columns else []),
            ascending=[True, True] + ([False] if "PL" in df_all.columns else []),
        )
        .drop_duplicates(subset=["CNPJ", "Data"], keep="first")
    )

    pivot = df_all.pivot_table(index="Data", columns="CNPJ", values="Cota")
    pivot.columns.name = None

    pl_df = (
        df_all.dropna(subset=["PL"])
        .sort_values("Data")
        .drop_duplicates(subset=["CNPJ"], keep="last")
        .set_index("CNPJ")["PL"]
    ) if "PL" in df_all.columns else pd.Series(dtype=float)

    return pivot.sort_index(), pl_df


# ─────────────────────────────────────────────────────────────────────────────
# IBOVESPA
# ─────────────────────────────────────────────────────────────────────────────
def carregar_ibovespa(data_ini: date, data_fim: date) -> pd.Series:
    try:
        ibov = yf.Ticker("^BVSP").history(
            start=str(data_ini),
            end=str(data_fim + timedelta(days=1)),
        )["Close"]
        ibov.index = ibov.index.tz_localize(None).normalize()
        ibov.name = "Ibovespa"
        return ibov
    except Exception as e:
        log.error("Erro ao baixar Ibovespa: %s", e)
        return pd.Series(dtype=float, name="Ibovespa")


# ─────────────────────────────────────────────────────────────────────────────
# CDI — BCB SGS série 12
# ─────────────────────────────────────────────────────────────────────────────
def carregar_cdi(data_ini: date, data_fim: date) -> pd.Series:
    """CDI diário via API BCB SGS (série 12). Retorna Series com ret diário em decimal."""
    cache_file = PASTA_CACHE / "cdi_diario.parquet"

    cached = None
    if cache_file.exists():
        try:
            cached = pd.read_parquet(cache_file)
        except Exception:
            cached = None

    di = data_ini.strftime("%d/%m/%Y")
    df_str = data_fim.strftime("%d/%m/%Y")
    url = URL_BCB_CDI.replace("{di}", di).replace("{df}", df_str)

    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "awr-dash/1.0"})
        if resp.status_code == 200:
            dados = json.loads(resp.text)
            if dados:
                df = pd.DataFrame(dados)
                df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
                df["valor"] = pd.to_numeric(
                    df["valor"].astype(str).str.replace(",", "."), errors="coerce"
                )
                df["ret"] = df["valor"] / 100
                df = df.dropna(subset=["data", "ret"]).set_index("data")["ret"]
                df = df.sort_index()
                df.name = "CDI"

                df.to_frame().to_parquet(cache_file)
                return df.loc[
                    (df.index >= pd.Timestamp(data_ini))
                    & (df.index <= pd.Timestamp(data_fim))
                ]
    except Exception as e:
        log.warning("Erro ao buscar CDI do BCB: %s", e)

    if cached is not None and not cached.empty:
        s = cached.iloc[:, 0]
        s.name = "CDI"
        return s.loc[
            (s.index >= pd.Timestamp(data_ini))
            & (s.index <= pd.Timestamp(data_fim))
        ]

    log.warning("CDI não disponível.")
    return pd.Series(dtype=float, name="CDI")
