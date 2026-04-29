# build_data.py — Pré-processa CVM + Ibovespa + CDI em CSVs comprimidos
#
# Roda 1x por dia (via GitHub Actions) e gera arquivos pequenos em data/:
#   data/cotas.csv.gz      — cotas diárias dos fundos (pivot Data x Nome)
#   data/ibov.csv.gz       — preços diários do Ibovespa
#   data/cdi.csv.gz        — retornos diários do CDI
#   data/pl.csv.gz         — patrimônio líquido por fundo (último valor)
#   data/metadata.json     — info da última atualização
#
# Esses arquivos são commitados no repo. O app.py NÃO baixa nada em runtime —
# só lê os CSVs (rápido, leve, sem dependência de rede da CVM/BCB).

from __future__ import annotations
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# Garante que o script roda na pasta dele
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from config import FUNDOS, CNPJ_PARA_NOME
from _cvm_downloader import (
    garantir_cache,
    carregar_cotas,
    carregar_ibovespa,
    carregar_cdi,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# Janela: últimos 3 anos
ANOS_HISTORICO = 3


def main() -> None:
    data_fim = date.today()
    data_ini = data_fim - timedelta(days=365 * ANOS_HISTORICO)

    log.info("=" * 60)
    log.info("BUILD DATA — janela %s a %s (%d anos)",
             data_ini, data_fim, ANOS_HISTORICO)
    log.info("=" * 60)

    out_dir = SCRIPT_DIR / "data"
    out_dir.mkdir(exist_ok=True)

    # 1) CVM cotas
    log.info("[1/4] Baixando ZIPs CVM...")
    zips = garantir_cache(data_ini, data_fim)
    if not zips:
        log.error("Nenhum ZIP CVM disponível. Abortando.")
        sys.exit(1)

    log.info("[2/4] Lendo cotas dos %d ZIPs...", len(zips))
    resultado = carregar_cotas(zips)
    if isinstance(resultado, tuple):
        df_cotas, pl_series = resultado
    else:
        df_cotas, pl_series = resultado, pd.Series(dtype=float)

    if df_cotas.empty:
        log.error("Nenhuma cota encontrada para os CNPJs configurados.")
        sys.exit(1)

    # Filtra janela e renomeia CNPJ → nome
    df_cotas = df_cotas.loc[str(data_ini):str(data_fim)].copy()
    df_cotas = df_cotas.rename(columns=CNPJ_PARA_NOME)
    pl_named = pl_series.rename(index=CNPJ_PARA_NOME)

    log.info("Cotas: %d dias x %d fundos", len(df_cotas), len(df_cotas.columns))

    # 2) Ibovespa
    log.info("[3/4] Baixando Ibovespa...")
    ibov = carregar_ibovespa(data_ini, data_fim)
    log.info("Ibov: %d observações", len(ibov))

    # 3) CDI
    log.info("[4/4] Baixando CDI...")
    cdi = carregar_cdi(data_ini, data_fim)
    log.info("CDI: %d observações", len(cdi))

    # 4) Salva CSVs comprimidos (gzip)
    log.info("Salvando CSVs comprimidos em %s", out_dir)

    df_cotas.to_csv(out_dir / "cotas.csv.gz", compression="gzip")
    log.info("  cotas.csv.gz   — %.1f KB",
             (out_dir / "cotas.csv.gz").stat().st_size / 1024)

    ibov.to_frame().to_csv(out_dir / "ibov.csv.gz", compression="gzip")
    log.info("  ibov.csv.gz    — %.1f KB",
             (out_dir / "ibov.csv.gz").stat().st_size / 1024)

    if not cdi.empty:
        cdi.to_frame().to_csv(out_dir / "cdi.csv.gz", compression="gzip")
        log.info("  cdi.csv.gz     — %.1f KB",
                 (out_dir / "cdi.csv.gz").stat().st_size / 1024)

    if not pl_named.empty:
        pl_named.to_frame(name="PL").to_csv(
            out_dir / "pl.csv.gz", compression="gzip"
        )
        log.info("  pl.csv.gz      — %.1f KB",
                 (out_dir / "pl.csv.gz").stat().st_size / 1024)

    # Limpa parquets antigos se existirem
    for old in ["cotas.parquet", "ibov.parquet", "cdi.parquet", "pl.parquet"]:
        old_path = out_dir / old
        if old_path.exists():
            old_path.unlink()
            log.info("  Removido (antigo): %s", old)

    # 5) Metadata
    metadata = {
        "data_atualizacao": pd.Timestamp.now().isoformat(),
        "data_ini": str(data_ini),
        "data_fim": str(data_fim),
        "anos_historico": ANOS_HISTORICO,
        "n_fundos": int(len(df_cotas.columns)),
        "n_dias": int(len(df_cotas)),
        "ultima_cota": str(df_cotas.index[-1].date()) if len(df_cotas) > 0 else None,
        "fundos": list(df_cotas.columns),
    }
    with open(out_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    log.info("  metadata.json")

    log.info("=" * 60)
    log.info("✓ BUILD CONCLUÍDO")
    log.info("  Última cota: %s", metadata["ultima_cota"])
    log.info("  %d fundos, %d dias", metadata["n_fundos"], metadata["n_dias"])
    log.info("=" * 60)


if __name__ == "__main__":
    main()