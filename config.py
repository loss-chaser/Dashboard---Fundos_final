# config.py — AWR Capital Dashboard
# Configurações centralizadas. Edite aqui para trocar fundos, URLs, etc.

from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# PASTAS
# ─────────────────────────────────────────────────────────────────────────────
PASTA_DADOS = Path("dados_cvm")
PASTA_SAIDA = Path("saida")
PASTA_CACHE = Path("cache")

for p in (PASTA_DADOS, PASTA_SAIDA, PASTA_CACHE):
    p.mkdir(exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# FUNDO AWR (destaque principal)
# ─────────────────────────────────────────────────────────────────────────────
CNPJ_AWR = "60171849000150"
NOME_AWR = "AWR Capital"

# ─────────────────────────────────────────────────────────────────────────────
# PEERS — mesma lista do seu calculos.py
# ─────────────────────────────────────────────────────────────────────────────
FUNDOS: dict[str, str] = {
    "AWR Capital":                                "60171849000150",
    "Constellation F FIF Cotas FIA":              "35744266000123",
    "Opportunity Log FIF Ações RL":               "13277011000165",
    "Real Investor FIC FIF Ações RL":             "10500884000105",
    "Encore Long Bias FIF Cotas FIM":             "37487351000189",
    "SPX Patriot FIF CIC Ações RL":               "15334585000153",
    "Kapitalo Tarkus FIF Cotas FIA":              "28747685000153",
    "Alphakey Ações FIF Cotas FIA":               "34839385000105",
    "Navi Long Biased FIF CIC Inv. Ações RL":     "59965040000110",
    "Oceana Long Biased FIC FIF Ações RL":        "12823624000198",
    "Squadra Long Biased FIF Cotas FIA":          "09285146000103",
    "Itaú Optimus Long Bias Multimercado FIF":    "46479577000129",
    "Dynamo Cougar FIF":                          "73232530000139",
    "Truxt Long Bias Access FIF Cotas FIA":       "38971881000160",
    "Absolute Pace FIC FIF Ações RL":             "46098790000190", 
}

CNPJ_PARA_NOME = {v: k for k, v in FUNDOS.items()}
TODOS_CNPJS = set(FUNDOS.values())

# ─────────────────────────────────────────────────────────────────────────────
# URLs CVM
# ─────────────────────────────────────────────────────────────────────────────
URL_CVM = (
    "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/"
    "inf_diario_fi_{ano}{mes:02d}.zip"
)
URL_CVM_HIST = (
    "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/HIST/"
    "inf_diario_fi_{ano}{mes:02d}.zip"
)

# ─────────────────────────────────────────────────────────────────────────────
# CDI — BCB SGS série 12
# ─────────────────────────────────────────────────────────────────────────────
URL_BCB_CDI = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"
    "?formato=json&dataInicial={di}&dataFinal={df}"
)

# ─────────────────────────────────────────────────────────────────────────────
# PARÂMETROS GERAIS
# ─────────────────────────────────────────────────────────────────────────────
DIAS_UTEIS_ANO = 252
RF_FALLBACK_AA = 0.12          # fallback se CDI não vier
MIN_OBS_METRICAS = 10          # mínimo de dias p/ calcular métricas

# ─────────────────────────────────────────────────────────────────────────────
# CORES (dashboard)
# ─────────────────────────────────────────────────────────────────────────────
COR_AWR      = "#C8A96E"       # dourado AWR
COR_AWR_BG   = "#1A1A2E"       # fundo escuro
COR_IBOV     = "#E74C3C"       # vermelho Ibov
COR_CDI      = "#3498DB"       # azul CDI
COR_OUTROS   = "#7F8C8D"       # cinza peers
COR_POSITIVO = "#2E7D32"
COR_NEGATIVO = "#C62828"
# Cores individuais para cada fundo no gráfico de evolução
CORES_FUNDOS: dict[str, str] = {
    "AWR Capital":                                "#C8A96E",
    "Constellation F FIF Cotas FIA":              "#4FC3F7",
    "Opportunity Log FIF Ações RL":               "#81C784",
    "Real Investor FIC FIF Ações RL":             "#FFB74D",
    "Encore Long Bias FIF Cotas FIM":             "#F48FB1",
    "SPX Patriot FIF CIC Ações RL":               "#CE93D8",
    "Kapitalo Tarkus FIF Cotas FIA":              "#4DD0E1",
    "Alphakey Ações FIF Cotas FIA":               "#FF8A65",
    "Navi Long Biased FIF CIC Inv. Ações RL":     "#A5D6A7",
    "Oceana Long Biased FIC FIF Ações RL":        "#90CAF9",
    "Squadra Long Biased FIF Cotas FIA":          "#FFCC02",
    "Itaú Optimus Long Bias Multimercado FIF":    "#EF9A9A",
    "Dynamo Cougar FIF":                          "#80DEEA",
    "Truxt Long Bias Access FIF Cotas FIA":       "#DCEDC8",
}
# ─────────────────────────────────────────────────────────────────────────────
# EMAIL (mantido do seu código original)
# ─────────────────────────────────────────────────────────────────────────────
ENVIAR_EMAIL = False
LINK_DASHBOARD = "http://127.0.0.1:8050"
