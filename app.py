# app.py — Dashboard AWR Capital (Dash + gráficos ECharts via echarts_awr.py)
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

import math

import dash
from dash import dcc, html, Input, Output, State, callback_context, dash_table
import numpy as np
import pandas as pd

import echarts_awr as ea

from config import (
    CNPJ_AWR, NOME_AWR, CNPJ_PARA_NOME, FUNDOS, CNPJ_FMT,
    COR_AWR, COR_AWR_BG, COR_IBOV, COR_CDI, COR_OUTROS,
    COR_POSITIVO, COR_NEGATIVO, DIAS_UTEIS_ANO, CORES_FUNDOS,
)
from data_loader import inicializar_global, filtrar_periodo, get_awr_inicio, get_metadata
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
# GRÁFICOS (ECharts, padrão AWR — módulo echarts_awr.py ao lado deste arquivo)
# ─────────────────────────────────────────────────────────────────────────────
# Tema escuro do módulo com as cores deste app: os gráficos moram num card
# #111318 (mesmo dos cards de KPI) sobre a página #0A0B0E.
COR_CARD_GRAFICO = "#111318"
TEMA_GRAF = ea.tema_com(
    ea.TEMA_ESCURO,
    superficie=COR_CARD_GRAFICO,
    texto1="#EFF1F5", texto2="#C7CDD8", texto3="#9AA5B4",
    tooltip_fundo="#0A0B0E", tooltip_borda="#2A3040",
    tooltip_sombra="0 6px 22px rgba(0,0,0,.6)",
    etiqueta_fundo="#2A3040", etiqueta_texto="#EFF1F5",
    destaque=COR_AWR, destaque_claro="#E3C896", destaque_escuro="#9C8557",
    ponteiro="rgba(227,200,150,0.5)", sombra_barra="rgba(200,169,110,0.10)",
    zoom_selecao="rgba(200,169,110,0.16)",
    positivo=COR_POSITIVO, negativo=COR_NEGATIVO,
    sucesso=COR_POSITIVO, perigo=COR_NEGATIVO,
    outros=COR_OUTROS,
    # correlação: azul (negativa) <-> neutro <-> dourado (positiva)
    div_neg="#3987e5", div_meio="#2A3040", div_pos="#C8A96E",
)

# Cor de cada entidade, montada UMA vez com a lista completa (filtro/período
# nunca repinta ninguém). CORES_FUNDOS manda; fundo novo sem cor fixa pega a
# próxima cor da paleta do tema.
CORES_ENTIDADES = ea.mapa_cores(
    list(FUNDOS) + ["CDI", "Ibovespa"], TEMA_GRAF,
    fixas={**CORES_FUNDOS, "CDI": COR_CDI, "Ibovespa": COR_IBOV},
)

# Estrela (benchmarks no Risco × Retorno)
_SIMBOLO_ESTRELA = ("path://M50,2 L61,36 L97,36 L68,57 L79,92 L50,71 L21,92 L32,57 "
                    "L3,36 L39,36 Z")

_ESTILO_CARD_GRAFICO = {
    "backgroundColor": COR_CARD_GRAFICO,
    "border": "1px solid #1E2330",
    "borderRadius": "8px",
    "padding": "16px 18px 10px",
    "boxShadow": "0 2px 12px rgba(0,0,0,0.35)",
}


def _card_grafico(*children):
    return html.Div(style=_ESTILO_CARD_GRAFICO, children=list(children))


def _titulo_grafico(texto, sub=None):
    """Título (e subtítulo) dentro do gráfico, no topo à esquerda."""
    t = TEMA_GRAF
    tt = {"text": texto, "left": 0, "top": 0, "itemGap": 6,
          "textStyle": {"color": t["texto1"], "fontSize": 15, "fontWeight": 600,
                        "fontFamily": t["fonte"]}}
    if sub:
        tt["subtext"] = sub
        tt["subtextStyle"] = {"color": t["texto3"], "fontSize": 11, "fontFamily": t["fonte"]}
    return tt


def _num_ou_none(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


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

/* ── Seletor de datas personalizado (DatePickerRange) ──
   O componente do Dash vem com tema claro cravado no CSS dele; sem estas
   regras ele aparece como um retangulo branco no meio da barra escura. */
.periodo-custom .DateInput,
.periodo-custom .DateInput_input,
.periodo-custom .DateRangePickerInput {
    background: transparent !important;
    color: #9AA5B4 !important;
    border: none !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 11px !important;
    font-weight: 500 !important;
}
.periodo-custom .DateRangePickerInput {
    border: 1px solid #1E2330 !important;
    border-radius: 4px !important;
}
.periodo-custom .DateRangePickerInput:hover { border-color: #C8A96E !important; }
.periodo-custom .DateInput_input { padding: 4px 6px !important; width: 84px !important; }
.periodo-custom .DateInput_input__focused { border-bottom: 1px solid #C8A96E !important; }
.periodo-custom .DateRangePickerInput_arrow { color: #5E6A7A !important; }
.periodo-custom .DateRangePickerInput_arrow_svg { fill: #5E6A7A !important; }
.periodo-custom .DateRangePicker_picker { background: #0D111A !important; z-index: 1200 !important; }
.periodo-custom .DayPicker, .periodo-custom .CalendarMonth,
.periodo-custom .CalendarMonthGrid, .periodo-custom .DayPicker_weekHeader {
    background: #0D111A !important; color: #EFF1F5 !important;
}
.periodo-custom .CalendarMonth_caption, .periodo-custom .DayPicker_weekHeader { color: #9AA5B4 !important; }
.periodo-custom .CalendarDay__default {
    background: #0D111A !important; border: 1px solid #1E2330 !important; color: #9AA5B4 !important;
}
.periodo-custom .CalendarDay__default:hover { background: #1E2330 !important; color: #EFF1F5 !important; }
.periodo-custom .CalendarDay__selected,
.periodo-custom .CalendarDay__selected:hover {
    background: #C8A96E !important; border-color: #C8A96E !important; color: #0D111A !important;
}
.periodo-custom .CalendarDay__selected_span,
.periodo-custom .CalendarDay__hovered_span {
    background: rgba(200,169,110,0.22) !important; border-color: #1E2330 !important; color: #EFF1F5 !important;
}
.periodo-custom .CalendarDay__blocked_out_of_range {
    background: #0A0E15 !important; color: #3A4250 !important;
}
.periodo-custom .DayPickerNavigation_button__default {
    background: #0D111A !important; border: 1px solid #1E2330 !important;
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

/* ── DataTable polish ── */
.dash-table-container { border-radius: 10px; border: 1px solid #15191F; }
.dash-spreadsheet-inner td.dash-cell, .dash-spreadsheet-inner th.dash-header { outline: none !important; }
.dash-spreadsheet-inner tbody tr { transition: background-color .12s ease; }

/* O dash_table declara as próprias variáveis de tema (claras) no <table>, e o faz
   via CSS injetado em runtime pelo async-table.js — ou seja, DEPOIS deste <style>.
   Sem !important o tema claro ganha: --hover é #fdfdfd (branco) e --accent é
   hotpink, o que deixava a linha sob o mouse branca-no-branco e ilegível. */
.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner table {
    --hover: #1A1F2B !important;
    --accent: #C8A96E !important;
    --border: #1A1F2B !important;
    --text-color: #EFF1F5 !important;
    --selected-background: rgba(200,169,110,0.14) !important;
    --background-color-ellipses: #111318 !important;
    --faded-text: #5E6A7A !important;
    --faded-text-header: #5E6A7A !important;
    --faded-dropdown: #1A1F2B !important;
    --muted: #3A4150 !important;
}
/* Fundo do hover precisa ser OPACO: a regra do dash pinta o <tr>, e um
   rgba() translúcido na célula deixava o branco do <tr> aparecer por baixo. */
.dash-spreadsheet-inner tbody tr:hover td.dash-cell { background-color: #1A1F2B !important; }

/* Tooltip das células (usado p/ mostrar nome completo + CNPJ do fundo) */
.dash-table-tooltip {
    background-color: #0A0B0E !important;
    border: 1px solid #2A3040 !important;
    border-radius: 6px !important;
    color: #EFF1F5 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 11.5px !important;
    line-height: 1.55 !important;
    box-shadow: 0 6px 22px rgba(0,0,0,0.6) !important;
    max-width: 340px !important;
}
.dash-table-tooltip .dash-table-tooltip-inner, .dash-table-tooltip p { margin: 0 !important; }
.dash-table-tooltip strong, .dash-table-tooltip b { color: #C8A96E !important; }

/* ── dcc.Dropdown (tema escuro) ── */
.corr-dd .Select-control,
.corr-dd .Select.is-open > .Select-control,
.corr-dd .Select.is-focused:not(.is-open) > .Select-control {
    background-color: #111318 !important;
    border: 1px solid #1E2330 !important;
    border-radius: 6px !important;
    box-shadow: none !important;
    min-height: 40px;
}
.corr-dd .Select-placeholder { color: #5E6A7A !important; }
.corr-dd .Select-input > input { color: #EFF1F5 !important; }
.corr-dd .Select-menu-outer {
    background-color: #111318 !important;
    border: 1px solid #1E2330 !important;
    border-radius: 6px !important;
    margin-top: 4px;
}
.corr-dd .VirtualizedSelectOption, .corr-dd .Select-option {
    background-color: #111318 !important; color: #C7CDD8 !important;
}
.corr-dd .VirtualizedSelectFocusedOption, .corr-dd .Select-option.is-focused {
    background-color: #1A1F2B !important; color: #EFF1F5 !important;
}
.corr-dd .Select--multi .Select-value {
    background-color: rgba(200,169,110,0.14) !important;
    border: 1px solid rgba(200,169,110,0.45) !important;
    color: #D9BE86 !important;
    border-radius: 5px !important;
    margin: 4px 4px 0 0 !important;
    font-size: 11.5px;
    display: inline-flex; align-items: center;
}
.corr-dd .Select--multi .Select-value-icon {
    border-right: 1px solid rgba(200,169,110,0.3) !important;
    padding: 1px 7px 0 !important;
}
.corr-dd .Select--multi .Select-value-icon:hover {
    background-color: rgba(200,169,110,0.28) !important; color: #fff !important;
}
.corr-dd .Select-arrow { border-color: #5E6A7A transparent transparent !important; }
.corr-dd .Select-clear-zone:hover .Select-clear { color: #E74C3C !important; }
.corr-dd .Select-clear { color: #5E6A7A !important; }

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


# ─── Selo de frescor do dado ────────────────────────────────────────────────
# A Action roda de seg a sex e o Space so recarrega os dados quando e
# reconstruido. Se ela falhar, o dashboard continua abrindo normal, com dado
# velho e sem avisar ninguem. Este selo torna o atraso visivel.
_ATRASO_ALERTA_DU = 2          # dias uteis tolerados antes de ficar vermelho


def _dias_uteis_entre(inicio: date, fim: date) -> int:
    """Dias uteis de (inicio, fim]. Nao considera feriado - a margem de 2 du
    ja absorve isso; o objetivo e detectar Action parada, nao contar pregao."""
    dias, d = 0, inicio
    while d < fim:
        d += timedelta(days=1)
        if d.weekday() < 5:
            dias += 1
    return dias


def selo_frescor():
    """Span com a data da ultima cota; vermelho quando o dado esta atrasado."""
    meta = get_metadata() or {}
    bruto = meta.get("ultima_cota")
    if not bruto:
        return html.Span()
    try:
        ultima = date.fromisoformat(str(bruto)[:10])
    except Exception:
        return html.Span()

    atraso = _dias_uteis_entre(ultima, date.today())
    atrasado = atraso > _ATRASO_ALERTA_DU
    cor, fundo = ("#E5615C", "rgba(229,97,92,0.12)") if atrasado else ("#5E6A7A", "transparent")
    titulo = (f"Ultima cota publicada: {ultima:%d/%m/%Y} ({atraso} dia(s) util(eis) atras). "
              + ("A atualizacao automatica pode ter falhado - confira a GitHub Action."
                 if atrasado else "Dado em dia."))
    return html.Span(
        ("⚠ " if atrasado else "") + f"cota {ultima:%d/%m}",
        title=titulo,
        style={
            "fontSize": "10px", "color": cor, "background": fundo,
            "border": f"1px solid {'#E5615C' if atrasado else '#1E2330'}",
            "borderRadius": "4px", "padding": "2px 7px", "marginLeft": "10px",
            "fontFamily": "'JetBrains Mono', monospace", "letterSpacing": "0.3px",
            "whiteSpace": "nowrap",
        },
    )


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
    ("Correlação",      "tab-correlacao"),
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


def _periodo_custom(periodo) -> tuple[date, date] | None:
    """Decodifica 'custom:AAAA-MM-DD:AAAA-MM-DD'. None se nao for custom."""
    if not isinstance(periodo, str) or not periodo.startswith("custom:"):
        return None
    try:
        _, ini, fim = periodo.split(":", 2)
        sd, ed = date.fromisoformat(ini), date.fromisoformat(fim)
    except Exception:
        return None
    if sd > ed:
        sd, ed = ed, sd
    if sd == ed:                      # janela de 1 dia nao gera serie
        sd = sd - timedelta(days=1)
    return sd, ed


def _datas_para_periodo(periodo: str) -> tuple[date, date]:
    custom = _periodo_custom(periodo)
    if custom:
        return custom
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
                        selo_frescor(),
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
                        dcc.DatePickerRange(
                            id="periodo-custom",
                            className="periodo-custom",
                            display_format="DD/MM/YY",
                            first_day_of_week=1,
                            minimum_nights=1,
                            start_date_placeholder_text="de",
                            end_date_placeholder_text="ate",
                            # min/max sao definidos pelo callback: aqui o layout
                            # ainda roda ANTES do inicializar_global(), e o
                            # get_awr_inicio() devolveria None.
                            style={"marginLeft": "8px"},
                        ),
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


def _ffill_intervalo_vivo(df: pd.DataFrame) -> pd.DataFrame:
    """ffill só ENTRE a primeira e a última cota de cada coluna.

    Buraco no meio da série (dia em que a CVM não publicou a cota do fundo)
    precisa ser preenchido: sem isso o pct_change devolve NaN na virada do
    buraco, o dropna() das métricas joga essa variação fora e o retorno
    composto perde o movimento daqueles dias. Era o que fazia o Kapitalo
    Tarkus aparecer com 50,27% no ranking e 47,52% na tabela de cotas.

    As pontas ficam NaN de propósito: preenchê-las criaria retornos de 0,00%
    em dias que o fundo ainda não reportou (ou antes de ele existir), o que
    infla o nº de observações e amassa a volatilidade.
    """
    out = df.ffill()
    for c in df.columns:
        s = df[c]
        primeiro, ultimo = s.first_valid_index(), s.last_valid_index()
        if primeiro is None:
            out[c] = s
            continue
        out.loc[out.index < primeiro, c] = np.nan
        out.loc[out.index > ultimo, c] = np.nan
    return out


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

    # Retornos diários (com os buracos de publicação tapados — ver docstring)
    ret_d = retornos_diarios(_ffill_intervalo_vivo(df_cotas))

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

    # ── Cotas p/ a tabela da aba Evolução ──
    # Só as datas em que HÁ cota de fundo. O join com o Ibovespa (how="outer")
    # acrescenta os dias em que a bolsa negociou mas a CVM ainda não publicou, e
    # o ffill copiaria a última cota pra esses dias — fazendo a tabela rotular
    # uma cota velha com uma data em que ela não existe.
    cols_fundos = [c for c in df_cotas_filled.columns if c != "Ibovespa"]
    df_cotas_raw = df_cotas_filled.loc[
        df_cotas_filled.index.isin(dados["df_cotas"].index), cols_fundos
    ]
    # Última data com cota de fato publicada, por fundo (p/ sinalizar defasagem)
    ult_cota = {
        c: (dados["df_cotas"][c].dropna().index[-1]
            if dados["df_cotas"][c].notna().any() else None)
        for c in cols_fundos
    }

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
        "df_cotas_raw": df_cotas_raw,
        "ult_cota": ult_cota,
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
    Output("periodo-custom", "start_date"),
    Output("periodo-custom", "end_date"),
    Output("periodo-custom", "min_date_allowed"),
    Output("periodo-custom", "max_date_allowed"),
    *[Output(f"btn-periodo-{key}", "className") for _, key in PERIODO_OPCOES],
    *[Input(f"btn-periodo-{key}", "n_clicks") for _, key in PERIODO_OPCOES],
    Input("periodo-custom", "start_date"),
    Input("periodo-custom", "end_date"),
)
def mudar_periodo(*args):
    """Botao de atalho OU intervalo escolhido no calendario.

    Os dois caminhos convivem: clicar num atalho reescreve as datas do
    calendario (fica coerente e da para ajustar a partir dali); mexer no
    calendario desmarca os atalhos, porque nenhum deles representa o
    intervalo escolhido.
    """
    n_btn = len(PERIODO_OPCOES)
    cs, ce = args[n_btn], args[n_btn + 1]

    triggered = callback_context.triggered
    periodo, veio_do_calendario = _DEFAULT_PERIODO, False
    if triggered and triggered[0]["prop_id"] != ".":
        tid = triggered[0]["prop_id"].split(".")[0]
        if tid == "periodo-custom":
            veio_do_calendario = True
        else:
            for _, key in PERIODO_OPCOES:
                if tid == f"btn-periodo-{key}":
                    periodo = key
                    break

    if veio_do_calendario and cs and ce:
        sd = date.fromisoformat(str(cs)[:10])
        ed = date.fromisoformat(str(ce)[:10])
        if sd > ed:
            sd, ed = ed, sd
        periodo = f"custom:{sd.isoformat()}:{ed.isoformat()}"
        sd, ed = _datas_para_periodo(periodo)
    else:
        sd, ed = _datas_para_periodo(periodo)

    display = f"{sd.strftime('%d/%m/%Y')} → {ed.strftime('%d/%m/%Y')}"
    classnames = [
        "periodo-btn periodo-btn-active" if key == periodo else "periodo-btn"
        for _, key in PERIODO_OPCOES
    ]
    # Limites do calendario: primeiro dia com dado da AWR ate hoje. Definidos
    # aqui (e nao no layout) porque o layout e montado antes do
    # inicializar_global(), quando get_awr_inicio() ainda devolve None.
    limite_min = get_awr_inicio() or date(2020, 1, 1)
    limite_max = date.today()
    return (periodo, display, sd.isoformat(), ed.isoformat(),
            limite_min.isoformat(), limite_max.isoformat(), *classnames)


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
    elif tab == "tab-correlacao":
        return _tab_correlacao(d)
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

    opt = _opcao_risco_retorno(d)
    if opt is None:
        return html.Div("Sem dados para o período.", style={"color": "#5E6A7A", "padding": "20px"})
    return _card_grafico(ea.dash_grafico(opt, _ALTURA_RISCO_RETORNO, TEMA_GRAF, id="graf-risco-retorno"))


_ALTURA_RISCO_RETORNO = 600

# Tooltip do Risco × Retorno: nome, retorno, vol e as linhas extras do ponto
# (CNPJ, Sharpe, DD) — o mesmo que o hover antigo mostrava.
_TIP_RISCO_RETORNO = ea.JS(
    "function(p){var d=p.data||{},v=d.value||[],a=d.awr||{};"
    "var h=AWR.cab(d.name||p.name)"
    "+AWR.linha(p.color,'retorno anualizado',AWR.fmt('pctf')(v[1]))"
    "+AWR.linha('transparent','volatilidade anualizada',AWR.fmt('pctf')(v[0]));"
    "(a.linhas||[]).forEach(function(l){h+=AWR.linha('transparent',l[0],AWR.esc(l[1]));});"
    "return h;}"
)


def _opcao_risco_retorno(d):
    """Dispersão vol × retorno anualizados: peers (cinza), AWR (dourado) e
    CDI/Ibovespa como estrelas. None se não houver ponto nenhum."""
    t = TEMA_GRAF
    m = d["metricas"]
    pontos = []

    def _extras(r):
        return [("CNPJ", CNPJ_FMT.get(r["Fundo"], "—")),
                ("Sharpe", ea.formatar(_num_ou_none(r["Sharpe"]), "num:2")),
                ("DD máx.", ea.formatar(_num_ou_none(r["DD_max"]), "pctf"))]

    # Ordem das séries = ordem de desenho: peers embaixo, AWR por cima de tudo
    for _, r in m[m["Fundo"] != NOME_AWR].iterrows():
        x, y = _num_ou_none(r["Vol_ann"]), _num_ou_none(r["Ret_ann"])
        if x is None or y is None:
            continue
        pontos.append({"nome": r["Fundo"], "x": x, "y": y, "grupo": "Peers", "extras": _extras(r)})

    # Benchmarks (CDI e Ibov) como estrelas
    from metrics import retorno_anualizado as ra_fn, vol_anualizada as va_fn
    cdi_s = d.get("cdi_series")
    if cdi_s is not None and len(cdi_s) > 20:
        cdi_ra, cdi_va = _num_ou_none(ra_fn(cdi_s)), _num_ou_none(va_fn(cdi_s))
        if cdi_ra is not None and cdi_va is not None:
            pontos.append({"nome": "CDI", "x": cdi_va, "y": cdi_ra, "grupo": "CDI"})
    ret_ibov = d["ret_diarios"].get("Ibovespa")
    if ret_ibov is not None and len(ret_ibov.dropna()) > 20:
        ib_ra, ib_va = _num_ou_none(ra_fn(ret_ibov.dropna())), _num_ou_none(va_fn(ret_ibov.dropna()))
        if ib_ra is not None and ib_va is not None:
            pontos.append({"nome": "Ibovespa", "x": ib_va, "y": ib_ra, "grupo": "Ibovespa"})

    for _, r in m[m["Fundo"] == NOME_AWR].iterrows():
        x, y = _num_ou_none(r["Vol_ann"]), _num_ou_none(r["Ret_ann"])
        if x is not None and y is not None:
            pontos.append({"nome": NOME_AWR, "x": x, "y": y, "grupo": NOME_AWR, "extras": _extras(r)})

    if not pontos:
        return None

    ys = [p["y"] for p in pontos]
    refs_y = [{"valor": 0, "rotulo": ""}] if min(ys) < 0 < max(ys) else None
    opt = ea.dispersao(
        pontos, fmt_x="pctf", fmt_y="pctf",
        nome_x="Volatilidade anualizada", nome_y="Retorno anualizado",
        tema=t, refs_y=refs_y,
        title=_titulo_grafico("Risco × Retorno (anualizados)"),
        grid={"top": 76},
        xAxis={"min": 0},                  # volatilidade não é negativa (o CDI fica ~0%)
        tooltip={"formatter": _TIP_RISCO_RETORNO},
    )

    rotulo_forte = {"show": True, "position": "top", "distance": 8, "color": t["texto1"],
                    "fontWeight": 700, "fontSize": 12, "fontFamily": t["fonte"]}
    estilos = {
        "Peers": {"cor": COR_OUTROS, "tam": 11, "simbolo": "circle",
                  "rotulo": {"show": True, "position": "right", "color": t["texto3"], "fontSize": 11,
                             "formatter": ea.JS("function(p){return (p.data&&p.data.curto)||p.name;}")}},
        # CDI fica colado no eixo Y (vol ~0%): rótulo à direita, longe dos ticks
        "CDI": {"cor": CORES_ENTIDADES["CDI"], "tam": 20, "simbolo": _SIMBOLO_ESTRELA,
                "rotulo": dict(rotulo_forte, formatter="CDI", position="right")},
        "Ibovespa": {"cor": CORES_ENTIDADES["Ibovespa"], "tam": 20, "simbolo": _SIMBOLO_ESTRELA,
                     "rotulo": dict(rotulo_forte, formatter="IBOV")},
        NOME_AWR: {"cor": COR_AWR, "tam": 18, "simbolo": "circle",
                   "rotulo": dict(rotulo_forte, formatter="AWR")},
    }
    for s in opt["series"]:
        # rótulo encavalado some (hideOverlap do dispersao); o de ponto maior
        # (AWR, estrelas) tem prioridade
        e = estilos.get(s["name"])
        if not e:
            continue
        s["symbol"] = e["simbolo"]
        s["symbolSize"] = e["tam"]
        s["itemStyle"] = dict(s["itemStyle"], color=e["cor"])
        s["label"] = dict(s["label"], **e["rotulo"])
        if s["name"] == "Peers":
            s["itemStyle"]["opacity"] = 0.9
            for it in s["data"]:
                it["curto"] = _short_nome(it["name"])
        if s["name"] == NOME_AWR:
            s["z"] = 5

    ordem = [NOME_AWR, "Peers", "CDI", "Ibovespa"]
    presentes = {s["name"] for s in opt["series"]}
    opt["legend"] = ea.legenda(t, tipo="barra", top=36, data=[
        {"name": n, "icon": (_SIMBOLO_ESTRELA if n in ("CDI", "Ibovespa") else "circle")}
        for n in ordem if n in presentes
    ], itemWidth=14, itemHeight=14)
    return opt


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: EVOLUÇÃO (cota base 100)
# ─────────────────────────────────────────────────────────────────────────────
_ALTURA_EVOLUCAO = 600
_TRACO_EVOLUCAO = {"CDI": "dotted", "Ibovespa": "dashed"}


def _tip_evolucao(cab):
    """Tooltip da evolução: data por extenso e uma linha por série (ordenada
    pelo valor), com o CNPJ do fundo — o que o hover antigo mostrava."""
    o = {"cab": list(cab), "cnpj": CNPJ_FMT, "traco": _TRACO_EVOLUCAO, "awr": NOME_AWR}
    return ea.JS(
        "(function(o){var T=AWR.T,f=AWR.fmt('num:2');"
        "function lin(p){var v=p.value;if(Array.isArray(v))v=v[v.length-1];"
        "if(v===null||v===undefined||v==='-'||!isFinite(v))return null;"
        "var tr=o.traco[p.seriesName]||'solid',c=o.cnpj[p.seriesName],awr=p.seriesName===o.awr;"
        "return [+v,'<div style=\"display:flex;align-items:center;gap:8px;margin-top:4px\">'"
        "+'<span style=\"display:inline-block;width:12px;height:0;border-top:2px '+tr+' '+p.color+';flex:none\"></span>'"
        "+'<b style=\"font-size:13px;font-weight:700;color:'+T.texto1+';min-width:48px\">'+f(v)+'</b>'"
        "+'<span style=\"color:'+(awr?T.texto1+';font-weight:600':T.texto3)+'\">'+AWR.esc(p.seriesName)+'</span>'"
        "+(c?'<span style=\"color:'+T.texto3+';opacity:.75;font-size:10.5px;margin-left:auto;padding-left:14px\">'+c+'</span>':'')"
        "+'</div>'];}"
        "return function(ps){if(!Array.isArray(ps))ps=[ps];if(!ps.length)return '';"
        "var i=ps[0].dataIndex,h=AWR.cab(o.cab[i]!=null?o.cab[i]:ps[0].axisValueLabel),rows=[];"
        "ps.forEach(function(p){var r=lin(p);if(r)rows.push(r);});"
        "rows.sort(function(a,b){return b[0]-a[0];});"
        "rows.forEach(function(r){h+=r[1];});"
        "return h+AWR.nota('cota base 100');};"
        "})(%s)" % ea.para_json(o)
    )


def _opcao_evolucao(cota, cdi_acum):
    """Linhas base 100: peers na cor de cada fundo (CORES_FUNDOS), CDI
    pontilhado, Ibovespa tracejado e o AWR mais grosso, por cima."""
    t = TEMA_GRAF
    idx = cota.index
    cdi_100 = None
    if cdi_acum is not None and len(cdi_acum) > 0:
        cdi_100 = (1 + cdi_acum) * 100
        idx = idx.union(cdi_100.index)      # o CDI tem as próprias datas
    base = cota.reindex(idx)

    def _dados(s):
        return [round(float(v), 4) if np.isfinite(v) else None for v in s.to_numpy(dtype=float)]

    series = []
    for col in base.columns:
        if col in (NOME_AWR, "Ibovespa"):
            continue
        series.append({"nome": col, "dados": _dados(base[col]),
                       "cor": CORES_ENTIDADES.get(col, COR_OUTROS), "largura": 1.5})
    if cdi_100 is not None:
        # conectar: os buracos do CDI são só do reindex nas datas dos fundos
        series.append({"nome": "CDI", "dados": _dados(cdi_100.reindex(idx)),
                       "cor": CORES_ENTIDADES["CDI"], "largura": 2, "pontilhado": True,
                       "conectar": True})
    if "Ibovespa" in base.columns:
        series.append({"nome": "Ibovespa", "dados": _dados(base["Ibovespa"]),
                       "cor": CORES_ENTIDADES["Ibovespa"], "largura": 2, "tracejado": True})
    if NOME_AWR in base.columns:
        series.append({"nome": NOME_AWR, "dados": _dados(base[NOME_AWR]),
                       "cor": COR_AWR, "largura": 3})

    x = ea.rotulos_data(idx, "dia_ano")
    cab = ea.rotulos_data(idx, "completo")
    curtos = {s["nome"]: (_short_nome(s["nome"]) if s["nome"] in FUNDOS else s["nome"]) for s in series}
    opt = ea.linha(
        x, series, fmt="num:2", fmt_eixo="num", tema=t, escala=True, rotulo_final=False, cab=cab,
        title=_titulo_grafico("Evolução comparada (base 100)"),
        grid={"top": 48, "right": 170},
        tooltip={"formatter": _tip_evolucao(cab)},
    )
    for s in opt["series"]:
        if s["name"] == NOME_AWR:
            s["z"] = 5                      # AWR por cima de todas
    # Legenda na lateral (17 séries não cabem numa linha): nome curto; o
    # tooltip mostra o nome inteiro + CNPJ. Clicar esconde/mostra a série.
    # Ordem fixa na legenda: AWR, benchmarks e os peers na ordem do config.
    presentes = [s["nome"] for s in series]
    ordem = [n for n in [NOME_AWR, "CDI", "Ibovespa"] + list(FUNDOS) if n in presentes]
    ordem += [n for n in presentes if n not in ordem]
    opt["legend"] = ea.legenda(
        t, tipo="linha", orient="vertical", left="auto", right=0, top=48, bottom=40, itemGap=11,
        data=ordem,
        formatter=ea.JS("function(n){var m=%s;return m[n]||n;}" % ea.para_json(curtos)),
        textStyle={"width": 140, "overflow": "truncate"},
    )
    return opt


def _tab_evolucao(d):
    cota = d["cota100"]
    cdi_acum = d.get("cdi_acum")
    df_cotas_raw = d.get("df_cotas_raw")

    if cota.empty:
        return html.Div("Sem dados.", style={"color": "#666"})

    grafico = _card_grafico(ea.dash_grafico(_opcao_evolucao(cota, cdi_acum), _ALTURA_EVOLUCAO,
                                            TEMA_GRAF, id="graf-evolucao"))

    # ── Tabela de cotas usadas no cálculo ──
    if df_cotas_raw is None or df_cotas_raw.empty:
        return grafico

    ult_cota = d.get("ult_cota") or {}
    ts_ini, ts_fim = df_cotas_raw.index[0], df_cotas_raw.index[-1]
    data_ini_str = ts_ini.strftime("%d/%m/%Y")
    data_fim_str = ts_fim.strftime("%d/%m/%Y")

    rows = []
    for col in df_cotas_raw.columns:
        serie = df_cotas_raw[col].dropna()
        if serie.empty:
            continue
        c_ini = serie.iloc[0]
        c_fim = serie.iloc[-1]
        ret = (c_fim / c_ini - 1) if c_ini != 0 else np.nan
        cor = CORES_FUNDOS.get(col, COR_OUTROS)
        # A cota final é a última publicada; se o fundo está defasado em relação
        # ao fim da janela, ela vem repetida (ffill) e isso é sinalizado.
        ts_ult = ult_cota.get(col) or serie.index[-1]
        defasado = ts_ult < ts_fim
        rows.append({
            "●": "●",
            "_cor": cor,
            "_defasado": defasado,
            "_ult": ts_ult.strftime("%d/%m/%Y"),
            "Fundo": col,
            "CNPJ": CNPJ_FMT.get(col, "—"),
            f"Cota {data_ini_str}": f"{c_ini:,.6f}".replace(",", "X").replace(".", ",").replace("X", "."),
            f"Cota {data_fim_str}": f"{c_fim:,.6f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "Rentabilidade": fmt_pct(ret, 2),
        })

    col_ids = ["●", "Fundo", "CNPJ", f"Cota {data_ini_str}", f"Cota {data_fim_str}", "Rentabilidade"]
    columns = [{"name": c, "id": c} for c in col_ids]
    _oculto = ("_cor", "_defasado", "_ult")
    data_records = [{k: v for k, v in r.items() if k not in _oculto} for r in rows]

    # Tooltip: nome completo + CNPJ + data real da última cota do fundo
    tooltip_data = []
    for r in rows:
        nota = (
            f"  \nÚltima cota publicada: **{r['_ult']}**"
            f"{'  (defasada — valor repetido até o fim da janela)' if r['_defasado'] else ''}"
        )
        info = {"value": f"**{r['Fundo']}**  \nCNPJ {r['CNPJ']}{nota}", "type": "markdown"}
        tooltip_data.append({"Fundo": info, "CNPJ": info, "●": info})

    style_data_cond = [
        {
            "if": {"filter_query": f'{{Fundo}} = "{r["Fundo"]}"', "column_id": "●"},
            "color": r["_cor"],
            "fontWeight": 900,
            "fontSize": "16px",
        }
        for r in rows
    ] + [
        # cota final defasada (repetida por ffill) sai em tom de alerta
        {
            "if": {"filter_query": f'{{Fundo}} = "{r["Fundo"]}"',
                   "column_id": f"Cota {data_fim_str}"},
            "color": "#E8927C",
        }
        for r in rows if r["_defasado"]
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
            {"if": {"column_id": "CNPJ"}, "textAlign": "left", "width": "150px",
             "minWidth": "150px", "color": "#9AA5B4", "letterSpacing": "0.2px"},
            {"if": {"column_id": "●"}, "textAlign": "center", "width": "30px", "padding": "2px"},
        ],
        style_data_conditional=style_data_cond,
        tooltip_data=tooltip_data,
        tooltip_delay=250,
        tooltip_duration=None,
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
_ALTURA_DIST = 500
_LABEL_METRICA = {
    "Ret_acum": "Retorno acumulado", "Ret_ann": "Retorno anualizado",
    "Vol_ann": "Volatilidade ann.", "Sharpe": "Sharpe", "Sortino": "Sortino",
    "DD_max": "Drawdown máximo", "Pct_meses_pos": "% meses positivos",
}

_TIP_HISTOGRAMA = ea.JS(
    "function(p){var d=p.data||{},a=d.awr||{},n=(d.value||[])[1]||0;"
    "var h=AWR.cab(a.titulo||'')+AWR.linha(p.color,n===1?'fundo':'fundos',String(n))"
    "+AWR.linha('transparent','dos peers',AWR.esc(a.pct||''));"
    "if(a.fundos&&a.fundos.length){h+='<div style=\"color:'+AWR.T.texto3+';font-size:11px;"
    "margin-top:6px;line-height:1.55\">'+a.fundos.map(AWR.esc).join('<br>')+'</div>';}"
    "return h;}"
)


def _passo_bonito(bruto):
    """Largura 'redonda' de faixa (1; 2; 2,5; 5 x 10^k), >= bruto."""
    if not (bruto > 0):
        return 1.0
    e = 10 ** math.floor(math.log10(bruto))
    for mult in (1, 2, 2.5, 5, 10):
        if bruto <= mult * e * (1 + 1e-9):
            return mult * e
    return 10 * e


def _opcao_histograma(valores, nomes, awr_val, metric_col, is_pct):
    """Histograma dos peers (faixas de largura redonda, eixo X numérico) com o
    AWR marcado na posição exata. None se nenhum peer tiver a métrica."""
    t = TEMA_GRAF
    fmt = "pctf" if is_pct else "num:2"
    rotulo = _LABEL_METRICA.get(metric_col, metric_col)
    pts = [(float(v), n) for v, n in zip(valores, nomes) if _num_ou_none(v) is not None]
    if not pts:
        return None
    awr_ok = _num_ou_none(awr_val)

    # Faixas: mesmo nº-alvo do histograma antigo (nbinsx), cobrindo peers + AWR
    extremos = [v for v, _ in pts] + ([awr_ok] if awr_ok is not None else [])
    lo, hi = min(extremos), max(extremos)
    alvo = max(8, int(len(pts) ** 0.5 * 2))
    passo = _passo_bonito((hi - lo) / alvo) if hi - lo > 1e-12 else _passo_bonito(abs(lo) * 0.2 or 1.0)
    ini = math.floor(lo / passo + 1e-9) * passo
    k = max(1, int(math.floor((hi - ini) / passo + 1e-9)) + 1)
    fmt_faixa = fmt
    if is_pct:
        fmt_faixa = "pctf:0" if abs(passo * 100 - round(passo * 100)) < 1e-9 else "pctf:1"

    grupos = [[] for _ in range(k)]
    for v, n in pts:
        j = min(max(int(math.floor((v - ini) / passo + 1e-9)), 0), k - 1)
        grupos[j].append((v, n))
    tot = len(pts)
    dados = []
    for j in range(k):
        a, b = ini + j * passo, ini + (j + 1) * passo
        dados.append({
            "value": [round(a + passo / 2, 10), len(grupos[j])],
            "awr": {"titulo": f"{ea.formatar(a, fmt_faixa)} a {ea.formatar(b, fmt_faixa)}",
                    "pct": ea.pct(len(grupos[j]) / tot * 100, 0),
                    "fundos": [f"{_short_nome(n)}  ·  {ea.formatar(v, fmt)}"
                               for v, n in sorted(grupos[j], reverse=True)]},
        })

    serie = {"name": "_serie", "type": "bar", "data": dados,
             "barCategoryGap": "6%", "barMaxWidth": 400,
             "itemStyle": {"color": COR_OUTROS, "borderRadius": [3, 3, 0, 0]},
             "emphasis": {"itemStyle": {"color": "#8A94A6"}}}
    if awr_ok is not None:
        ml = ea.referencias([{"valor": awr_ok, "rotulo": f"AWR: {ea.formatar(awr_ok, fmt)}",
                              "cor": COR_AWR}], t, eixo="x", posicao="end")
        ml["lineStyle"] = {"type": "solid", "width": 2.5, "opacity": 1}
        ml["label"].update({"fontWeight": 600, "fontSize": 12})
        for it in ml["data"]:
            it["label"]["color"] = t["texto1"]
        serie["markLine"] = ml

    fim = ini + k * passo
    opt = ea.base(t)
    opt.update({
        "title": _titulo_grafico(f"Distribuição — {rotulo}",
                                 "nº de peers por faixa  ·  a linha dourada marca o AWR"),
        "grid": ea.grade(t, topo=72, direita=24, base_=34, esquerda=40),
        "xAxis": ea.eixo_valor(fmt_faixa, t, nome=rotulo, nameGap=30,
                               min=round(ini, 10), max=round(fim, 10), interval=passo,
                               splitLine={"show": False},
                               axisLine={"show": True, "lineStyle": {"color": t["eixo"]}}),
        "yAxis": ea.eixo_valor("num", t, nome="Nº de fundos", minInterval=1, nameGap=30),
        "tooltip": dict(ea.tooltip_item("num", t), formatter=_TIP_HISTOGRAMA),
        "series": [serie],
    })
    return opt


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
        _card_grafico(ea.dash_iframe_vazio("dist-graph", _ALTURA_DIST)),
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
    Output("dist-graph", "srcDoc"),
    Input("dist-metric", "data"),
    Input("store-data", "data"),
    Input("active-tab", "data"),
)
def update_dist(metric_col, cache_key, active_tab):
    if active_tab != "tab-distribuicao":
        return ""
    if not cache_key or cache_key not in _CACHE or not metric_col:
        return ea.pagina_aviso("Carregando...", _ALTURA_DIST, TEMA_GRAF)

    m = _CACHE[cache_key]["metricas"]
    if m.empty:
        return ea.pagina_aviso("Sem dados para o período.", _ALTURA_DIST, TEMA_GRAF)

    pares = m[m["Fundo"] != NOME_AWR]
    awr_val = m.loc[m["Fundo"] == NOME_AWR, metric_col]
    awr_val = awr_val.iloc[0] if len(awr_val) > 0 else np.nan

    is_pct = metric_col in ("Ret_acum", "Ret_ann", "Vol_ann", "DD_max", "Pct_meses_pos")

    opt = _opcao_histograma(pares[metric_col], pares["Fundo"], awr_val, metric_col, is_pct)
    if opt is None:
        return ea.pagina_aviso("Sem dados desta métrica no período.", _ALTURA_DIST, TEMA_GRAF)
    return ea.pagina_html(opt, _ALTURA_DIST, TEMA_GRAF)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: TABELA COMPLETA
# ─────────────────────────────────────────────────────────────────────────────
_COL_LABELS = {
    "#": "#", "★": "★", "Fundo": "Fundo", "CNPJ": "CNPJ", "N_obs": "N obs",
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


# Colunas que recebem cor por sinal (verde/vermelho) na tabela
_SIGN_COLS = ["Ret_acum", "Ret_ann", "Sharpe", "Sortino", "IR_Ibov", "Pct_do_CDI"]


def _insert_cols_fixas(display: pd.DataFrame) -> pd.DataFrame:
    """Insere as colunas #, ★ e CNPJ.

    Usada tanto pelos records quanto pelo header, pra que a ordem das colunas
    nunca saia de sincronia entre os dois.
    """
    display.insert(0, "#", range(1, len(display) + 1))
    display.insert(1, "★", display["Fundo"].apply(lambda x: "★" if x == NOME_AWR else ""))
    pos = display.columns.get_loc("Fundo") + 1
    display.insert(pos, "CNPJ", display["Fundo"].map(CNPJ_FMT).fillna("—"))
    return display


def _build_tabela_records(m: pd.DataFrame) -> list[dict]:
    """Ordena por retorno, adiciona ranking, helpers numéricos e formata colunas."""
    display = m.copy()
    if "Ret_acum" in display.columns:
        display = display.sort_values("Ret_acum", ascending=False, na_position="last").reset_index(drop=True)
    display = _insert_cols_fixas(display)
    # Helpers numéricos (antes de formatar) p/ colorir células por sinal via filter_query.
    # Não entram em `columns`, então ficam ocultos — só alimentam o style_data_conditional.
    for c in _SIGN_COLS:
        if c in display.columns:
            display[f"_num_{c}"] = pd.to_numeric(display[c], errors="coerce").fillna(0.0)
    for col, fn in _FMT_MAP.items():
        if col in display.columns:
            display[col] = display[col].apply(fn)
    return display.to_dict("records")


def _tabela_columns(m: pd.DataFrame) -> list[dict]:
    display = _insert_cols_fixas(m.copy())
    return [{"name": _COL_LABELS.get(c, c), "id": c} for c in display.columns]


def _tabela_style_data_cond():
    conds = [
        # zebra striping discreto
        {"if": {"row_index": "odd"}, "backgroundColor": "#0F1217"},
    ]
    # verde/vermelho por sinal nos retornos e índices
    for c in ["Ret_acum", "Ret_ann", "Sharpe", "Sortino", "IR_Ibov"]:
        conds += [
            {"if": {"filter_query": f"{{_num_{c}}} > 0", "column_id": c}, "color": COR_POSITIVO},
            {"if": {"filter_query": f"{{_num_{c}}} < 0", "column_id": c}, "color": COR_NEGATIVO},
        ]
    # drawdown sempre em tom de alerta (é sempre negativo)
    conds.append({"if": {"column_id": "DD_max"}, "color": "#E8927C"})
    # % do CDI: verde se bate o CDI (≥100%), cinza caso contrário
    conds += [
        {"if": {"filter_query": "{_num_Pct_do_CDI} >= 1", "column_id": "Pct_do_CDI"}, "color": COR_POSITIVO},
        {"if": {"filter_query": "{_num_Pct_do_CDI} < 1", "column_id": "Pct_do_CDI"}, "color": "#9AA5B4"},
    ]
    # linha do AWR destacada (por último p/ o fundo vencer o zebra)
    conds += [
        {"if": {"filter_query": '{★} = "★"'},
         "backgroundColor": "rgba(200,169,110,0.10)", "fontWeight": 700},
        {"if": {"filter_query": '{★} = "★"', "column_id": "Fundo"}, "color": COR_AWR},
        {"if": {"filter_query": '{★} = "★"', "column_id": "★"}, "color": COR_AWR},
    ]
    return conds


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
            style_as_list_view=True,
            style_table={
                "overflowX": "auto",
                "borderRadius": "10px",
            },
            style_header={
                "backgroundColor": "#0A0B0E",
                "color": "#8A94A6",
                "fontWeight": 700,
                "fontSize": "10px",
                "textTransform": "uppercase",
                "letterSpacing": "0.6px",
                "fontFamily": "'Inter', sans-serif",
                "border": "none",
                "borderBottom": f"2px solid {COR_AWR}",
                "padding": "12px 13px",
            },
            style_cell={
                "backgroundColor": "#0C0E12",
                "color": "#EFF1F5",
                "fontSize": "12.5px",
                "fontFamily": "'JetBrains Mono', 'DM Mono', monospace",
                "border": "none",
                "borderBottom": "1px solid #15191F",
                "padding": "11px 13px",
                "textAlign": "right",
                "whiteSpace": "normal",
                "height": "auto",
            },
            style_cell_conditional=[
                {"if": {"column_id": "Fundo"}, "textAlign": "left", "minWidth": "230px",
                 "fontFamily": "'Inter', sans-serif", "fontSize": "13px"},
                {"if": {"column_id": "CNPJ"}, "textAlign": "left", "width": "155px",
                 "minWidth": "155px", "color": "#9AA5B4", "fontSize": "11.5px",
                 "whiteSpace": "nowrap"},
                {"if": {"column_id": "★"}, "textAlign": "center", "width": "32px", "padding": "2px 4px"},
                {"if": {"column_id": "#"}, "textAlign": "center", "width": "42px",
                 "color": "#5E6A7A", "fontWeight": 600, "padding": "2px 6px"},
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
# TAB 5: CORRELAÇÃO (heatmap dinâmico)
# ─────────────────────────────────────────────────────────────────────────────
# Tokens genéricos de nome de fundo — removidos para gerar rótulos curtos no heatmap.
_STOP_TOKENS = {
    "fif", "fic", "cic", "fia", "fim", "rl", "cotas", "ações", "acoes",
    "inv", "long", "bias", "biased", "multimercado", "access", "de", "da", "f",
}


def _short_nome(nome: str) -> str:
    """Rótulo curto e legível p/ os eixos do heatmap (ex.: 'Kapitalo Tarkus')."""
    toks = [t for t in nome.split() if t.lower().strip(".") not in _STOP_TOKENS and len(t) > 1]
    if not toks:
        return nome.split()[0] if nome.split() else nome
    return " ".join(toks[:2])


_ALTURA_CORR = 660


def _opcao_correlacao(corr, cols):
    """Mapa de calor da correlação (escala fixa −1..+1) com a linha e a coluna
    do AWR contornadas em dourado e o rótulo do AWR destacado nos eixos."""
    t = TEMA_GRAF
    n = len(cols)
    labels, vistos = [], set()
    for c in cols:
        lb = ("★ " + _short_nome(c)) if c == NOME_AWR else _short_nome(c)
        base_lb, k = lb, 2
        while lb in vistos:                  # nome curto repetido colapsaria a categoria
            lb, k = f"{base_lb} ({k})", k + 1
        vistos.add(lb)
        labels.append(lb)

    z = corr.values.astype(float)
    matriz = [[(round(float(v), 4) if np.isfinite(v) else None) for v in lin] for lin in z]
    opt = ea.mapa_calor(labels, labels, matriz, fmt="num:2", minimo=-1, maximo=1, tema=t)

    # (a cor do texto de cada célula — clara ou escura — o mapa_calor já escolhe
    # pelo contraste com a cor real da célula)
    opt["series"][0]["label"]["fontSize"] = 11 if n <= 10 else 10

    # Subtítulo: com quem o AWR está mais / menos correlacionado
    subt = None
    if NOME_AWR in cols:
        s = corr[NOME_AWR].drop(labels=[NOME_AWR], errors="ignore").dropna()
        if not s.empty:
            subt = (f"AWR  ·  + correlacionado: {_short_nome(s.idxmax())} "
                    f"({ea.formatar(s.max(), 'num:2')})   ·   − correlacionado: "
                    f"{_short_nome(s.idxmin())} ({ea.formatar(s.min(), 'num:2')})")
    opt["title"] = _titulo_grafico("Matriz de correlação", subt)
    opt["grid"]["top"] = 66 if subt else 42

    # rótulo do AWR em destaque nos dois eixos
    rich = {"awr": {"color": t["texto1"], "fontWeight": 700, "fontFamily": t["fonte"], "fontSize": 11,
                    "backgroundColor": "rgba(200,169,110,0.16)", "padding": [3, 6], "borderRadius": 3}}
    fmt_rot = ea.JS("function(v){v=String(v);return v.charAt(0)==='★'?'{awr|'+v+'}':v;}")
    for eixo in ("xAxis", "yAxis"):
        opt[eixo]["axisLabel"].update({"formatter": fmt_rot, "rich": rich})

    # Faixa do AWR (linha + coluna) contornada em dourado: série custom que
    # desenha 2 retângulos de borda a borda das células (markArea não serve:
    # no eixo de categoria uma faixa de 1 célula tem altura zero e some).
    if NOME_AWR in cols:
        ia = cols.index(NOME_AWR)
        opt["series"].append({
            "name": "_faixa_awr", "type": "custom", "data": [[0, 0]], "silent": True, "z": 10,
            "tooltip": {"show": False}, "animation": False, "clip": False,
            "renderItem": ea.JS(
                "function(params,api){var n=%d,i=%d,s=api.size([1,1]),"
                "a=api.coord([0,0]),b=api.coord([n-1,n-1]),r=api.coord([i,i]),"
                "x0=Math.min(a[0],b[0])-s[0]/2,y0=Math.min(a[1],b[1])-s[1]/2,"
                "st={fill:'none',stroke:'%s',lineWidth:2.5};"
                "return {type:'group',children:["
                "{type:'rect',shape:{x:x0,y:r[1]-s[1]/2,width:n*s[0],height:s[1]},style:st},"
                "{type:'rect',shape:{x:r[0]-s[0]/2,y:y0,width:s[0],height:n*s[1]},style:st}]};}"
                % (n, ia, COR_AWR)
            ),
        })
        opt["visualMap"]["seriesIndex"] = 0

    nomes = [c for c in cols]
    opt["tooltip"]["formatter"] = ea.JS(
        "(function(N){return function(p){if(p.seriesType!=='heatmap')return '';var v=p.value||[];"
        "var sem=(v[2]==='-'||v[2]==null);"
        "return AWR.cab(N[v[1]])+AWR.cab('× '+N[v[0]])"
        "+AWR.linha(p.color,'correlação',sem?'–':AWR.fmt('num:2')(v[2]))"
        "+(sem?AWR.nota('menos de 20 dias em comum'):'');};})(%s)" % ea.para_json(nomes)
    )
    return opt


def _tab_correlacao(d):
    m = d["metricas"]
    if m.empty:
        return html.Div("Sem dados.", style={"color": "#666"})

    fundos = list(m["Fundo"])
    if NOME_AWR in fundos:                       # AWR sempre em 1º na lista de opções
        fundos = [NOME_AWR] + [f for f in fundos if f != NOME_AWR]
    options = [{"label": f, "value": f} for f in fundos]

    return html.Div([
        # ── Controles: seletor de fundos (add/remove) ──
        html.Div(
            style={"display": "flex", "alignItems": "center", "gap": "14px",
                   "marginBottom": "18px", "flexWrap": "wrap"},
            children=[
                html.Span("FUNDOS NA MATRIZ", style={
                    "color": "#5E6A7A", "fontSize": "10px", "letterSpacing": "0.8px",
                    "textTransform": "uppercase", "fontWeight": 600, "whiteSpace": "nowrap",
                }),
                html.Div(
                    dcc.Dropdown(
                        id="corr-fundos",
                        options=options,
                        value=fundos,            # todos por padrão; remova com o × ou adicione
                        multi=True,
                        placeholder="Adicione ou remova fundos…",
                        className="corr-dd",
                        clearable=True,
                    ),
                    style={"flex": "1", "minWidth": "440px"},
                ),
            ],
        ),
        _card_grafico(ea.dash_iframe_vazio("corr-heatmap", _ALTURA_CORR)),
        html.Div(
            "Correlação dos retornos diários no período selecionado  ·  escala de −1 a +1: "
            "mais dourado = mais correlacionado, azul = correlação negativa  ·  "
            "a faixa do AWR fica contornada em dourado.",
            style={"color": "#5E6A7A", "fontSize": "11px", "marginTop": "10px",
                   "letterSpacing": "0.3px"},
        ),
    ])


@app.callback(
    Output("corr-heatmap", "srcDoc"),
    Input("corr-fundos", "value"),
    Input("store-data", "data"),
    Input("active-tab", "data"),
)
def update_corr(selected, cache_key, active_tab):
    if active_tab != "tab-correlacao":
        return ""
    if not cache_key or cache_key not in _CACHE:
        return ea.pagina_aviso("Carregando...", _ALTURA_CORR, TEMA_GRAF)

    ret = _CACHE[cache_key]["ret_diarios"]
    selected = selected or []
    cols = [c for c in selected if c in ret.columns and c != "Ibovespa"]
    if NOME_AWR in cols:                          # AWR em 1º → faixa no topo/esquerda
        cols = [NOME_AWR] + [c for c in cols if c != NOME_AWR]

    if len(cols) < 2:
        return ea.pagina_aviso("Selecione ao menos 2 fundos para ver a correlação.", _ALTURA_CORR,
                               TEMA_GRAF)

    corr = ret[cols].corr(min_periods=20)
    return ea.pagina_html(_opcao_correlacao(corr, cols), _ALTURA_CORR, TEMA_GRAF)


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
