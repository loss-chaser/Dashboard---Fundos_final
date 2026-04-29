---
title: Dashboard Fundos AWR
emoji: 📊
colorFrom: yellow
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# AWR Capital — Dashboard Comparador de Fundos

Dashboard interativo (Dash/Plotly) que compara performance de fundos brasileiros
contra Ibovespa e CDI. Os dados são atualizados automaticamente todo dia útil
às 8h (BRT) via GitHub Actions.

## Arquitetura

```
dashboard-fundos/
├── app.py                          # Dashboard Dash (frontend + callbacks)
├── data_loader.py                  # Lê parquets pré-processados
├── metrics.py                      # Sharpe, Sortino, DD, IR, etc.
├── config.py                       # Lista de fundos, CNPJs, cores
├── build_data.py                   # Script de pré-processamento
├── _cvm_downloader.py              # Download CVM/Ibov/CDI (só usado pelo build)
├── calculos.py                     # Relatório semanal por email (legado)
├── requirements.txt
├── Dockerfile                      # Para deploy no Hugging Face Spaces
├── data/                           # Parquets gerados pelo build_data.py
│   ├── cotas.parquet
│   ├── ibov.parquet
│   ├── cdi.parquet
│   ├── pl.parquet
│   └── metadata.json
└── .github/workflows/
    └── update-data.yml             # Atualização automática diária
```

## Como funciona

1. **GitHub Actions roda `build_data.py` toda manhã** (seg-sex, 11:00 UTC):
   - Baixa ZIPs CVM dos últimos 3 anos
   - Baixa Ibovespa via yfinance
   - Baixa CDI via API do BCB
   - Processa tudo e salva em `data/*.parquet`
   - Commita os parquets atualizados no repo

2. **O Hugging Face Space pega o push e redeploya automaticamente**:
   - Lê os parquets em ~2 segundos
   - Sem download de dados em runtime
   - RAM mínima, boot rápido

## Rodar localmente

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Gerar os parquets (1ª vez ou pra atualizar)
python build_data.py

# 3. Rodar o dashboard
python app.py
# Abre em http://127.0.0.1:8050
```

## Deploy no Hugging Face Spaces

```bash
# 1. Criar Space novo em huggingface.co/new-space
#    SDK: Docker
#    Visibility: Public

# 2. Adicionar o remote
git remote add hf https://huggingface.co/spaces/SEU_USUARIO/dashboard-fundos

# 3. Push
git push hf main
```

O Space vai buildar o Dockerfile e expor o app na URL `https://SEU_USUARIO-dashboard-fundos.hf.space`.

## Métricas calculadas

| Métrica | Descrição |
|---------|-----------|
| Retorno acumulado | prod(1 + r_d) - 1 |
| Retorno anualizado | (1 + acum)^(252/n) - 1 |
| Volatilidade ann. | sd(r_d) × √252 |
| Sharpe | (excesso sobre CDI) / vol |
| Sortino | excesso / downside deviation |
| Drawdown máximo | maior queda vs pico |
| % meses positivos | fração dos meses com retorno > 0 |
| % meses > CDI | fração dos meses batendo CDI |
| % do CDI | retorno acum / CDI acum |
| Tracking error | vol(r_fundo - r_ibov) |
| Information ratio | (ret_ann fundo - ret_ann ibov) / TE |

## Configuração

Edite `config.py` para:
- Trocar/adicionar fundos (dict `FUNDOS`)
- Ajustar cores do dashboard

Após editar, rode `python build_data.py` novamente e commite os parquets.
