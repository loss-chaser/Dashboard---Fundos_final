# calculos.py — AWR Capital
# =============================================================================
# Script de email semanal. Usa os módulos compartilhados do dashboard
# (data_loader, metrics, config) e importa email_sender da pasta VD_codigos.
#
# Rodar manualmente (só calcula, sem email):
#   python calculos.py
#
# Rodar com envio (agendador de tarefas):
#   python calculos.py --email
# =============================================================================

from __future__ import annotations
import logging, sys
from datetime import datetime, date
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from matplotlib.lines import Line2D

# Garante imports locais (config, data_loader, metrics)
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

# email_sender.py está em VD_codigos/ (3 níveis acima deste arquivo)
_VD_DIR = Path(__file__).resolve().parent.parent.parent
if str(_VD_DIR) not in sys.path:
    sys.path.insert(0, str(_VD_DIR))

from config import (
    PASTA_SAIDA, NOME_AWR, LINK_DASHBOARD,
    COR_AWR_BG, COR_AWR, COR_IBOV, COR_OUTROS,
)
from data_loader import carregar_tudo
from metrics import retorno_entre

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICO PNG
# ─────────────────────────────────────────────────────────────────────────────
def gerar_grafico(df_rent: pd.DataFrame, data_ini: date, data_fim: date) -> Path:
    fig, ax = plt.subplots(figsize=(14, 7), facecolor=COR_AWR_BG)
    ax.set_facecolor(COR_AWR_BG)

    for col in df_rent.columns:
        if col in (NOME_AWR, "Ibovespa"):
            continue
        ax.plot(df_rent.index, df_rent[col] * 100,
                color=COR_OUTROS, linewidth=0.9, alpha=0.4)

    if "Ibovespa" in df_rent.columns:
        ax.plot(df_rent.index, df_rent["Ibovespa"] * 100,
                color=COR_IBOV, linewidth=1.8, linestyle="--",
                alpha=0.9, label="Ibovespa")

    if NOME_AWR in df_rent.columns:
        ax.plot(df_rent.index, df_rent[NOME_AWR] * 100,
                color=COR_AWR, linewidth=2.8, zorder=10, label=NOME_AWR)

    ax.axhline(0, color="white", linewidth=0.5, alpha=0.25)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=1))
    ax.tick_params(colors="white", labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor("#3A3A5C")

    ax.set_title(
        f"Rentabilidade Acumulada — {NOME_AWR} vs Peers\n"
        f"{data_ini.strftime('%d/%m/%Y')} → {data_fim.strftime('%d/%m/%Y')}",
        color="white", fontsize=13, pad=14,
    )
    ax.set_xlabel("Data", color="white", fontsize=9)
    ax.set_ylabel("Retorno Acumulado (%)", color="white", fontsize=9)

    handles = [
        Line2D([0], [0], color=COR_AWR,    linewidth=2.8, label=NOME_AWR),
        Line2D([0], [0], color=COR_IBOV,   linewidth=1.8, linestyle="--", label="Ibovespa"),
        Line2D([0], [0], color=COR_OUTROS, linewidth=1.2, alpha=0.6, label="Outros fundos"),
    ]
    ax.legend(handles=handles, facecolor="#2A2A4A", edgecolor="#3A3A5C",
              labelcolor="white", fontsize=9, loc="upper left")

    fig.text(0.99, 0.01, "AWR Capital · Dados: CVM + Yahoo Finance",
             ha="right", va="bottom", color="#666", fontsize=7)

    plt.tight_layout()
    caminho = PASTA_SAIDA / f"grafico_awr_{data_fim.strftime('%Y%m%d')}.png"
    plt.savefig(caminho, dpi=150, bbox_inches="tight", facecolor=COR_AWR_BG)
    plt.close(fig)
    print(f"[AWR] Gráfico salvo: {caminho}")
    return caminho


# ─────────────────────────────────────────────────────────────────────────────
# TABELA HTML
# ─────────────────────────────────────────────────────────────────────────────
def _fmt(v: float, dec: int = 2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    sinal = "+" if v >= 0 else ""
    return f"{sinal}{v*100:.{dec}f}%"

def _cor(v: float) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "#999999"
    return "#2E7D32" if v >= 0 else "#C62828"

def gerar_tabela_html(df_rent: pd.DataFrame, rent_semana: pd.Series,
                      variacao: pd.Series) -> str:
    FONT = "'Montserrat', 'Helvetica Neue', Helvetica, Arial, sans-serif"

    # Ordena por retorno acumulado decrescente; Ibovespa sempre no fim
    ordem = sorted(
        [c for c in rent_semana.index if c != "Ibovespa"],
        key=lambda x: float(df_rent[x].iloc[-1]) if x in df_rent.columns else -999.0,
        reverse=True,
    ) + (["Ibovespa"] if "Ibovespa" in rent_semana.index else [])

    rows_html = ""
    for i, nome in enumerate(ordem):
        if nome not in rent_semana.index:
            continue
        ra = df_rent[nome].iloc[-1] if nome in df_rent.columns else np.nan
        rs = rent_semana.get(nome, np.nan)
        rv = variacao.get(nome, np.nan)
        is_awr = nome == NOME_AWR
        bg = "#FFF8E1" if is_awr else ("#F8F8F8" if i % 2 == 0 else "#FFFFFF")
        peso = "700" if is_awr else "400"
        cor_nome = "#E8B517" if is_awr else "#333333"
        rows_html += f"""
          <tr style="background:{bg};">
            <td style="font-family:{FONT};font-size:12px;font-weight:{peso};
                       color:{cor_nome};padding:8px 10px;border-bottom:1px solid #EEE;">
              {nome}</td>
            <td style="font-family:'Roboto Mono',monospace;font-size:12px;font-weight:{peso};
                       color:{_cor(ra)};padding:8px 10px;text-align:right;
                       border-bottom:1px solid #EEE;">{_fmt(ra)}</td>
            <td style="font-family:'Roboto Mono',monospace;font-size:12px;font-weight:{peso};
                       color:{_cor(rs)};padding:8px 10px;text-align:right;
                       border-bottom:1px solid #EEE;">{_fmt(rs)}</td>
            <td style="font-family:'Roboto Mono',monospace;font-size:12px;font-weight:{peso};
                       color:{_cor(rv)};padding:8px 10px;text-align:right;
                       border-bottom:1px solid #EEE;">{_fmt(rv)}</td>
          </tr>"""

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #E0E0E0;border-radius:4px;overflow:hidden;border-collapse:collapse;">
      <thead><tr style="background:#0E0E0E;">
        <th style="font-family:{FONT};font-size:10px;font-weight:700;color:#E8B517;
            padding:10px;text-align:left;letter-spacing:0.8px;text-transform:uppercase;">Fundo</th>
        <th style="font-family:{FONT};font-size:10px;font-weight:700;color:#E8B517;
            padding:10px;text-align:right;letter-spacing:0.8px;text-transform:uppercase;">Acumulado</th>
        <th style="font-family:{FONT};font-size:10px;font-weight:700;color:#E8B517;
            padding:10px;text-align:right;letter-spacing:0.8px;text-transform:uppercase;">Semana</th>
        <th style="font-family:{FONT};font-size:10px;font-weight:700;color:#E8B517;
            padding:10px;text-align:right;letter-spacing:0.8px;text-transform:uppercase;">Δ vs Ant.</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>"""


# ─────────────────────────────────────────────────────────────────────────────
# FUNÇÃO PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────
def rodar() -> dict:
    hoje = date.today()
    data_busca = date(2024, 1, 1)

    print("\n" + "=" * 60)
    print(f"  AWR Capital — Cálculo semanal · {hoje.strftime('%d/%m/%Y')}")
    print("=" * 60)

    dados = carregar_tudo(data_busca=data_busca, data_fim=hoje)

    df_cotas = dados["df_cotas"]
    ibov     = dados["ibov"]
    data_ini = dados["data_ini"]

    df_cotas = df_cotas.join(ibov, how="outer")

    df_filled = df_cotas.ffill()
    primeira  = df_filled.bfill().iloc[0]
    df_rent   = (df_filled / primeira) - 1

    hoje_ts  = df_rent.index[-1]
    uma_sem  = hoje_ts - pd.Timedelta(days=7)
    duas_sem = hoje_ts - pd.Timedelta(days=14)

    rent_semana  = retorno_entre(df_rent, uma_sem,  hoje_ts)
    rent_sem_ant = retorno_entre(df_rent, duas_sem, uma_sem)
    variacao     = rent_semana - rent_sem_ant

    caminho_png = gerar_grafico(df_rent, data_ini, hoje)
    tabela_html = gerar_tabela_html(df_rent, rent_semana, variacao)

    print("\n── Retorno acumulado (última data) ──")
    print((df_rent.iloc[-1] * 100).round(2).to_string())
    print("\n── Retorno da semana ──")
    print((rent_semana * 100).round(2).to_string())
    print("\n── Variação vs semana anterior ──")
    print((variacao * 100).round(2).to_string())

    return {
        "df_rent":      df_rent,
        "rent_semana":  rent_semana,
        "rent_sem_ant": rent_sem_ant,
        "variacao":     variacao,
        "caminho_png":  caminho_png,
        "tabela_html":  tabela_html,
        "data_ini":     data_ini,
        "data_fim":     hoje,
    }


# ─────────────────────────────────────────────────────────────────────────────
# EXECUÇÃO
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    enviar = "--email" in sys.argv
    resultado = rodar()

    if enviar:
        try:
            from email_sender import send_report
            awr_acum = resultado["df_rent"][NOME_AWR].iloc[-1] \
                       if NOME_AWR in resultado["df_rent"].columns else np.nan
            awr_sem  = resultado["rent_semana"].get(NOME_AWR, np.nan)
            ibov_ac  = resultado["df_rent"]["Ibovespa"].iloc[-1] \
                       if "Ibovespa" in resultado["df_rent"].columns else np.nan
            destaques = {
                "top":      f"{NOME_AWR}: {_fmt(awr_acum)} acumulado · {_fmt(awr_sem)} na semana",
                "bottom":   f"Ibovespa: {_fmt(ibov_ac)} acumulado",
                "universo": f"{len(resultado['rent_semana'])} fundos analisados",
            }
            ok = send_report(
                arquivo         = resultado["caminho_png"],
                tipo            = "fundos",
                dt              = datetime.now(),
                destaques       = destaques,
                link_nuvem      = LINK_DASHBOARD,
                imagens_inline  = [resultado["caminho_png"]],
                titulos_imagens = ["Rentabilidade Acumulada — AWR vs Peers vs Ibovespa"],
                tabela_html     = resultado["tabela_html"],
            )
            print("\n✓ Email enviado." if ok else "\n✗ Falha no email.")
        except ImportError:
            print("\n[!] email_sender.py não encontrado em:", _VD_DIR)
    else:
        print("\n  → Rode com --email para enviar o relatório.")
