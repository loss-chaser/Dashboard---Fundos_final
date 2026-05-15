# app.py — Dashboard AWR Capital (Dash/Plotly)
# Equivalente Python do app Shiny do Emerson, com os fundos do calculos.py
#
# Abas:
#   1. Resumo (cards)
#   2. Risco × Retorno (scatter)
#   3. Evolução (cota base 100)
#   4. Distribuição (histograma)
#   5. Tabela completa (com download Excel)
#
# Rodar:  python app.py
# Acessa: http://127.0.0.1:8050

from __future__ import annotations
import logging, os, sys
from datetime import date, timedelta
from pathlib import Path

# Garante que o working directory é a pasta do script
# (necessário quando roda de fora da pasta, ex: caminho absoluto)
_SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(_SCRIPT_DIR)
sys.path.insert(0, str(_SCRIPT_DIR))

import dash
from dash import dcc, html, Input, Output, State, callback_context, dash_table
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd

from config import (
    CNPJ_AWR, NOME_AWR, CNPJ_PARA_NOME, FUNDOS,
    COR_AWR, COR_AWR_BG, COR_IBOV, COR_CDI, COR_OUTROS,
    COR_POSITIVO, COR_NEGATIVO, DIAS_UTEIS_ANO, CORES_FUNDOS,
)
from data_loader import inicializar_global, filtrar_periodo, get_awr_inicio
from metrics import (
    retornos_diarios, retorno_acumulado, retorno_anualizado,
    vol_anualizada, sharpe, max_drawdown, cota_base_100,
    calcular_metricas_todos, retorno_entre, drawdown_series,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE FORMATAÇÃO
# ─────────────────────────────────────────────────────────────────────────────
def fmt_pct(v, dec=1):
    if v is None or not np.isfinite(v):
        return "—"
    return f"{v*100:,.{dec}f}%".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_num(v, dec=2):
    if v is None or not np.isfinite(v):
        return "—"
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pl(v):
    if v is None or not np.isfinite(v):
        return "—"
    if v >= 1e9:
        return f"R$ {v/1e9:,.1f} bi".replace(",", "X").replace(".", ",").replace("X", ".")
    if v >= 1e6:
        return f"R$ {v/1e6:,.0f} MM".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {v/1e3:,.0f} mil".replace(",", "X").replace(".", ",").replace("X", ".")

def cor_sinal(v):
    if v is None or not np.isfinite(v):
        return "#999"
    return COR_POSITIVO if v >= 0 else COR_NEGATIVO


# ─────────────────────────────────────────────────────────────────────────────
# DASH APP
# ─────────────────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    title="Comparador AWR Capital",
    suppress_callback_exceptions=True,
)

app.index_string = """
<!DOCTYPE html>
<html>
<head>
{%metas%}
<title>{%title%}</title>
{%favicon%}
{%css%}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; }
body {
    font-family: 'Inter', 'Segoe UI', sans-serif !important;
    background: #0A0B0E !important;
    margin: 0;
    -webkit-font-smoothing: antialiased;
}
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0A0B0E; }
::-webkit-scrollbar-thumb { background: #1E2330; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2A3040; }

.card-kpi { transition: transform 0.18s ease, box-shadow 0.18s ease; }
.card-kpi:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.45) !important; }

/* ── Tab buttons ── */
.tab-btn {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: #5E6A7A;
    padding: 10px 22px;
    font-size: 13px;
    font-weight: 500;
    font-family: 'Inter', sans-serif;
    letter-spacing: 0.3px;
    cursor: pointer;
    transition: color 0.15s ease, border-color 0.15s ease;
    outline: none;
    position: relative;
    top: 1px;
}
.tab-btn:hover { color: #C8A96E; }
.tab-btn-active {
    color: #C8A96E !important;
    border-bottom: 2px solid #C8A96E !important;
    font-weight: 700;
}

/* ── Period buttons ── */
.periodo-btn {
    background: transparent;
    border: 1px solid #1E2330;
    color: #9AA5B4;
    padding: 5px 10px;
    font-size: 11px;
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s ease;
    outline: none;
    letter-spacing: 0.4px;
}
.periodo-btn:hover { border-color: #C8A96E; color: #EFF1F5; }
.periodo-btn-active {
    background: rgba(200,169,110,0.12) !important;
    border-color: #C8A96E !important;
    color: #C8A96E !important;
    font-weight: 700;
}

/* ── Metric selector buttons ── */
.metric-btn {
    background: transparent;
    border: 1px solid #1E2330;
    color: #9AA5B4;
    padding: 6px 14px;
    font-size: 12px;
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s ease;
    outline: none;
    white-space: nowrap;
}
.metric-btn:hover { border-color: #C8A96E; color: #EFF1F5; }
.metric-btn-active {
    background: rgba(200,169,110,0.12) !important;
    border-color: #C8A96E !important;
    color: #C8A96E !important;
    font-weight: 700;
}

/* ── Refresh button ── */
.btn-refresh {
    background: transparent;
    border: 1px solid #1E2330;
    color: #5E6A7A;
    width: 30px;
    height: 30px;
    border-radius: 5px;
    cursor: pointer;
    font-size: 15px;
    line-height: 1;
    transition: all 0.15s ease;
    outline: none;
    margin-left: 6px;
    padding: 0;
}
.btn-refresh:hover { border-color: #C8A96E; color: #C8A96E; }

</style>
</head>
<body>
{%app_entry%}
<footer>
{%config%}
{%scripts%}
{%renderer%}
</footer>
</body>
</html>
"""

# ─── Opções de período e abas ────────────────────────────────────────────────
PERIODO_OPCOES = [
    ("1M", "1m"), ("3M", "3m"), ("6M", "6m"),
    ("YTD", "ytd"), ("1A", "1a"), ("2A", "2a"), ("MAX", "max"),
]
TAB_OPCOES = [
    ("Risco × Retorno", "tab-risco-retorno"),
    ("Evolução",        "tab-evolucao"),
    ("Distribuição",    "tab-distribuicao"),
    ("Tabela Completa", "tab-tabela"),
]
METRIC_OPCOES = [
    ("Ret. Acum.",  "Ret_acum"),
    ("Ret. Ann.",   "Ret_ann"),
    ("Volatilidade","Vol_ann"),
    ("Sharpe",      "Sharpe"),
    ("Sortino",     "Sortino"),
    ("Drawdown",    "DD_max"),
    ("% Meses +",   "Pct_meses_pos"),
]
_DEFAULT_PERIODO = "1a"
_DEFAULT_TAB     = "tab-risco-retorno"
_DEFAULT_METRIC  = "Ret_acum"


def _datas_para_periodo(periodo: str) -> tuple[date, date]:
    hoje = date.today()
    if periodo == "1m":   return hoje - timedelta(days=30),   hoje
    if periodo == "3m":   return hoje - timedelta(days=91),   hoje
    if periodo == "6m":   return hoje - timedelta(days=182),  hoje
    if periodo == "ytd":  return date(hoje.year, 1, 1),       hoje
    if periodo == "2a":   return hoje - timedelta(days=730),  hoje
    if periodo == "max":
        awr_inicio = get_awr_inicio()
        return (awr_inicio or date(2020, 1, 1)), hoje
    return hoje - timedelta(days=365), hoje  # 1a (default)




# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
app.layout = html.Div(
    style={
        "fontFamily": "'Inter', 'Segoe UI', sans-serif",
        "backgroundColor": "#0A0B0E",
        "minHeight": "100vh",
        "color": "#EFF1F5",
    },
    children=[
        # ── Header ──
        html.Div(
            style={
                "background": "#0A0B0E",
                "borderTop": f"3px solid {COR_AWR}",
                "borderBottom": "1px solid #1E2330",
                "padding": "14px 36px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
                "position": "sticky",
                "top": "0",
                "zIndex": "100",
                "backdropFilter": "blur(8px)",
            },
            children=[
                # Logo
                html.Div(
                    style={"display": "flex", "alignItems": "baseline", "gap": "10px"},
                    children=[
                        html.Span("AWR", style={
                            "fontSize": "20px", "fontWeight": 700,
                            "color": COR_AWR, "letterSpacing": "3px",
                        }),
                        html.Span("CAPITAL", style={
                            "fontSize": "20px", "fontWeight": 300,
                            "color": "#EFF1F5", "letterSpacing": "3px",
                        }),
                        html.Span("·", style={
                            "color": "#1E2330", "fontSize": "18px", "margin": "0 4px",
                        }),
                        html.Span("Comparador", style={
                            "fontSize": "13px", "color": "#5E6A7A",
                            "fontWeight": 400, "letterSpacing": "0.5px",
                        }),
                    ],
                ),
                # Seletor de período
                html.Div(
                    style={"display": "flex", "alignItems": "center", "gap": "4px"},
                    children=[
                        html.Span("PERÍODO", style={
                            "color": "#5E6A7A", "fontSize": "10px",
                            "letterSpacing": "0.8px", "textTransform": "uppercase",
                            "marginRight": "6px",
                        }),
                        *[
                            html.Button(
                                lbl,
                                id=f"btn-periodo-{key}",
                                n_clicks=0,
                                className="periodo-btn periodo-btn-active" if key == _DEFAULT_PERIODO else "periodo-btn",
                            )
                            for lbl, key in PERIODO_OPCOES
                        ],
                        html.Span(
                            id="periodo-display",
                            style={
                                "color": "#EFF1F5", "fontSize": "11px",
                                "marginLeft": "12px", "marginRight": "4px",
                                "fontFamily": "'JetBrains Mono', monospace",
                                "letterSpacing": "0.3px",
                            },
                        ),
                        html.Button("↻", id="btn-refresh", n_clicks=0, className="btn-refresh", title="Atualizar dados"),
                    ],
                ),
            ],
        ),

        # ── Cards resumo ──
        html.Div(id="cards-resumo", style={"padding": "24px 36px 8px"}),

        # ── Barra de abas customizada ──
        html.Div(
            style={
                "display": "flex",
                "padding": "0 36px",
                "borderBottom": "1px solid #1E2330",
            },
            children=[
                html.Button(
                    lbl,
                    id=f"btn-tab-{key.replace('tab-', '')}",
                    n_clicks=0,
                    className="tab-btn tab-btn-active" if key == _DEFAULT_TAB else "tab-btn",
                )
                for lbl, key in TAB_OPCOES
            ],
        ),

        # ── Conteúdo das abas ──
        dcc.Loading(
            id="loading",
            type="dot",
            color=COR_AWR,
            children=[
                html.Div(id="tab-content", style={"padding": "24px 36px"}),
            ],
        ),

        # ── Stores ──
        dcc.Store(id="store-data"),
        dcc.Store(id="active-tab",          data=_DEFAULT_TAB),
        dcc.Store(id="periodo-selecionado", data=_DEFAULT_PERIODO),
        dcc.Store(id="dist-metric",         data=_DEFAULT_METRIC),

        # ── Footer ──
        html.Div(
            "AWR Capital · Dados: CVM + Yahoo Finance + BCB",
            style={
                "textAlign": "center", "color": "#2A3040",
                "fontSize": "11px", "padding": "20px",
                "borderTop": "1px solid #111318",
                "letterSpacing": "0.5px",
            },
        ),
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: CARREGAR DADOS
# ─────────────────────────────────────────────────────────────────────────────
# Cache global em memória
_CACHE = {}


def _build_cache(sd: date, ed: date) -> str:
    """Carrega dados e monta cache. Retorna cache_key."""
    cache_key = f"{sd}_{ed}"
    if cache_key in _CACHE:
        return cache_key

    print(f"[AWR] Filtrando dados de {sd} a {ed}...")
    dados = filtrar_periodo(data_busca=sd, data_fim=ed)

    df_cotas = dados["df_cotas"]
    ibov = dados["ibov"]
    cdi = dados["cdi"]

    # Junta Ibovespa nas cotas
    df_cotas = df_cotas.join(ibov, how="outer")

    # Retornos diários
    ret_d = retornos_diarios(df_cotas)

    # Retorno acumulado (para gráfico e tabela)
    df_cotas_filled = df_cotas.ffill()
    primeira = df_cotas_filled.bfill().iloc[0]
    df_rent_acum = (df_cotas_filled / primeira) - 1

    # CDI acumulado para gráfico
    if len(cdi) > 0:
        cdi_acum = (1 + cdi).cumprod() - 1
        cdi_acum.name = "CDI"
    else:
        cdi_acum = pd.Series(dtype=float, name="CDI")

    # Ibovespa retornos diários para métricas
    ibov_ret = ret_d["Ibovespa"] if "Ibovespa" in ret_d.columns else None

    # Métricas (exclui Ibovespa da lista de fundos)
    fundos_cols = [c for c in ret_d.columns if c != "Ibovespa"]
    ret_fundos = ret_d[fundos_cols]

    metricas = calcular_metricas_todos(
        ret_diarios=ret_fundos,
        cdi_series=cdi if len(cdi) > 0 else None,
        ibov_ret=ibov_ret,
        pl_series=dados["pl"],
    )

    # Retorno semanal
    hoje_ts = df_rent_acum.index[-1]
    uma_sem = hoje_ts - pd.Timedelta(days=7)
    duas_sem = hoje_ts - pd.Timedelta(days=14)
    rent_semana = retorno_entre(df_rent_acum, uma_sem, hoje_ts)
    rent_sem_ant = retorno_entre(df_rent_acum, duas_sem, uma_sem)
    variacao = rent_semana - rent_sem_ant

    # Cota base 100
    cota100 = cota_base_100(ret_d)

    _CACHE[cache_key] = {
        "metricas": metricas,
        "ret_diarios": ret_d,
        "df_rent_acum": df_rent_acum,
        "cdi_acum": cdi_acum,
        "cota100": cota100,
        "cdi_series": cdi,
        "rent_semana": rent_semana,
        "rent_sem_ant": rent_sem_ant,
        "variacao": variacao,
        "data_ini": dados["data_ini"],
        "data_fim": dados["data_fim"],
        "df_cotas_raw": df_cotas_filled[[c for c in df_cotas_filled.columns if c != "Ibovespa"]],
    }

    print(f"[AWR] Dados prontos! {metricas.shape[0]} fundos com métricas.")
    return cache_key


# Pré-carrega todos os dados ANTES de iniciar o servidor (feito uma única vez)
print("\n" + "=" * 60)
print("  AWR Capital — Carregando parquets pré-processados...")
print("=" * 60 + "\n")
inicializar_global()
# _DEFAULT_KEY calculado dinamicamente no callback — não congela a data no startup


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: SELETOR DE PERÍODO
# ─────────────────────────────────────────────────────────────────────────────
@app.callback(
    Output("periodo-selecionado", "data"),
    Output("periodo-display", "children"),
    *[Output(f"btn-periodo-{key}", "className") for _, key in PERIODO_OPCOES],
    *[Input(f"btn-periodo-{key}", "n_clicks") for _, key in PERIODO_OPCOES],
)
def mudar_periodo(*_):
    triggered = callback_context.triggered
    periodo = _DEFAULT_PERIODO
    if triggered and triggered[0]["prop_id"] != ".":
        tid = triggered[0]["prop_id"].split(".")[0]
        for _, key in PERIODO_OPCOES:
            if tid == f"btn-periodo-{key}":
                periodo = key
                break

    sd, ed = _datas_para_periodo(periodo)
    display = f"{sd.strftime('%d/%m/%Y')} → {ed.strftime('%d/%m/%Y')}"
    classnames = [
        "periodo-btn periodo-btn-active" if key == periodo else "periodo-btn"
        for _, key in PERIODO_OPCOES
    ]
    return periodo, display, *classnames


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: TROCA DE ABA
# ─────────────────────────────────────────────────────────────────────────────
@app.callback(
    Output("active-tab", "data"),
    *[Output(f"btn-tab-{key.replace('tab-','')}", "className") for _, key in TAB_OPCOES],
    *[Input(f"btn-tab-{key.replace('tab-','')}", "n_clicks") for _, key in TAB_OPCOES],
)
def mudar_tab(*_):
    triggered = callback_context.triggered
    tab = _DEFAULT_TAB
    if triggered and triggered[0]["prop_id"] != ".":
        tid = triggered[0]["prop_id"].split(".")[0]
        for _, key in TAB_OPCOES:
            if tid == f"btn-tab-{key.replace('tab-','')}":
                tab = key
                break

    classnames = [
        "tab-btn tab-btn-active" if key == tab else "tab-btn"
        for _, key in TAB_OPCOES
    ]
    return tab, *classnames


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: CARREGAR DADOS
# ─────────────────────────────────────────────────────────────────────────────
@app.callback(
    Output("store-data", "data"),
    Input("btn-refresh", "n_clicks"),
    Input("periodo-selecionado", "data"),
)
def load_data(n_clicks, periodo):
    hoje = date.today()
    sd, ed = _datas_para_periodo(periodo or _DEFAULT_PERIODO)
    cache_key = f"{sd}_{ed}"

    triggered = callback_context.triggered
    is_refresh = any("btn-refresh" in t["prop_id"] for t in triggered)
    if cache_key in _CACHE and not is_refresh:
        return cache_key

    try:
        return _build_cache(sd, ed)
    except Exception as e:
        log.error("Erro ao carregar dados: %s", e)
        import traceback
        traceback.print_exc()
        return _build_cache(hoje - timedelta(days=365), hoje)


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: CARDS RESUMO
# ─────────────────────────────────────────────────────────────────────────────
@app.callback(
    Output("cards-resumo", "children"),
    Input("store-data", "data"),
)
def update_cards(cache_key):
    if not cache_key or cache_key not in _CACHE:
        return html.Div("Carregando dados...", style={"color": "#666"})

    d = _CACHE[cache_key]
    m = d["metricas"]
    if m.empty:
        return html.Div("Sem dados para o período.", style={"color": "#C62828"})

    awr = m[m["Fundo"] == NOME_AWR]
    pares = m[m["Fundo"] != NOME_AWR]

    def _val(df, col):
        if df.empty or col not in df.columns:
            return np.nan
        v = df[col].iloc[0]
        return v if np.isfinite(v) else np.nan

    awr_ret = _val(awr, "Ret_acum")
    awr_sharpe = _val(awr, "Sharpe")
    awr_dd = _val(awr, "DD_max")

    # Ranking
    if not pares.empty and np.isfinite(awr_ret):
        rank_ret = int((pares["Ret_acum"].dropna() > awr_ret).sum()) + 1
        total = len(pares["Ret_acum"].dropna()) + 1
    else:
        rank_ret, total = 0, 0

    # Retorno semanal AWR
    awr_sem = d["rent_semana"].get(NOME_AWR, np.nan)

    def card(titulo, valor, sub, cor_borda):
        return html.Div(
            className="card-kpi",
            style={
                "backgroundColor": "#111318",
                "border": "1px solid #1E2330",
                "borderTop": f"2px solid {cor_borda}",
                "borderRadius": "8px",
                "padding": "18px 22px",
                "flex": "1",
                "marginRight": "12px",
                "boxShadow": "0 2px 12px rgba(0,0,0,0.35)",
            },
            children=[
                html.Div(titulo, style={
                    "fontSize": "10px", "color": "#5E6A7A",
                    "textTransform": "uppercase", "letterSpacing": "1px",
                    "fontWeight": 600,
                }),
                html.Div(valor, style={
                    "fontSize": "26px", "fontWeight": 700, "color": "#EFF1F5",
                    "marginTop": "6px",
                    "fontFamily": "'JetBrains Mono', 'DM Mono', monospace",
                    "letterSpacing": "-0.5px",
                }),
                html.Div(sub, style={
                    "fontSize": "11px", "color": "#5E6A7A", "marginTop": "8px",
                }),
            ],
        )

    med_pares = pares["Ret_acum"].median() if not pares.empty else np.nan
    delta = awr_ret - med_pares if np.isfinite(awr_ret) and np.isfinite(med_pares) else np.nan

    return html.Div(
        style={"display": "flex", "gap": "0"},
        children=[
            card(
                "Retorno AWR no período",
                fmt_pct(awr_ret),
                f"Mediana peers: {fmt_pct(med_pares)}  ·  Δ: {fmt_pct(delta)}",
                COR_AWR,
            ),
            card(
                "Ranking de retorno",
                f"{rank_ret}° / {total}" if total > 0 else "—",
                f"Semana: {fmt_pct(awr_sem)}",
                COR_POSITIVO,
            ),
            card(
                "Sharpe AWR",
                fmt_num(awr_sharpe),
                f"Mediana peers: {fmt_num(pares['Sharpe'].median()) if not pares.empty else '—'}",
                "#3498DB",
            ),
            card(
                "Drawdown máximo",
                fmt_pct(awr_dd),
                f"Mediana peers: {fmt_pct(pares['DD_max'].median()) if not pares.empty else np.nan}",
                COR_NEGATIVO,
            ),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: CONTEÚDO DAS TABS
# ─────────────────────────────────────────────────────────────────────────────
@app.callback(
    Output("tab-content", "children"),
    Input("active-tab", "data"),
    Input("store-data", "data"),
    State("dist-metric", "data"),
)
def update_tab(tab, cache_key, dist_metric):
    if not cache_key or cache_key not in _CACHE:
        return html.Div("Carregando...", style={"color": "#5E6A7A", "padding": "20px"})

    d = _CACHE[cache_key]

    if tab == "tab-risco-retorno":
        return _tab_risco_retorno(d)
    elif tab == "tab-evolucao":
        return _tab_evolucao(d)
    elif tab == "tab-distribuicao":
        return _tab_distribuicao(d, dist_metric or _DEFAULT_METRIC)
    elif tab == "tab-tabela":
        return _tab_tabela(d)
    return html.Div()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: RISCO × RETORNO
# ─────────────────────────────────────────────────────────────────────────────
def _tab_risco_retorno(d):
    try:
        return _tab_risco_retorno_inner(d)
    except Exception as e:
        log.error("Erro em _tab_risco_retorno: %s", e, exc_info=True)
        return html.Div(f"Erro ao renderizar gráfico: {e}",
                        style={"color": COR_NEGATIVO, "padding": "20px"})


def _tab_risco_retorno_inner(d):
    m = d["metricas"]
    if m.empty:
        return html.Div("Sem dados para o período.", style={"color": "#5E6A7A", "padding": "20px"})

    fig = go.Figure()

    # Peers
    pares = m[m["Fundo"] != NOME_AWR].copy()
    if not pares.empty:
        pl_col = pares["PL"].fillna(0) if "PL" in pares.columns else pd.Series(0.0, index=pares.index)
        fig.add_trace(go.Scatter(
            x=pares["Vol_ann"],
            y=pares["Ret_ann"],
            mode="markers",
            marker=dict(
                size=9,
                color=COR_OUTROS,
                opacity=0.55,
            ),
            text=pares["Fundo"],
            customdata=np.stack([
                pares["Sharpe"].fillna(0),
                pares["DD_max"].fillna(0),
                pl_col,
            ], axis=-1),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Ret ann: %{y:.1%}<br>"
                "Vol ann: %{x:.1%}<br>"
                "Sharpe: %{customdata[0]:.2f}<br>"
                "DD máx: %{customdata[1]:.1%}<br>"
                "<extra></extra>"
            ),
            name="Peers",
        ))

    # AWR
    awr = m[m["Fundo"] == NOME_AWR]
    if not awr.empty:
        fig.add_trace(go.Scatter(
            x=awr["Vol_ann"],
            y=awr["Ret_ann"],
            mode="markers+text",
            marker=dict(size=18, color=COR_AWR, line=dict(width=2, color="#FFF")),
            text=["AWR"],
            textposition="top center",
            textfont=dict(color=COR_AWR, size=12, family="DM Sans"),
            hovertemplate=(
                "<b>AWR Capital</b><br>"
                f"Ret ann: {fmt_pct(awr['Ret_ann'].iloc[0])}<br>"
                f"Vol ann: {fmt_pct(awr['Vol_ann'].iloc[0])}<br>"
                f"Sharpe: {fmt_num(awr['Sharpe'].iloc[0])}<br>"
                "<extra></extra>"
            ),
            name="AWR Capital",
        ))

    # Benchmarks (CDI e Ibov) como estrelas
    cdi_s = d.get("cdi_series")
    if cdi_s is not None and len(cdi_s) > 20:
        from metrics import retorno_anualizado as ra_fn, vol_anualizada as va_fn
        cdi_ra = ra_fn(cdi_s)
        cdi_va = va_fn(cdi_s)
        if np.isfinite(cdi_ra) and np.isfinite(cdi_va):
            fig.add_trace(go.Scatter(
                x=[cdi_va], y=[cdi_ra],
                mode="markers+text",
                marker=dict(size=18, symbol="star", color=COR_CDI,
                            line=dict(width=1.5, color="#FFF")),
                text=["CDI"], textposition="top center",
                textfont=dict(color=COR_CDI, size=11),
                name="CDI",
                hovertemplate=f"<b>CDI</b><br>Ret ann: {fmt_pct(cdi_ra)}<br>Vol ann: {fmt_pct(cdi_va)}<extra></extra>",
            ))

    ret_ibov = d["ret_diarios"].get("Ibovespa")
    if ret_ibov is not None and len(ret_ibov.dropna()) > 20:
        from metrics import retorno_anualizado as ra_fn, vol_anualizada as va_fn
        ib_ra = ra_fn(ret_ibov.dropna())
        ib_va = va_fn(ret_ibov.dropna())
        if np.isfinite(ib_ra) and np.isfinite(ib_va):
            fig.add_trace(go.Scatter(
                x=[ib_va], y=[ib_ra],
                mode="markers+text",
                marker=dict(size=18, symbol="star", color=COR_IBOV,
                            line=dict(width=1.5, color="#FFF")),
                text=["IBOV"], textposition="top center",
                textfont=dict(color=COR_IBOV, size=11),
                name="Ibovespa",
                hovertemplate=f"<b>Ibovespa</b><br>Ret ann: {fmt_pct(ib_ra)}<br>Vol ann: {fmt_pct(ib_va)}<extra></extra>",
            ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0A0B0E",
        plot_bgcolor="#111318",
        title=dict(
            text="Risco × Retorno (anualizados)",
            font=dict(size=15, color="#EFF1F5", family="Inter"),
        ),
        xaxis=dict(
            title="Volatilidade anualizada", tickformat=".0%",
            gridcolor="#1A1F2B", ticklen=0, tickfont=dict(color="#5E6A7A"),
        ),
        yaxis=dict(
            title="Retorno anualizado", tickformat=".0%",
            gridcolor="#1A1F2B", ticklen=0, tickfont=dict(color="#5E6A7A"),
            zeroline=True, zerolinecolor="#2A3040",
        ),
        legend=dict(orientation="h", y=-0.15, font=dict(size=11, color="#5E6A7A")),
        margin=dict(l=60, r=30, t=60, b=80),
        hoverlabel=dict(
            bgcolor="#111318", font_size=12,
            font_family="Inter", bordercolor="#1E2330",
        ),
    )

    return dcc.Graph(figure=fig, style={"height": "600px"})


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: EVOLUÇÃO (cota base 100)
# ─────────────────────────────────────────────────────────────────────────────
def _tab_evolucao(d):
    cota = d["cota100"]
    cdi_acum = d.get("cdi_acum")
    df_cotas_raw = d.get("df_cotas_raw")

    if cota.empty:
        return html.Div("Sem dados.", style={"color": "#666"})

    fig = go.Figure()

    # Peers (cinza, finos)
    # Peers — cada um com sua própria cor
    for col in cota.columns:
        if col in (NOME_AWR, "Ibovespa"):
            continue
        cor = CORES_FUNDOS.get(col, COR_OUTROS)
        fig.add_trace(go.Scatter(
            x=cota.index, y=cota[col],
            mode="lines",
            line=dict(color=cor, width=1.5),
            opacity=0.8,
            name=col,
            showlegend=True,
            hoverlabel=dict(bgcolor="#111318", bordercolor=cor, font_color=cor, font_size=12, font_family="Inter"),
            hovertemplate=f"<b>{col}</b><br>%{{x|%d/%m/%Y}}<br>Base 100: %{{y:.2f}}<extra></extra>",
        ))

    # CDI acumulado → cota 100
    if cdi_acum is not None and len(cdi_acum) > 0:
        cdi_100 = (1 + cdi_acum) * 100
        fig.add_trace(go.Scatter(
            x=cdi_100.index, y=cdi_100.values,
            mode="lines",
            line=dict(color=COR_CDI, width=2, dash="dot"),
            name="CDI",
            hoverlabel=dict(bgcolor="#111318", bordercolor=COR_CDI, font_color=COR_CDI, font_size=12, font_family="Inter"),
            hovertemplate="<b>CDI</b><br>%{x|%d/%m/%Y}<br>Base 100: %{y:.2f}<extra></extra>",
        ))

    # Ibovespa
    if "Ibovespa" in cota.columns:
        fig.add_trace(go.Scatter(
            x=cota.index, y=cota["Ibovespa"],
            mode="lines",
            line=dict(color=COR_IBOV, width=2, dash="dash"),
            name="Ibovespa",
            hoverlabel=dict(bgcolor="#111318", bordercolor=COR_IBOV, font_color=COR_IBOV, font_size=12, font_family="Inter"),
            hovertemplate="<b>Ibovespa</b><br>%{x|%d/%m/%Y}<br>Base 100: %{y:.2f}<extra></extra>",
        ))

    # AWR (destaque — mais grosso, por cima)
    if NOME_AWR in cota.columns:
        fig.add_trace(go.Scatter(
            x=cota.index, y=cota[NOME_AWR],
            mode="lines",
            line=dict(color=COR_AWR, width=3.5),
            name=NOME_AWR,
            hoverlabel=dict(bgcolor="#111318", bordercolor=COR_AWR, font_color=COR_AWR, font_size=12, font_family="Inter"),
            hovertemplate=f"<b>{NOME_AWR}</b><br>%{{x|%d/%m/%Y}}<br>Base 100: %{{y:.2f}}<extra></extra>",
        ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0A0B0E",
        plot_bgcolor="#111318",
        title=dict(
            text="Evolução comparada (base 100)",
            font=dict(size=15, color="#EFF1F5", family="Inter"),
        ),
        xaxis=dict(title="", gridcolor="#1A1F2B", ticklen=0, tickfont=dict(color="#5E6A7A")),
        yaxis=dict(
            title="Base 100", gridcolor="#1A1F2B",
            ticklen=0, tickfont=dict(color="#5E6A7A"),
        ),
        legend=dict(
            orientation="h",
            y=-0.30,
            font=dict(size=9, color="#5E6A7A"),
            itemwidth=30,
            tracegroupgap=0,
        ),
        margin=dict(l=60, r=30, t=60, b=160),
        hovermode="closest",
        hoverlabel=dict(
            bgcolor="#111318", font_size=12,
            font_family="Inter", bordercolor="#1E2330",
            namelength=-1,
        ),
    )

    grafico = dcc.Graph(figure=fig, style={"height": "600px"})

    # ── Tabela de cotas usadas no cálculo ──
    if df_cotas_raw is None or df_cotas_raw.empty:
        return grafico

    data_ini_str = df_cotas_raw.index[0].strftime("%d/%m/%Y")
    data_fim_str = df_cotas_raw.index[-1].strftime("%d/%m/%Y")

    rows = []
    for col in df_cotas_raw.columns:
        serie = df_cotas_raw[col].dropna()
        if serie.empty:
            continue
        c_ini = serie.iloc[0]
        c_fim = serie.iloc[-1]
        ret = (c_fim / c_ini - 1) if c_ini != 0 else np.nan
        cor = CORES_FUNDOS.get(col, COR_OUTROS)
        rows.append({
            "●": "●",
            "_cor": cor,
            "Fundo": col,
            f"Cota {data_ini_str}": f"{c_ini:,.6f}".replace(",", "X").replace(".", ",").replace("X", "."),
            f"Cota {data_fim_str}": f"{c_fim:,.6f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "Rentabilidade": fmt_pct(ret, 2),
        })

    col_ids = ["●", "Fundo", f"Cota {data_ini_str}", f"Cota {data_fim_str}", "Rentabilidade"]
    columns = [{"name": c, "id": c} for c in col_ids]
    data_records = [{k: v for k, v in r.items() if k != "_cor"} for r in rows]

    style_data_cond = [
        {
            "if": {"filter_query": f'{{Fundo}} = "{r["Fundo"]}"', "column_id": "●"},
            "color": r["_cor"],
            "fontWeight": 900,
            "fontSize": "16px",
        }
        for r in rows
    ] + [
        {
            "if": {"filter_query": f'{{Fundo}} = "{NOME_AWR}"'},
            "backgroundColor": "rgba(200,169,110,0.06)",
            "fontWeight": 700,
        }
    ]

    tabela = dash_table.DataTable(
        columns=columns,
        data=data_records,
        style_table={"overflowX": "auto", "marginTop": "24px", "borderRadius": "8px", "overflow": "hidden"},
        style_header={
            "backgroundColor": "#0A0B0E",
            "color": COR_AWR,
            "fontWeight": 700,
            "fontSize": "10px",
            "textTransform": "uppercase",
            "letterSpacing": "0.8px",
            "border": "1px solid #1E2330",
        },
        style_cell={
            "backgroundColor": "#111318",
            "color": "#EFF1F5",
            "fontSize": "12px",
            "fontFamily": "'JetBrains Mono', 'DM Mono', monospace",
            "border": "1px solid #1A1F2B",
            "padding": "7px 12px",
            "textAlign": "right",
        },
        style_cell_conditional=[
            {"if": {"column_id": "Fundo"}, "textAlign": "left", "minWidth": "220px",
             "fontFamily": "'Inter', sans-serif"},
            {"if": {"column_id": "●"}, "textAlign": "center", "width": "30px", "padding": "2px"},
        ],
        style_data_conditional=style_data_cond,
        page_size=15,
    )

    titulo_tabela = html.Div(
        f"Cotas usadas no cálculo  ·  {data_ini_str} → {data_fim_str}",
        style={
            "marginTop": "28px", "marginBottom": "8px",
            "color": "#5E6A7A", "fontSize": "11px",
            "textTransform": "uppercase", "letterSpacing": "1px",
        },
    )

    return html.Div([grafico, titulo_tabela, tabela])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: DISTRIBUIÇÃO (histograma)
# ─────────────────────────────────────────────────────────────────────────────
def _tab_distribuicao(d, current_metric=_DEFAULT_METRIC):
    m = d["metricas"]
    if m.empty:
        return html.Div("Sem dados.", style={"color": "#5E6A7A", "padding": "20px"})

    return html.Div([
        html.Div(
            style={"display": "flex", "gap": "6px", "marginBottom": "20px", "flexWrap": "wrap"},
            children=[
                html.Button(
                    lbl,
                    id=f"btn-metric-{key}",
                    n_clicks=0,
                    className="metric-btn metric-btn-active" if key == current_metric else "metric-btn",
                )
                for lbl, key in METRIC_OPCOES
            ],
        ),
        dcc.Graph(id="dist-graph", style={"height": "500px"}),
    ])


@app.callback(
    Output("dist-metric", "data"),
    *[Output(f"btn-metric-{key}", "className") for _, key in METRIC_OPCOES],
    *[Input(f"btn-metric-{key}", "n_clicks") for _, key in METRIC_OPCOES],
    prevent_initial_call=True,
)
def mudar_metrica(*_):
    triggered = callback_context.triggered
    metric = _DEFAULT_METRIC
    if triggered and triggered[0]["prop_id"] != ".":
        tid = triggered[0]["prop_id"].split(".")[0]
        for _, key in METRIC_OPCOES:
            if tid == f"btn-metric-{key}":
                metric = key
                break
    classnames = [
        "metric-btn metric-btn-active" if key == metric else "metric-btn"
        for _, key in METRIC_OPCOES
    ]
    return metric, *classnames


@app.callback(
    Output("dist-graph", "figure"),
    Input("dist-metric", "data"),
    Input("store-data", "data"),
    Input("active-tab", "data"),
)
def update_dist(metric_col, cache_key, active_tab):
    if active_tab != "tab-distribuicao":
        return go.Figure()
    if not cache_key or cache_key not in _CACHE or not metric_col:
        return go.Figure()

    m = _CACHE[cache_key]["metricas"]
    if m.empty:
        return go.Figure()

    pares = m[m["Fundo"] != NOME_AWR]
    awr_val = m.loc[m["Fundo"] == NOME_AWR, metric_col]
    awr_val = awr_val.iloc[0] if len(awr_val) > 0 else np.nan

    is_pct = metric_col in ("Ret_acum", "Ret_ann", "Vol_ann", "DD_max", "Pct_meses_pos")

    fig = go.Figure()

    vals = pares[metric_col].dropna()
    fig.add_trace(go.Histogram(
        x=vals,
        nbinsx=max(8, int(len(vals) ** 0.5 * 2)),
        marker=dict(color="#1E2330", line=dict(color="#2A3040", width=0.5)),
        name="Peers",
        hovertemplate=f"{metric_col}: %{{x:.2{'%' if is_pct else 'f'}}}<br>N: %{{y}}<extra></extra>",
    ))

    if np.isfinite(awr_val):
        fig.add_vline(
            x=awr_val,
            line=dict(color=COR_AWR, width=3),
            annotation_text=f"AWR: {fmt_pct(awr_val) if is_pct else fmt_num(awr_val)}",
            annotation_font=dict(color=COR_AWR, size=12),
        )

    label_map = {
        "Ret_acum": "Retorno acumulado", "Ret_ann": "Retorno anualizado",
        "Vol_ann": "Volatilidade ann.", "Sharpe": "Sharpe", "Sortino": "Sortino",
        "DD_max": "Drawdown máximo", "Pct_meses_pos": "% meses positivos",
    }

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0A0B0E",
        plot_bgcolor="#111318",
        title=dict(
            text=f"Distribuição — {label_map.get(metric_col, metric_col)}",
            font=dict(size=15, color="#EFF1F5", family="Inter"),
        ),
        xaxis=dict(
            title=label_map.get(metric_col, metric_col),
            tickformat=".1%" if is_pct else ".2f",
            gridcolor="#1A1F2B", ticklen=0, tickfont=dict(color="#5E6A7A"),
        ),
        yaxis=dict(
            title="Nº de fundos", gridcolor="#1A1F2B",
            ticklen=0, tickfont=dict(color="#5E6A7A"),
        ),
        bargap=0.06,
        margin=dict(l=60, r=30, t=60, b=60),
        hoverlabel=dict(
            bgcolor="#111318", font_size=12,
            font_family="Inter", bordercolor="#1E2330",
        ),
    )

    return fig


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: TABELA COMPLETA
# ─────────────────────────────────────────────────────────────────────────────
_COL_LABELS = {
    "#": "#", "★": "★", "Fundo": "Fundo", "N_obs": "N obs",
    "Ret_acum": "Ret. Acum.", "Ret_ann": "Ret. Ann.",
    "Vol_ann": "Vol. Ann.", "Sharpe": "Sharpe", "Sortino": "Sortino",
    "DD_max": "DD Máx.", "Pct_meses_pos": "% Meses +",
    "Pct_do_CDI": "% do CDI", "Pct_meses_vs_CDI": "% M > CDI",
    "Pct_meses_vs_Ibov": "% M > Ibov", "TE_Ibov": "TE Ibov",
    "IR_Ibov": "IR Ibov", "PL": "Patrimônio",
}

_FMT_MAP = {
    "Ret_acum": lambda v: fmt_pct(v, 2),
    "Ret_ann": lambda v: fmt_pct(v),
    "Vol_ann": lambda v: fmt_pct(v),
    "Sharpe": lambda v: fmt_num(v),
    "Sortino": lambda v: fmt_num(v),
    "DD_max": lambda v: fmt_pct(v),
    "Pct_meses_pos": lambda v: fmt_pct(v, 0),
    "Pct_do_CDI": lambda v: fmt_pct(v, 0),
    "Pct_meses_vs_CDI": lambda v: fmt_pct(v, 0),
    "Pct_meses_vs_Ibov": lambda v: fmt_pct(v, 0),
    "TE_Ibov": lambda v: fmt_pct(v),
    "IR_Ibov": lambda v: fmt_num(v),
    "PL": lambda v: fmt_pl(v),
}


def _build_tabela_records(m: pd.DataFrame) -> list[dict]:
    """Ordena por retorno, adiciona ranking e formata colunas."""
    display = m.copy()
    if "Ret_acum" in display.columns:
        display = display.sort_values("Ret_acum", ascending=False, na_position="last").reset_index(drop=True)
    display.insert(0, "#", range(1, len(display) + 1))
    display.insert(1, "★", display["Fundo"].apply(lambda x: "★" if x == NOME_AWR else ""))
    for col, fn in _FMT_MAP.items():
        if col in display.columns:
            display[col] = display[col].apply(fn)
    return display.to_dict("records")


def _tabela_columns(m: pd.DataFrame) -> list[dict]:
    display = m.copy()
    display.insert(0, "#", 0)
    display.insert(1, "★", "")
    return [{"name": _COL_LABELS.get(c, c), "id": c} for c in display.columns]


def _tabela_style_data_cond():
    return [
        {
            "if": {"filter_query": '{★} = "★"'},
            "backgroundColor": "rgba(200,169,110,0.06)",
            "fontWeight": 700,
        },
    ]


def _tab_tabela(d):
    m = d["metricas"]
    if m.empty:
        return html.Div("Sem dados.", style={"color": "#666"})

    records = _build_tabela_records(m)
    columns = _tabela_columns(m)

    return html.Div([
        # ── Barra de busca ──
        html.Div(
            style={
                "display": "flex", "alignItems": "center", "gap": "10px",
                "marginBottom": "14px",
            },
            children=[
                html.Span("🔍", style={"color": "#5E6A7A", "fontSize": "13px"}),
                dcc.Input(
                    id="search-tabela",
                    type="text",
                    placeholder="Buscar fundo pelo nome…",
                    debounce=True,
                    style={
                        "backgroundColor": "#111318",
                        "border": "1px solid #1E2330",
                        "borderRadius": "5px",
                        "color": "#EFF1F5",
                        "padding": "7px 14px",
                        "fontSize": "12px",
                        "fontFamily": "'Inter', sans-serif",
                        "width": "300px",
                        "outline": "none",
                        "letterSpacing": "0.2px",
                    },
                ),
                html.Span(
                    "Pressione Enter para filtrar · clique nos cabeçalhos para ordenar",
                    style={
                        "color": "#2A3040", "fontSize": "10px",
                        "letterSpacing": "0.5px",
                    },
                ),
            ],
        ),
        # ── DataTable ──
        dash_table.DataTable(
            id="tabela-fundos",
            columns=columns,
            data=records,
            sort_action="native",
            page_size=20,
            style_table={
                "overflowX": "auto",
                "borderRadius": "8px",
                "overflow": "hidden",
            },
            style_header={
                "backgroundColor": "#0A0B0E",
                "color": COR_AWR,
                "fontWeight": 700,
                "fontSize": "10px",
                "textTransform": "uppercase",
                "letterSpacing": "0.8px",
                "border": "1px solid #1E2330",
            },
            style_cell={
                "backgroundColor": "#111318",
                "color": "#EFF1F5",
                "fontSize": "12px",
                "fontFamily": "'JetBrains Mono', 'DM Mono', monospace",
                "border": "1px solid #1A1F2B",
                "padding": "9px 12px",
                "textAlign": "right",
                "whiteSpace": "normal",
            },
            style_cell_conditional=[
                {"if": {"column_id": "Fundo"}, "textAlign": "left", "minWidth": "200px",
                 "fontFamily": "'Inter', sans-serif"},
                {"if": {"column_id": "★"}, "textAlign": "center", "width": "28px", "padding": "2px 4px"},
                {"if": {"column_id": "#"}, "textAlign": "center", "width": "38px",
                 "color": "#5E6A7A", "fontWeight": 600, "padding": "2px 4px"},
            ],
            style_data_conditional=_tabela_style_data_cond(),
        ),
    ])


@app.callback(
    Output("tabela-fundos", "data"),
    Input("search-tabela", "value"),
    State("store-data", "data"),
    prevent_initial_call=True,
)
def filtrar_tabela(search, cache_key):
    if not cache_key or cache_key not in _CACHE:
        return []
    m = _CACHE[cache_key]["metricas"]
    if search:
        m = m[m["Fundo"].str.contains(search, case=False, na=False)]
    return _build_tabela_records(m)


# ─────────────────────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────────────────────
# Expõe o Flask server para servidores WSGI (gunicorn no Render / HF Spaces).
# O comando do Procfile / Dockerfile usa: gunicorn app:server
# (inicializar_global() já foi chamado mais acima, na linha ~313)
server = app.server

# ── Autenticação por senha (HTTP Basic Auth) ──────────────────────────────────
from auth import proteger_servidor
proteger_servidor(server)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    print(f"\n[AWR] Dashboard rodando em http://0.0.0.0:{port}\n")
    app.run(debug=False, host="0.0.0.0", port=port)
