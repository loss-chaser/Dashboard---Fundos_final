# metrics.py — Métricas financeiras (inspirado no metrics.R do Emerson)
# Sharpe, Sortino, drawdown, information ratio, % meses, etc.

from __future__ import annotations
import numpy as np
import pandas as pd

from config import DIAS_UTEIS_ANO, RF_FALLBACK_AA, MIN_OBS_METRICAS


# ─────────────────────────────────────────────────────────────────────────────
# RETORNOS BÁSICOS
# ─────────────────────────────────────────────────────────────────────────────
def retornos_diarios(df_cotas: pd.DataFrame) -> pd.DataFrame:
    """Retornos diários a partir de cotas (pct_change)."""
    return df_cotas.pct_change().iloc[1:]


def retorno_acumulado(ret: pd.Series) -> float:
    """Retorno acumulado composto."""
    r = ret.dropna()
    if len(r) == 0:
        return np.nan
    return (1 + r).prod() - 1


def retorno_anualizado(ret: pd.Series, dias_uteis: int = DIAS_UTEIS_ANO,
                       min_obs: int = MIN_OBS_METRICAS) -> float:
    r = ret.dropna()
    n = len(r)
    if n < min_obs:
        return np.nan
    acum = (1 + r).prod()
    return acum ** (dias_uteis / n) - 1


def vol_anualizada(ret: pd.Series, dias_uteis: int = DIAS_UTEIS_ANO,
                   min_obs: int = 5) -> float:
    r = ret.dropna()
    if len(r) < min_obs:
        return np.nan
    return r.std() * np.sqrt(dias_uteis)


# ─────────────────────────────────────────────────────────────────────────────
# SHARPE & SORTINO
# ─────────────────────────────────────────────────────────────────────────────
def sharpe(ret: pd.Series, rf_aa: float = RF_FALLBACK_AA,
           dias_uteis: int = DIAS_UTEIS_ANO, min_obs: int = 20) -> float:
    r = ret.dropna()
    if len(r) < min_obs:
        return np.nan
    rf_d = (1 + rf_aa) ** (1 / dias_uteis) - 1
    excesso = r - rf_d
    sd = excesso.std()
    if sd == 0 or not np.isfinite(sd):
        return np.nan
    return (excesso.mean() / sd) * np.sqrt(dias_uteis)


def _downside_dev(ret: pd.Series, mar: float = 0,
                  dias_uteis: int = DIAS_UTEIS_ANO, min_obs: int = 5) -> float:
    r = ret.dropna()
    if len(r) < min_obs:
        return np.nan
    neg = np.minimum(r - mar, 0)
    return np.sqrt(np.mean(neg ** 2)) * np.sqrt(dias_uteis)


def sortino(ret: pd.Series, rf_aa: float = RF_FALLBACK_AA,
            dias_uteis: int = DIAS_UTEIS_ANO, min_obs: int = 20) -> float:
    r = ret.dropna()
    if len(r) < min_obs:
        return np.nan
    rf_d = (1 + rf_aa) ** (1 / dias_uteis) - 1
    excesso = r - rf_d
    dd = _downside_dev(r, mar=rf_d, dias_uteis=dias_uteis, min_obs=min_obs)
    if dd == 0 or not np.isfinite(dd):
        return np.nan
    return (excesso.mean() * dias_uteis) / dd


# ─────────────────────────────────────────────────────────────────────────────
# DRAWDOWN
# ─────────────────────────────────────────────────────────────────────────────
def max_drawdown(ret: pd.Series) -> float:
    r = ret.dropna()
    if len(r) == 0:
        return np.nan
    eq = (1 + r).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1
    return dd.min()


def drawdown_series(ret: pd.Series) -> pd.Series:
    """Série temporal de drawdown (para gráfico)."""
    r = ret.dropna()
    if len(r) == 0:
        return pd.Series(dtype=float)
    eq = (1 + r).cumprod()
    peak = eq.cummax()
    return eq / peak - 1


# ─────────────────────────────────────────────────────────────────────────────
# TRACKING ERROR & INFORMATION RATIO
# ─────────────────────────────────────────────────────────────────────────────
def tracking_error(ret_fundo: pd.Series, ret_bench: pd.Series,
                   dias_uteis: int = DIAS_UTEIS_ANO,
                   min_obs: int = 20) -> float:
    aligned = pd.concat([ret_fundo, ret_bench], axis=1).dropna()
    if len(aligned) < min_obs:
        return np.nan
    diff = aligned.iloc[:, 0] - aligned.iloc[:, 1]
    return diff.std() * np.sqrt(dias_uteis)


def information_ratio(ret_fundo: pd.Series, ret_bench: pd.Series,
                      dias_uteis: int = DIAS_UTEIS_ANO,
                      min_obs: int = 20) -> float:
    aligned = pd.concat([ret_fundo, ret_bench], axis=1).dropna()
    if len(aligned) < min_obs:
        return np.nan
    rf = aligned.iloc[:, 0]
    rb = aligned.iloc[:, 1]
    n = len(rf)
    ret_f = (1 + rf).prod() ** (dias_uteis / n) - 1
    ret_b = (1 + rb).prod() ** (dias_uteis / n) - 1
    te = tracking_error(ret_fundo, ret_bench, dias_uteis, min_obs)
    if te == 0 or not np.isfinite(te):
        return np.nan
    return (ret_f - ret_b) / te


# ─────────────────────────────────────────────────────────────────────────────
# % MESES POSITIVOS / BATENDO BENCHMARK
# ─────────────────────────────────────────────────────────────────────────────
def pct_meses_positivos(ret: pd.Series) -> float:
    r = ret.dropna()
    if len(r) == 0:
        return np.nan
    monthly = (1 + r).resample("ME").prod() - 1
    if len(monthly) == 0:
        return np.nan
    return (monthly > 0).mean()


def pct_meses_batendo_bench(ret_fundo: pd.Series, ret_bench: pd.Series) -> float:
    aligned = pd.concat([ret_fundo, ret_bench], axis=1).dropna()
    if len(aligned) == 0:
        return np.nan
    aligned.columns = ["fundo", "bench"]
    monthly_f = (1 + aligned["fundo"]).resample("ME").prod() - 1
    monthly_b = (1 + aligned["bench"]).resample("ME").prod() - 1
    common = pd.concat([monthly_f, monthly_b], axis=1).dropna()
    if len(common) == 0:
        return np.nan
    return (common.iloc[:, 0] > common.iloc[:, 1]).mean()


# ─────────────────────────────────────────────────────────────────────────────
# COTA BASE 100 (para gráfico de evolução)
# ─────────────────────────────────────────────────────────────────────────────
def cota_base_100(ret: pd.DataFrame) -> pd.DataFrame:
    """A partir de retornos diários, gera cota base 100."""
    return 100 * (1 + ret).cumprod()


# ─────────────────────────────────────────────────────────────────────────────
# TABELA COMPLETA DE MÉTRICAS
# ─────────────────────────────────────────────────────────────────────────────
def calcular_metricas_todos(
    ret_diarios: pd.DataFrame,
    cdi_series: pd.Series | None = None,
    ibov_ret: pd.Series | None = None,
    pl_series: pd.Series | None = None,
    rf_aa: float = RF_FALLBACK_AA,
) -> pd.DataFrame:
    """
    Calcula todas as métricas para cada fundo.
    Retorna DataFrame com uma linha por fundo.
    """
    # RF do CDI efetivo do período
    if cdi_series is not None and len(cdi_series) > 5:
        cdi_acum = retorno_acumulado(cdi_series)
        n_cdi = len(cdi_series)
        if np.isfinite(cdi_acum) and n_cdi > 0:
            rf_aa = (1 + cdi_acum) ** (DIAS_UTEIS_ANO / n_cdi) - 1

    records = []
    for col in ret_diarios.columns:
        r = ret_diarios[col].dropna()
        n = len(r)
        if n < MIN_OBS_METRICAS:
            continue

        rec = {
            "Fundo": col,
            "N_obs": n,
            "Ret_acum": retorno_acumulado(r),
            "Ret_ann": retorno_anualizado(r),
            "Vol_ann": vol_anualizada(r),
            "Sharpe": sharpe(r, rf_aa),
            "Sortino": sortino(r, rf_aa),
            "DD_max": max_drawdown(r),
            "Pct_meses_pos": pct_meses_positivos(r),
        }

        # % do CDI
        if cdi_series is not None and len(cdi_series) > 0:
            cdi_acum_val = retorno_acumulado(cdi_series)
            rec["Pct_do_CDI"] = (
                rec["Ret_acum"] / cdi_acum_val
                if np.isfinite(cdi_acum_val) and cdi_acum_val > 0
                else np.nan
            )
            rec["Pct_meses_vs_CDI"] = pct_meses_batendo_bench(r, cdi_series)
        else:
            rec["Pct_do_CDI"] = np.nan
            rec["Pct_meses_vs_CDI"] = np.nan

        # Info ratio vs Ibovespa
        if ibov_ret is not None and len(ibov_ret) > 0:
            rec["TE_Ibov"] = tracking_error(r, ibov_ret)
            rec["IR_Ibov"] = information_ratio(r, ibov_ret)
            rec["Pct_meses_vs_Ibov"] = pct_meses_batendo_bench(r, ibov_ret)
        else:
            rec["TE_Ibov"] = np.nan
            rec["IR_Ibov"] = np.nan
            rec["Pct_meses_vs_Ibov"] = np.nan

        # PL
        if pl_series is not None and col in pl_series.index:
            rec["PL"] = pl_series[col]
        else:
            rec["PL"] = np.nan

        records.append(rec)

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values("Ret_acum", ascending=False).reset_index(drop=True)
    return df


def retorno_entre(df_ret_acum: pd.DataFrame, d_ini, d_fim) -> pd.Series:
    """Retorno entre duas datas (do seu calculos.py original)."""
    idx = df_ret_acum.index
    i = idx.searchsorted(d_ini)
    f = idx.searchsorted(d_fim, side="right") - 1
    if i >= len(idx) or f < 0 or i > f:
        return pd.Series(dtype=float)
    return ((1 + df_ret_acum.iloc[f]) / (1 + df_ret_acum.iloc[i])) - 1
