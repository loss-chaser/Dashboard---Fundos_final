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
from data_loader import inicializar_global, filtrar_periodo
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


def _tab_style():
    return {
        "backgroundColor": "#0D0D1A",
        "color": "#888",
        "border": "1px solid #2A2A4A",
        "padding": "10px 20px",
        "fontSize": "13px",
        "fontWeight": 500,
    }

def _tab_selected():
    return {
        "backgroundColor": "#1A1A2E",
        "color": COR_AWR,
        "borderTop": f"2px solid {COR_AWR}",
        "borderLeft": "1px solid #2A2A4A",
        "borderRight": "1px solid #2A2A4A",
        "borderBottom": "none",
        "padding": "10px 20px",
        "fontSize": "13px",
        "fontWeight": 700,
    }


# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
app.layout = html.Div(
    style={
        "fontFamily": "'DM Sans', 'Segoe UI', sans-serif",
        "backgroundColor": "#0D0D1A",
        "minHeight": "100vh",
        "color": "#E8E8E8",
    },
    children=[
        # ── Header ──
        html.Div(
            style={
                "background": "linear-gradient(135deg, #0D0D1A 0%, #1A1A2E 100%)",
                "borderBottom": "1px solid #2A2A4A",
                "padding": "20px 32px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
            },
            children=[
                html.Div([
                    html.H1(
                        "Comparador AWR",
                        style={
                            "margin": 0, "fontSize": "24px", "fontWeight": 700,
                            "color": COR_AWR, "letterSpacing": "1px",
                        },
                    ),
                    html.Span(
                        "AWR Capital vs Peers vs Benchmarks",
                        style={"color": "#666", "fontSize": "13px", "marginLeft": "12px"},
                    ),
                ]),
                html.Div([
                    html.Label("Período:", style={"color": "#888", "fontSize": "12px", "marginRight": "8px"}),
                    dcc.DatePickerRange(
                        id="date-range",
                        min_date_allowed=date(2020, 1, 1),
                        max_date_allowed=date.today(),
                        start_date=date(2024, 1, 1),
                        end_date=date.today(),
                        display_format="DD/MM/YYYY",
                        style={"fontSize": "12px"},
                    ),
                    html.Button(
                        "Atualizar",
                        id="btn-refresh",
                        n_clicks=0,
                        style={
                            "marginLeft": "12px",
                            "padding": "8px 20px",
                            "backgroundColor": COR_AWR,
                            "color": "#0D0D1A",
                            "border": "none",
                            "borderRadius": "4px",
                            "fontWeight": 700,
                            "cursor": "pointer",
                            "fontSize": "12px",
                            "letterSpacing": "0.5px",
                        },
                    ),
                ], style={"display": "flex", "alignItems": "center"}),
            ],
        ),

        # ── Cards resumo ──
        html.Div(id="cards-resumo", style={"padding": "20px 32px"}),

        # ── Tabs ──
        dcc.Tabs(
            id="tabs",
            value="tab-risco-retorno",
            style={"padding": "0 32px"},
            colors={
                "border": "#2A2A4A",
                "primary": COR_AWR,
                "background": "#0D0D1A",
            },
            children=[
                dcc.Tab(label="Risco × Retorno", value="tab-risco-retorno",
                        style=_tab_style(), selected_style=_tab_selected()),
                dcc.Tab(label="Evolução", value="tab-evolucao",
                        style=_tab_style(), selected_style=_tab_selected()),
                dcc.Tab(label="Distribuição", value="tab-distribuicao",
                        style=_tab_style(), selected_style=_tab_selected()),
                dcc.Tab(label="Tabela Completa", value="tab-tabela",
                        style=_tab_style(), selected_style=_tab_selected()),
            ],
        ),

        # ── Loading (só no conteúdo, não nas abas) ──
        dcc.Loading(
            id="loading",
            type="dot",
            color=COR_AWR,
            children=[
                html.Div(id="tab-content", style={"padding": "20px 32px"}),
            ],
        ),

        # ── Store para dados ──
        dcc.Store(id="store-data"),

        # ── Footer ──
        html.Div(
            "AWR Capital · Dados: CVM + Yahoo Finance + BCB",
            style={
                "textAlign": "center", "color": "#444",
                "fontSize": "11px", "padding": "20px",
                "borderTop": "1px solid #1A1A2E",
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
_DEFAULT_KEY = _build_cache(date.today() - timedelta(days=365), date.today())


@app.callback(
    Output("store-data", "data"),
    Input("btn-refresh", "n_clicks"),
    Input("date-range", "start_date"),
    Input("date-range", "end_date"),
)
def load_data(n_clicks, start_date, end_date):
    if start_date is None or end_date is None:
        return _DEFAULT_KEY

    sd = date.fromisoformat(start_date[:10])
    ed = date.fromisoformat(end_date[:10])
    cache_key = f"{sd}_{ed}"

    # Usa cache se já temos e não foi clique em Atualizar
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
        return _DEFAULT_KEY


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
            style={
                "backgroundColor": "#1A1A2E",
                "borderLeft": f"4px solid {cor_borda}",
                "borderRadius": "6px",
                "padding": "16px 20px",
                "flex": "1",
                "marginRight": "12px",
                "boxShadow": "0 2px 8px rgba(0,0,0,0.3)",
            },
            children=[
                html.Div(titulo, style={
                    "fontSize": "11px", "color": "#888",
                    "textTransform": "uppercase", "letterSpacing": "0.8px",
                }),
                html.Div(valor, style={
                    "fontSize": "28px", "fontWeight": 700, "color": "#E8E8E8",
                    "marginTop": "4px",
                }),
                html.Div(sub, style={
                    "fontSize": "12px", "color": "#666", "marginTop": "6px",
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
    Input("tabs", "value"),
    Input("store-data", "data"),
)
def update_tab(tab, cache_key):
    if not cache_key or cache_key not in _CACHE:
        return html.Div("Selecione período e clique em Atualizar.", style={"color": "#666"})

    d = _CACHE[cache_key]

    if tab == "tab-risco-retorno":
        return _tab_risco_retorno(d)
    elif tab == "tab-evolucao":
        return _tab_evolucao(d)
    elif tab == "tab-distribuicao":
        return _tab_distribuicao(d)
    elif tab == "tab-tabela":
        return _tab_tabela(d)
    return html.Div()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: RISCO × RETORNO
# ─────────────────────────────────────────────────────────────────────────────
def _tab_risco_retorno(d):
    m = d["metricas"]
    if m.empty:
        return html.Div("Sem dados.", style={"color": "#666"})

    fig = go.Figure()

    # Peers
    pares = m[m["Fundo"] != NOME_AWR].copy()
    if not pares.empty:
        fig.add_trace(go.Scatter(
            x=pares["Vol_ann"],
            y=pares["Ret_ann"],
            mode="markers",
            marker=dict(
                size=10,
                color=COR_OUTROS,
                opacity=0.6,
                line=dict(width=0.5, color="#555"),
            ),
            text=pares["Fundo"],
            customdata=np.stack([
                pares["Sharpe"].fillna(0),
                pares["DD_max"].fillna(0),
                pares["PL"].fillna(0),
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
        paper_bgcolor="#0D0D1A",
        plot_bgcolor="#12122A",
        title=dict(text="Risco × Retorno (anualizados)", font=dict(size=16, color="#E8E8E8")),
        xaxis=dict(title="Volatilidade anualizada", tickformat=".0%", gridcolor="#1E1E3A"),
        yaxis=dict(title="Retorno anualizado", tickformat=".0%", gridcolor="#1E1E3A",
                   zeroline=True, zerolinecolor="#333"),
        legend=dict(orientation="h", y=-0.15, font=dict(size=11)),
        margin=dict(l=60, r=30, t=60, b=80),
        hoverlabel=dict(bgcolor="#1A1A2E", font_size=12),
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
            hovertemplate="<b>CDI</b><br>%{x|%d/%m/%Y}<br>Base 100: %{y:.2f}<extra></extra>",
        ))

    # Ibovespa
    if "Ibovespa" in cota.columns:
        fig.add_trace(go.Scatter(
            x=cota.index, y=cota["Ibovespa"],
            mode="lines",
            line=dict(color=COR_IBOV, width=2, dash="dash"),
            name="Ibovespa",
            hovertemplate="<b>Ibovespa</b><br>%{x|%d/%m/%Y}<br>Base 100: %{y:.2f}<extra></extra>",
        ))

    # AWR (destaque — mais grosso, por cima)
    if NOME_AWR in cota.columns:
        fig.add_trace(go.Scatter(
            x=cota.index, y=cota[NOME_AWR],
            mode="lines",
            line=dict(color=COR_AWR, width=3.5),
            name=NOME_AWR,
            hovertemplate=f"<b>{NOME_AWR}</b><br>%{{x|%d/%m/%Y}}<br>Base 100: %{{y:.2f}}<extra></extra>",
        ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0D0D1A",
        plot_bgcolor="#12122A",
        title=dict(text="Evolução comparada (base 100)", font=dict(size=16, color="#E8E8E8")),
        xaxis=dict(title="", gridcolor="#1E1E3A"),
        yaxis=dict(title="Base 100", gridcolor="#1E1E3A"),
        legend=dict(
            orientation="h",
            y=-0.30,
            font=dict(size=9),
            itemwidth=30,
            tracegroupgap=0,
        ),
        margin=dict(l=60, r=30, t=60, b=160),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#1A1A2E", font_size=11),
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
            "backgroundColor": "#1E1A10",
            "fontWeight": 700,
        }
    ]

    tabela = dash_table.DataTable(
        columns=columns,
        data=data_records,
        style_table={"overflowX": "auto", "marginTop": "24px"},
        style_header={
            "backgroundColor": "#0E0E0E",
            "color": COR_AWR,
            "fontWeight": 700,
            "fontSize": "11px",
            "textTransform": "uppercase",
            "border": "1px solid #2A2A4A",
        },
        style_cell={
            "backgroundColor": "#12122A",
            "color": "#D0D0D0",
            "fontSize": "12px",
            "fontFamily": "'DM Mono', 'Roboto Mono', monospace",
            "border": "1px solid #1E1E3A",
            "padding": "6px 10px",
            "textAlign": "right",
        },
        style_cell_conditional=[
            {"if": {"column_id": "Fundo"}, "textAlign": "left", "minWidth": "220px"},
            {"if": {"column_id": "●"}, "textAlign": "center", "width": "30px", "padding": "2px"},
        ],
        style_data_conditional=style_data_cond,
        page_size=15,
    )

    titulo_tabela = html.Div(
        f"Cotas usadas no cálculo  ·  {data_ini_str} → {data_fim_str}",
        style={
            "marginTop": "28px", "marginBottom": "6px",
            "color": "#888", "fontSize": "12px",
            "textTransform": "uppercase", "letterSpacing": "0.8px",
        },
    )

    return html.Div([grafico, titulo_tabela, tabela])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: DISTRIBUIÇÃO (histograma)
# ─────────────────────────────────────────────────────────────────────────────
def _tab_distribuicao(d):
    m = d["metricas"]
    if m.empty:
        return html.Div("Sem dados.", style={"color": "#666"})

    metric_options = [
        {"label": "Retorno acumulado", "value": "Ret_acum"},
        {"label": "Retorno anualizado", "value": "Ret_ann"},
        {"label": "Volatilidade ann.", "value": "Vol_ann"},
        {"label": "Sharpe", "value": "Sharpe"},
        {"label": "Sortino", "value": "Sortino"},
        {"label": "Drawdown máximo", "value": "DD_max"},
        {"label": "% meses positivos", "value": "Pct_meses_pos"},
    ]

    return html.Div([
        dcc.Dropdown(
            id="dist-metric",
            options=metric_options,
            value="Ret_acum",
            style={
                "width": "300px", "marginBottom": "16px",
                "backgroundColor": "#1A1A2E", "color": "#333",
            },
        ),
        dcc.Graph(id="dist-graph", style={"height": "500px"}),
    ])


@app.callback(
    Output("dist-graph", "figure"),
    Input("dist-metric", "value"),
    Input("store-data", "data"),
)
def update_dist(metric_col, cache_key):
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
        marker=dict(color="#555", line=dict(color="#777", width=0.5)),
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
        paper_bgcolor="#0D0D1A",
        plot_bgcolor="#12122A",
        title=dict(text=f"Distribuição — {label_map.get(metric_col, metric_col)}",
                   font=dict(size=16, color="#E8E8E8")),
        xaxis=dict(
            title=label_map.get(metric_col, metric_col),
            tickformat=".1%" if is_pct else ".2f",
            gridcolor="#1E1E3A",
        ),
        yaxis=dict(title="Nº de fundos", gridcolor="#1E1E3A"),
        bargap=0.05,
        margin=dict(l=60, r=30, t=60, b=60),
    )

    return fig


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: TABELA COMPLETA
# ─────────────────────────────────────────────────────────────────────────────
def _tab_tabela(d):
    m = d["metricas"]
    if m.empty:
        return html.Div("Sem dados.", style={"color": "#666"})

    # Formata para exibição
    display = m.copy()
    display.insert(0, "★", display["Fundo"].apply(lambda x: "★" if x == NOME_AWR else ""))

    # Formata colunas
    fmt_map = {
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

    for col, fn in fmt_map.items():
        if col in display.columns:
            display[col] = display[col].apply(fn)

    col_labels = {
        "★": "★", "Fundo": "Fundo", "N_obs": "N obs",
        "Ret_acum": "Ret. Acum.", "Ret_ann": "Ret. Ann.",
        "Vol_ann": "Vol. Ann.", "Sharpe": "Sharpe", "Sortino": "Sortino",
        "DD_max": "DD Máx.", "Pct_meses_pos": "% Meses +",
        "Pct_do_CDI": "% do CDI", "Pct_meses_vs_CDI": "% M > CDI",
        "Pct_meses_vs_Ibov": "% M > Ibov", "TE_Ibov": "TE Ibov",
        "IR_Ibov": "IR Ibov", "PL": "Patrimônio",
    }

    columns = [
        {"name": col_labels.get(c, c), "id": c}
        for c in display.columns
    ]

    return html.Div([
        dash_table.DataTable(
            id="tabela-fundos",
            columns=columns,
            data=display.to_dict("records"),
            sort_action="native",
            filter_action="native",
            page_size=20,
            style_table={"overflowX": "auto"},
            style_header={
                "backgroundColor": "#0E0E0E",
                "color": COR_AWR,
                "fontWeight": 700,
                "fontSize": "11px",
                "textTransform": "uppercase",
                "letterSpacing": "0.5px",
                "border": "1px solid #2A2A4A",
            },
            style_cell={
                "backgroundColor": "#12122A",
                "color": "#D0D0D0",
                "fontSize": "12px",
                "fontFamily": "'DM Mono', 'Roboto Mono', monospace",
                "border": "1px solid #1E1E3A",
                "padding": "8px 10px",
                "textAlign": "right",
            },
            style_cell_conditional=[
                {"if": {"column_id": "Fundo"}, "textAlign": "left", "minWidth": "200px"},
                {"if": {"column_id": "★"}, "textAlign": "center", "width": "30px"},
            ],
            style_data_conditional=[
                {
                    "if": {"filter_query": '{★} = "★"'},
                    "backgroundColor": "#1E1A10",
                    "fontWeight": 700,
                },
            ],
        ),
        html.Div(
            style={"marginTop": "12px", "fontSize": "11px", "color": "#666"},
            children="Clique nos cabeçalhos para ordenar. Use os filtros para buscar.",
        ),
    ])


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