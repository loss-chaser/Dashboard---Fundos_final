# data_loader.py — Leitura dos CSVs comprimidos pré-processados
#
# Esse módulo NÃO baixa nada da CVM/BCB/yfinance em runtime.
# Os dados são gerados pelo build_data.py (que roda 1x/dia via GitHub Actions)
# e ficam commitados em data/*.csv.gz.

from __future__ import annotations
import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from config import NOME_AWR

log = logging.getLogger(__name__)

# Pasta onde build_data.py salva os arquivos
DATA_DIR = Path(__file__).resolve().parent / "data"

# Cache em memória (preenchido por inicializar_global)
_GLOBAL_RAW: dict = {}


def _ler_csv_serie(path: Path, nome: str) -> pd.Series:
    """Lê CSV.gz de Series (1 coluna) e retorna Series com índice de datas."""
    if not path.exists():
        log.warning("Arquivo não encontrado: %s", path)
        return pd.Series(dtype=float, name=nome)
    df = pd.read_csv(path, compression="gzip", index_col=0, parse_dates=True)
    s = df.iloc[:, 0]
    s.name = nome
    return s


def inicializar_global(data_min: date | None = None) -> None:
    """
    Carrega os CSVs gerados por build_data.py para memória.
    O parâmetro data_min é mantido por compatibilidade com app.py mas é ignorado
    (a janela já foi filtrada no build).
    """
    global _GLOBAL_RAW

    if not DATA_DIR.exists():
        log.error(
            "Pasta %s não existe. Rode `python build_data.py` primeiro "
            "para gerar os dados.",
            DATA_DIR,
        )
        return

    log.info("Carregando dados de %s...", DATA_DIR)

    # Cotas (DataFrame pivot Data x Nome do fundo)
    cotas_path = DATA_DIR / "cotas.csv.gz"
    if not cotas_path.exists():
        log.error(
            "cotas.csv.gz não encontrado. Rode `python build_data.py` primeiro."
        )
        return
    df_cotas = pd.read_csv(cotas_path, compression="gzip", index_col=0, parse_dates=True)

    # Ibovespa (Series)
    ibov = _ler_csv_serie(DATA_DIR / "ibov.csv.gz", "Ibovespa")

    # CDI (Series)
    cdi = _ler_csv_serie(DATA_DIR / "cdi.csv.gz", "CDI")

    # PL (Series)
    pl_path = DATA_DIR / "pl.csv.gz"
    if pl_path.exists():
        pl = pd.read_csv(pl_path, compression="gzip", index_col=0).iloc[:, 0]
    else:
        pl = pd.Series(dtype=float)

    # Metadata
    meta_path = DATA_DIR / "metadata.json"
    if meta_path.exists():
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            log.info(
                "Dataset: %d dias, %d fundos, atualizado em %s (última cota: %s)",
                meta.get("n_dias", "?"),
                meta.get("n_fundos", "?"),
                meta.get("data_atualizacao", "?"),
                meta.get("ultima_cota", "?"),
            )
        except Exception as e:
            log.warning("Erro lendo metadata.json: %s", e)
    else:
        log.info(
            "Dataset carregado: %d dias, %d fundos.",
            len(df_cotas),
            len(df_cotas.columns),
        )

    _GLOBAL_RAW = {
        "df_cotas": df_cotas,
        "ibov": ibov,
        "cdi": cdi,
        "pl": pl,
    }


def filtrar_periodo(data_busca: date, data_fim: date) -> dict:
    """
    Filtra o dataset global pela janela [data_busca, data_fim].
    Retorna o mesmo dict que carregar_tudo() retornava antes.
    """
    if not _GLOBAL_RAW:
        inicializar_global()
        if not _GLOBAL_RAW:
            raise RuntimeError(
                "Dataset global não inicializado e não há dados em data/. "
                "Rode `python build_data.py` primeiro."
            )

    df_cotas = _GLOBAL_RAW["df_cotas"]
    ibov = _GLOBAL_RAW["ibov"]
    cdi = _GLOBAL_RAW["cdi"]
    pl = _GLOBAL_RAW["pl"]

    # Respeita a primeira cota disponível do AWR (nunca antes dela)
    if NOME_AWR in df_cotas.columns:
        serie_awr = df_cotas[NOME_AWR].dropna()
        awr_inicio = (
            serie_awr.index[0].date() if not serie_awr.empty else data_busca
        )
        data_ini = max(awr_inicio, data_busca)
    else:
        data_ini = data_busca

    ts_ini = pd.Timestamp(data_ini)
    ts_fim = pd.Timestamp(data_fim)

    df_f = df_cotas.loc[(df_cotas.index >= ts_ini) & (df_cotas.index <= ts_fim)].copy()
    ibov_f = (
        ibov.loc[(ibov.index >= ts_ini) & (ibov.index <= ts_fim)].copy()
        if not ibov.empty else ibov
    )
    cdi_f = (
        cdi.loc[(cdi.index >= ts_ini) & (cdi.index <= ts_fim)].copy()
        if not cdi.empty else cdi
    )

    return {
        "df_cotas": df_f,
        "ibov": ibov_f,
        "cdi": cdi_f,
        "pl": pl,
        "data_ini": data_ini,
        "data_fim": data_fim,
    }