# -*- coding: utf-8 -*-
"""
echarts_awr - graficos ECharts no padrao AWR (aprovado em 30/09/2026).

Todo grafico dos dashboards/sites/programas da AWR sai por aqui. O grafico e um
dict `option` do ECharts montado em Python; este modulo entrega:

  * temas ........ TEMA_ESCURO (navy + dourado, o do FIDC) e TEMA_CLARO;
                   tema_com(TEMA_ESCURO, destaque=..., fundo=...) deriva o do app.
  * construtores . linha, barras, paineis_ligados, rosca, dispersao, mapa_calor,
                   cascata, histograma - ja com tooltip, zoom, foco no hover etc.
  * pecas ........ base, grade, eixo_categoria, eixo_valor, tooltip_eixo,
                   tooltip_item, legenda, zoom, referencias, faixa - para montar
                   um option na mao quando nenhum construtor serve.
  * render ....... st_grafico (Streamlit), dash_grafico / pagina_html (Dash:
                   html.Iframe(srcDoc=...)), trecho_html + cabecalho_html (pagina
                   HTML/Jinja que ja tem <head>), salvar_html (arquivo).
  * tabelas ...... coluna, tabela -> st_tabela (Streamlit), dash_tabela / pagina_tabela
                   (Dash) - Tabulator com busca, ordenacao numerica, total, selos.
  * matplotlib ... mpl_estilo, mpl_cor, mpl_eixo_fmt, mpl_rotulo_final,
                   mpl_rotular_barras, mpl_legenda - o mesmo visual em PDF/PNG/e-mail.

Regras do padrao (nao quebrar): nunca eixo duplo (duas escalas = paineis_ligados);
cores categoricas em ordem fixa, nunca recicladas (9a serie em diante = cinza
"outros"); cor segue a entidade, nao o ranking; status (perigo/alerta/sucesso)
so quando a cor significa estado, e sempre com texto junto; texto nunca na cor da
serie; grade em hairline; valor em negrito primeiro no tooltip.

Formatos (fmt) - iguais no Python (formatar) e no JS (AWR.fmt):
  'brl'  R$ 1.234.567   'brl:2' com centavos   'brlc' R$ 1,2 mi
  'pct'  12,3% (valor ja em %)   'pctf' 12,3% (valor em fracao 0,123)
  'varpct' +1,2%   'pp' +0,5 p.p.   'num' 1.234   'num:2' 1.234,56
  'numc' 1,2 mi    'mult' 1,25x     'txt' texto cru
Nos eixos o numero sai compacto sozinho (R$ 300 mil, 15%, 1,2 mi).

Funcoes JS dentro do option: JS("AWR.eixo('brl')"). O runtime AWR (fmt, eixo,
rotulo, tipEixo, tipItem, esc...) ja vem em toda pagina gerada aqui.

Dados extras no tooltip: cada ponto pode levar {"awr": {"linhas": [[rotulo,
valor_formatado], ...], "nota": "texto", "nota_cor": "#hex", "titulo": "..."}}
- os construtores aceitam `extras=` e `notas=` por ponto e montam isso.

CANONICO: VD_codigos/echarts_awr/echarts_awr.py. Os apps tem copias identicas:
edite SO aqui e rode `python sincronizar_copias.py` na mesma pasta.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
from copy import deepcopy

__version__ = "1.5.1"
# 1.5.1: cabecalho da tabela nao fica branco no hover (o CSS do Tabulator tinha
#        regra mais especifica, #cdcdcd)
# 1.5: tabelas: altura real quando cabe (sem faixa vazia acima do total), largura
#      minima pelo conteudo, media sem arredondar, total alinhado na barra,
#      sinal='inverso', fmt_campo (formato por linha), 'datahora', chave= (lembra
#      ordenacao e busca entre redesenhos)
# 1.4: tabelas (Tabulator): coluna(), tabela(), st_tabela, dash_tabela, pagina_tabela
# 1.3: linha com muitas series -> tooltip so da linha mais perto do mouse
#      (AWR.proximo / AWR.tipProximo; tooltip_proximo=, extras_series=)
# 1.1: estilo matplotlib (mpl_*) para PDF/PNG/e-mail
# 1.2: cascata cruza o zero e aceita subtotal (None); refs esticam o eixo;
#      barras: rotulo_fmt, textos, margem_direita, vao; linha: conectar_nulos,
#      pontilhado, rotulo_nome; paineis_ligados linha-sobre-linha; texto do
#      mapa_calor pelo contraste real; dispersao sem o bug do labelLayout;
#      aviso()/pagina_aviso() para estado vazio; fonte_css no tema

ECHARTS_CDN = "https://cdnjs.cloudflare.com/ajax/libs/echarts/5.5.0/echarts.min.js"
FONTE_CSS = "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap"

# =============================================================================
# TEMAS
# Paletas categoricas validadas (daltonismo protan/deutan, visao normal e
# contraste) com o validate_palette.js da skill de dataviz em 30/09/2026:
#   escuro sobre #0E1524: CVD adjacente 8,6 / normal 22,5 / 3 primeiras ok em
#                         todos os pares / contraste >= 3:1 nas 8
#   claro sobre #FFFFFF : CVD adjacente 9,2 / normal 15,6 / 3 primeiras ok em
#                         todos os pares / #e87ba4 e #1baf7a < 3:1 -> manter
#                         legenda + rotulo direto quando aparecerem
# A ordem E o mecanismo de seguranca: nao reordenar sem revalidar.
# =============================================================================
TEMA_ESCURO = {
    "nome": "escuro",
    "fonte": "Manrope, sans-serif",
    "fonte_carregar": "Manrope",
    "fundo": "transparent",          # atras do grafico (iframe); cor solida se o app pedir
    "superficie": "#0E1524",         # card onde o grafico mora: anel dos marcadores / vao entre fatias
    "texto1": "#F4F6FB",
    "texto2": "#B3C0D6",
    "texto3": "#98A7C2",
    "inativo": "rgba(152,167,194,0.35)",
    "grade": "rgba(142,155,179,0.10)",
    "eixo": "rgba(142,155,179,0.22)",
    "tooltip_fundo": "#111A2E",
    "tooltip_borda": "#2A3854",
    "tooltip_sombra": "0 10px 28px rgba(0,0,0,.5)",
    "etiqueta_fundo": "#2A3854",
    "etiqueta_texto": "#F4F6FB",
    "ponteiro": "rgba(235,220,178,0.5)",
    "sombra_barra": "rgba(201,169,97,0.10)",
    "destaque": "#C9A961",           # serie unica
    "destaque_claro": "#EBDCB2",
    "destaque_escuro": "#A98B4F",
    "perigo": "#E5484D",
    "alerta": "#F0B429",
    "sucesso": "#30A46C",
    "positivo": "#30A46C",
    "negativo": "#E5484D",
    "outros": "#5C6A85",
    "categorias": ["#B08A2A", "#3987e5", "#d55181", "#008300",
                   "#e66767", "#9085e9", "#199e70", "#d95926"],
    "div_neg": "#3987e5", "div_meio": "#253048", "div_pos": "#e66767",
    "seq": ["#1A2438", "#C9A961"],
    "zoom_fundo": "rgba(142,155,179,0.06)",
    "zoom_selecao": "rgba(201,169,97,0.16)",
}

TEMA_CLARO = {
    "nome": "claro",
    "fonte": "Manrope, sans-serif",
    "fonte_carregar": "Manrope",
    "fundo": "transparent",
    "superficie": "#FFFFFF",
    "texto1": "#0F172A",
    "texto2": "#475569",
    "texto3": "#64748B",
    "inativo": "#CBD5E1",
    "grade": "#E9EDF3",
    "eixo": "#CBD5E1",
    "tooltip_fundo": "#FFFFFF",
    "tooltip_borda": "#E2E8F0",
    "tooltip_sombra": "0 10px 28px rgba(15,23,42,.14)",
    "etiqueta_fundo": "#334155",
    "etiqueta_texto": "#FFFFFF",
    "ponteiro": "rgba(15,23,42,0.35)",
    "sombra_barra": "rgba(160,122,31,0.08)",
    "destaque": "#A07A1F",
    "destaque_claro": "#C9A961",
    "destaque_escuro": "#7A5C14",
    "perigo": "#D03B3B",
    "alerta": "#C98500",
    "sucesso": "#0C8A0C",
    "positivo": "#0C8A0C",
    "negativo": "#D03B3B",
    "outros": "#94A3B8",
    "categorias": ["#A07A1F", "#2a78d6", "#e87ba4", "#008300",
                   "#1baf7a", "#eb6834", "#4a3aa7", "#e34948"],
    "div_neg": "#2a78d6", "div_meio": "#F0EFEC", "div_pos": "#e34948",
    "seq": ["#F6F0E0", "#A07A1F"],
    "zoom_fundo": "rgba(15,23,42,0.04)",
    "zoom_selecao": "rgba(160,122,31,0.14)",
}


def tema_com(base=None, **mudancas):
    """Copia um tema trocando so o que o app precisa (ex.: fundo='#0E1524')."""
    t = dict(base or TEMA_ESCURO)
    t.update(mudancas)
    return t


def cor_categoria(i, tema=None):
    """Cor da i-esima entidade (0-based). Da 9a em diante: cinza 'outros'."""
    t = tema or TEMA_ESCURO
    cats = t["categorias"]
    return cats[i] if 0 <= i < len(cats) else t["outros"]


def mapa_cores(nomes, tema=None, fixas=None):
    """{nome: cor} em ordem fixa. Use UMA vez com a lista completa de entidades
    e reaproveite o dict - assim filtro nao repinta ninguem."""
    fixas = dict(fixas or {})
    out, i = {}, 0
    for n in nomes:
        if n in fixas:
            out[n] = fixas[n]
        else:
            out[n] = cor_categoria(i, tema)
            i += 1
    return out


# =============================================================================
# JSON COM FUNCOES JS
# =============================================================================
class JS(str):
    """Trecho de JavaScript cru dentro do option (funcao ou expressao)."""


def _limpar(o, js):
    if isinstance(o, JS):
        js.append(str(o).replace("</script", "<\\/script"))
        return "@@AWRJS%d@@" % (len(js) - 1)
    if o is None or isinstance(o, (bool, str)):
        return o
    if isinstance(o, dict):
        return {str(k): _limpar(v, js) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [_limpar(v, js) for v in o]
    if isinstance(o, int):
        return o
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    nome_tipo = type(o).__name__
    if nome_tipo in ("NAType", "NaTType"):
        return None
    if isinstance(o, (_dt.datetime, _dt.date)):
        return o.isoformat()
    if hasattr(o, "tolist"):                      # numpy array/escalar, pandas Series/Index
        return _limpar(o.tolist(), js)
    if hasattr(o, "isoformat"):                   # pandas Timestamp
        return o.isoformat()
    if hasattr(o, "item"):
        return _limpar(o.item(), js)
    try:
        f = float(o)                              # Decimal
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return str(o)


def para_json(obj):
    """JSON do option com as JS(...) inseridas cruas e '</' escapado."""
    js = []
    limpo = _limpar(obj, js)
    s = json.dumps(limpo, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    s = s.replace("</", "<\\/")
    for i, code in enumerate(js):
        s = s.replace('"@@AWRJS%d@@"' % i, code)
    return s


def mesclar(a, b):
    """Merge profundo: b por cima de a (dicts aninhados); devolve copia."""
    out = deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = mesclar(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


# =============================================================================
# FORMATACAO NO PYTHON (mesma regra do AWR.fmt no JS)
# =============================================================================
def _br(v, casas):
    s = f"{abs(v):,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _vazio(v):
    if v is None:
        return True
    try:
        return math.isnan(float(v)) or math.isinf(float(v))
    except (TypeError, ValueError):
        return False


def brl(v, casas=0):
    if _vazio(v):
        return "–"
    return ("-" if v < 0 else "") + "R$ " + _br(v, casas)


def compacto(v, prefixo=""):
    if _vazio(v):
        return "–"
    a, s = abs(v), ("-" if v < 0 else "")
    for lim, suf in ((1e9, " bi"), (1e6, " mi")):
        if a >= lim:
            return s + prefixo + _br(a / lim, 1).removesuffix(",0") + suf
    if a >= 1e4:
        return s + prefixo + _br(a / 1e3, 0) + " mil"
    if a >= 1e3:
        return s + prefixo + _br(a / 1e3, 1).removesuffix(",0") + " mil"
    return s + prefixo + _br(a, 0)


def brl_compacto(v):
    return compacto(v, "R$ ")


def pct(v, casas=1, fracao=False):
    if _vazio(v):
        return "–"
    x = v * 100 if fracao else v
    return ("-" if x < 0 else "") + _br(x, casas) + "%"


def num(v, casas=0):
    if _vazio(v):
        return "–"
    return ("-" if v < 0 else "") + _br(v, casas)


def formatar(v, spec="num"):
    """Formata como o AWR.fmt(spec) do JS."""
    k, _, d = str(spec).partition(":")
    d = int(d) if d else None
    if _vazio(v):
        return "–"
    if k == "brl":
        return brl(v, d or 0)
    if k == "brlc":
        return brl_compacto(v)
    if k == "pct":
        return pct(v, 1 if d is None else d)
    if k == "pctf":
        return pct(v, 1 if d is None else d, fracao=True)
    if k == "varpct":
        return ("+" if v > 0 else "") + pct(v, 1 if d is None else d)
    if k == "pp":
        return ("+" if v > 0 else "-" if v < 0 else "") + _br(v, 1 if d is None else d) + " p.p."
    if k == "numc":
        return compacto(v)
    if k == "mult":
        return num(v, 2 if d is None else d) + "x"
    if k == "txt":
        return str(v)
    return num(v, d or 0)


_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def rotulos_data(datas, estilo="dia"):
    """Datas -> rotulos pt-BR para o eixo/tooltip.
    estilo: 'dia' 01/out | 'dia_ano' 01/out/26 | 'mes' out/26 | 'ano' 2026 |
            'completo' qua, 01/out/2026 | 'iso' 2026-10-01"""
    out = []
    for d in list(datas):
        if d is None or type(d).__name__ in ("NaTType", "NAType") or (isinstance(d, float) and math.isnan(d)):
            out.append("")
            continue
        if isinstance(d, str):
            try:
                d = _dt.date.fromisoformat(d[:10])
            except ValueError:
                out.append(d)
                continue
        if hasattr(d, "to_pydatetime"):
            d = d.to_pydatetime()
        m = _MESES[d.month - 1]
        if estilo == "dia":
            out.append(f"{d.day:02d}/{m}")
        elif estilo == "dia_ano":
            out.append(f"{d.day:02d}/{m}/{d.year % 100:02d}")
        elif estilo == "mes":
            out.append(f"{m}/{d.year % 100:02d}")
        elif estilo == "ano":
            out.append(str(d.year))
        elif estilo == "completo":
            out.append(f"{_SEMANA[d.weekday()]}, {d.day:02d}/{m}/{d.year}")
        else:
            out.append(d.isoformat()[:10])
    return out


def _teto_bonito(v):
    """Arredonda para cima num valor 'redondo' (limite de eixo): 1; 1,2; 1,5; 2;
    2,5; 3; 4; 5; 6; 8 x 10^k."""
    if v <= 0:
        return 0
    e = 10 ** math.floor(math.log10(v))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if v <= m * e + 1e-12:
            return m * e
    return 10 * e


def _rgba(cor, a):
    c = str(cor).strip()
    if not c.startswith("#"):
        return c
    c = c[1:]
    if len(c) == 3:
        c = "".join(x * 2 for x in c)
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


def _hex_rgb(cor):
    c = str(cor).strip()
    if c.startswith("rgb"):
        p = [x.strip() for x in c[c.index("(") + 1:c.index(")")].split(",")]
        return tuple(int(float(x)) for x in p[:3])
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(x * 2 for x in c)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _luminancia(cor):
    def _lin(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _hex_rgb(cor)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contraste(a, b):
    la, lb = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _interpolar(cores, f):
    """Cor em f (0..1) de uma escala com paradas igualmente espacadas (como o visualMap)."""
    n = len(cores) - 1
    if n <= 0:
        return cores[0]
    i = min(int(f * n), n - 1)
    loc = f * n - i
    a, b = _hex_rgb(cores[i]), _hex_rgb(cores[i + 1])
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * loc) for x, y in zip(a, b))


def _degrade(cor, topo=0.22):
    return {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
            "colorStops": [{"offset": 0, "color": _rgba(cor, topo)},
                           {"offset": 1, "color": _rgba(cor, 0)}]}


def _js_fmt(spec):
    return json.dumps(spec)


# =============================================================================
# PECAS
# =============================================================================
def base(tema=None):
    t = tema or TEMA_ESCURO
    return {
        "backgroundColor": "transparent",
        "color": list(t["categorias"]),
        "textStyle": {"fontFamily": t["fonte"], "color": t["texto2"]},
        "animationDuration": 700,
        "animationEasing": "cubicOut",
        "animationDurationUpdate": 400,
        "aria": {"enabled": True, "decal": {"show": False}},
    }


def grade(tema=None, *, topo=16, direita=16, base_=8, esquerda=8, **kw):
    g = {"left": esquerda, "right": direita, "top": topo, "bottom": base_, "containLabel": True}
    g.update(kw)
    return g


def _etiqueta_ponteiro(t):
    return {"show": True, "backgroundColor": t["etiqueta_fundo"], "color": t["etiqueta_texto"],
            "fontFamily": t["fonte"], "fontSize": 11, "padding": [4, 6], "borderRadius": 4,
            "margin": 6}


def eixo_categoria(dados, tema=None, *, rotulos=True, etiqueta=True, grid=0, truncar=None,
                   invertido=False, lacuna=True, **kw):
    t = tema or TEMA_ESCURO
    rot = {"show": rotulos, "color": t["texto3"], "fontFamily": t["fonte"], "fontSize": 11,
           "hideOverlap": True}
    if truncar:
        rot["formatter"] = JS("function(v){v=String(v);return v.length>%d?v.slice(0,%d)+'…':v;}"
                              % (truncar, truncar - 1))
    e = {"type": "category", "data": list(dados), "gridIndex": grid, "inverse": invertido,
         "boundaryGap": lacuna,
         "axisLine": {"lineStyle": {"color": t["eixo"]}}, "axisTick": {"show": False},
         "axisLabel": rot,
         "axisPointer": {"label": _etiqueta_ponteiro(t) if etiqueta else {"show": False}}}
    return mesclar(e, kw)


def eixo_valor(fmt="num", tema=None, *, escala=False, grid=0, divisoes=4, nome=None, **kw):
    t = tema or TEMA_ESCURO
    e = {"type": "value", "gridIndex": grid, "scale": escala, "splitNumber": divisoes,
         "splitLine": {"lineStyle": {"color": t["grade"]}},
         "axisLine": {"show": False}, "axisTick": {"show": False},
         "axisLabel": {"color": t["texto3"], "fontFamily": t["fonte"], "fontSize": 11,
                       "formatter": JS("AWR.eixo(%s)" % _js_fmt(fmt)), "hideOverlap": True},
         "axisPointer": {"label": {"show": False}}}
    if nome:
        e.update({"name": nome, "nameLocation": "middle", "nameGap": 34,
                  "nameTextStyle": {"color": t["texto3"], "fontFamily": t["fonte"], "fontSize": 11}})
    return mesclar(e, kw)


def _tooltip_base(t):
    return {
        "backgroundColor": t["tooltip_fundo"], "borderColor": t["tooltip_borda"], "borderWidth": 1,
        "padding": [10, 12], "confine": True, "transitionDuration": 0.2,
        "textStyle": {"color": t["texto1"], "fontFamily": t["fonte"], "fontSize": 12},
        "extraCssText": "border-radius:8px;box-shadow:%s;" % t["tooltip_sombra"],
    }


def tooltip_eixo(fmt="num", tema=None, *, fmts=None, cab=None, rodape=None, total=None,
                 ordenar=False, extras=False, ponteiro="line"):
    """Tooltip de eixo (uma leitura com todas as series naquele X).
    fmts: {indice_da_serie: fmt} ou lista; cab: rotulo completo por indice (ex.
    data por extenso); rodape: texto por indice; total: rotulo da linha de soma."""
    t = tema or TEMA_ESCURO
    o = {"fmt": fmt}
    if fmts is not None:
        o["fmts"] = fmts if isinstance(fmts, dict) else {i: f for i, f in enumerate(fmts)}
    if cab is not None:
        o["cab"] = list(cab)
    if rodape is not None:
        o["rodape"] = list(rodape)
    if total:
        o["total"] = total
    if ordenar:
        o["ordenar"] = True
    if extras:
        o["extras"] = True
    d = _tooltip_base(t)
    d.update({"trigger": "axis", "formatter": JS("AWR.tipEixo(%s)" % para_json(o))})
    if ponteiro == "line":
        d["axisPointer"] = {"type": "line", "lineStyle": {"color": t["ponteiro"], "width": 1}}
    elif ponteiro == "shadow":
        d["axisPointer"] = {"type": "shadow", "shadowStyle": {"color": t["sombra_barra"]}}
    elif ponteiro == "cross":
        d["axisPointer"] = {"type": "cross", "lineStyle": {"color": t["ponteiro"], "width": 1},
                            "crossStyle": {"color": t["ponteiro"], "width": 1}}
    return d


def tooltip_item(fmt="num", tema=None, *, nome=None, pct=True):
    t = tema or TEMA_ESCURO
    o = {"fmt": fmt, "pct": pct}
    if nome is not None:
        o["nome"] = nome
    d = _tooltip_base(t)
    d.update({"trigger": "item", "formatter": JS("AWR.tipItem(%s)" % para_json(o))})
    return d


def legenda(tema=None, *, tipo="linha", **kw):
    t = tema or TEMA_ESCURO
    linha_ = tipo == "linha"
    l = {"top": 0, "left": 0, "icon": "roundRect",
         "itemWidth": 14 if linha_ else 10, "itemHeight": 3 if linha_ else 10, "itemGap": 16,
         "textStyle": {"color": t["texto2"], "fontFamily": t["fonte"], "fontSize": 12},
         "inactiveColor": t["inativo"], "type": "scroll",
         "pageIconColor": t["texto2"], "pageIconInactiveColor": t["inativo"],
         "pageTextStyle": {"color": t["texto3"]}}
    return mesclar(l, kw)


def zoom(tipo="inside", tema=None, *, eixos=(0,), eixo="x", base_=4, inicio=None, fim=None):
    """'inside': arrastar = mover; Ctrl+rolagem ou pinca no trackpad = zoom
    (rolagem normal continua rolando a pagina). 'slider': inside + barrinha."""
    t = tema or TEMA_ESCURO
    chave = "xAxisIndex" if eixo == "x" else "yAxisIndex"
    dentro = {"type": "inside", chave: list(eixos), "zoomOnMouseWheel": "ctrl",
              "moveOnMouseMove": True, "moveOnMouseWheel": False, "preventDefaultMouseMove": False}
    if inicio is not None:
        dentro["start"] = inicio
    if fim is not None:
        dentro["end"] = fim
    if tipo != "slider":
        return [dentro]
    barra = {"type": "slider", chave: list(eixos), "bottom": base_, "height": 18, "brushSelect": False,
             "borderColor": "transparent", "backgroundColor": t["zoom_fundo"],
             "fillerColor": t["zoom_selecao"],
             "handleStyle": {"color": t["destaque"], "borderColor": t["destaque"]},
             "moveHandleStyle": {"color": t["destaque_escuro"], "opacity": 0.6},
             "textStyle": {"color": t["texto3"], "fontFamily": t["fonte"], "fontSize": 10},
             "dataBackground": {"lineStyle": {"color": t["destaque_escuro"], "opacity": 0.5},
                                "areaStyle": {"color": t["destaque_escuro"], "opacity": 0.12}},
             "selectedDataBackground": {"lineStyle": {"color": t["destaque"]},
                                        "areaStyle": {"color": t["destaque"], "opacity": 0.22}},
             "labelFormatter": JS("function(v,s){return s;}")}
    if inicio is not None:
        barra["start"] = inicio
    if fim is not None:
        barra["end"] = fim
    return [dentro, barra]


def referencias(itens, tema=None, *, eixo="y", posicao="end"):
    """Linhas de referencia tracejadas (markLine). itens: [dict(valor, rotulo, cor)]."""
    t = tema or TEMA_ESCURO
    dados = []
    for it in itens or []:
        cor = it.get("cor") or t["texto3"]
        dados.append({"name": it.get("rotulo", ""), ("yAxis" if eixo == "y" else "xAxis"): it["valor"],
                      "lineStyle": {"color": cor},
                      "label": {"color": cor}})
    return {"symbol": "none", "silent": True, "animation": False,
            "lineStyle": {"type": "dashed", "width": 1, "opacity": 0.8},
            "label": {"formatter": "{b}", "position": posicao, "fontFamily": t["fonte"],
                      "fontSize": 11, "lineHeight": 13},
            "data": dados}


def faixa(itens, tema=None, *, eixo="y"):
    """Faixas sombreadas (markArea) - limite/meta/zona. itens:
    [dict(de, ate, rotulo, cor)]. O rotulo fica em cima da faixa."""
    t = tema or TEMA_ESCURO
    chave = "yAxis" if eixo == "y" else "xAxis"
    dados = []
    for it in itens or []:
        cor = it.get("cor") or t["perigo"]
        dados.append([{"name": it.get("rotulo", ""), chave: it["de"],
                       "itemStyle": {"color": _rgba(cor, 0.08)},
                       "label": {"color": cor}},
                      {chave: it["ate"]}])
    return {"silent": True, "animation": False,
            "label": {"show": True, "position": "top" if eixo == "x" else "insideTopRight",
                      "fontFamily": t["fonte"], "fontSize": 11, "fontWeight": 600},
            "data": dados}


def _awr_ponto(extras, notas, i):
    a = {}
    if extras is not None and i < len(extras) and extras[i]:
        a["linhas"] = [[str(r), str(v)] for r, v in extras[i]]
    if notas is not None and i < len(notas) and notas[i]:
        n = notas[i]
        if isinstance(n, (tuple, list)):
            a["nota"], a["nota_cor"] = str(n[0]), n[1]
        else:
            a["nota"] = str(n)
    return a


def _normalizar_series(series, nome_padrao="_serie"):
    if series and isinstance(series[0], dict):
        return [dict(s) for s in series]
    return [{"nome": nome_padrao, "dados": list(series)}]


def _ultimo(dados):
    for v in reversed(list(dados)):
        if isinstance(v, dict):
            v = v.get("value")
        if not _vazio(v):
            return v
    return None


def _esticar_para_refs(dados, refs, eixo_min, eixo_max, escala):
    """Estica o eixo para uma referencia fora da faixa dos dados aparecer
    (ex.: Saldo inicial acima de todo o historico). Nao mexe no que o app fixou."""
    vals = []
    for v in dados:
        if isinstance(v, dict):
            v = v.get("value")
        if isinstance(v, (list, tuple)):
            v = v[-1] if v else None
        if not _vazio(v) and not isinstance(v, str):
            vals.append(float(v))
    rv = [float(r["valor"]) for r in refs or [] if not _vazio(r.get("valor"))]
    if not vals or not rv:
        return eixo_min, eixo_max
    dmin, dmax = min(vals), max(vals)
    rmin, rmax = min(rv), max(rv)
    if eixo_max is None and rmax > dmax:
        eixo_max = _teto_bonito(rmax * 1.04) if rmax > 0 else rmax * 0.96
    if eixo_min is None and rmin < dmin and (escala or rmin < 0):
        eixo_min = -_teto_bonito(-rmin * 1.04) if rmin < 0 else rmin * 0.96
    return eixo_min, eixo_max


# =============================================================================
# CONSTRUTORES
# =============================================================================
def linha(x, series, *, fmt="num", fmt_eixo=None, tema=None, area=None, rotulo_final=None,
          refs=None, faixas=None, escala=False, zoom_=None, cab=None, rodape=None, titulo=None,
          legenda_=None, suave=False, empilhar=False, marcadores=False, ordenar_tooltip=None,
          eixo_min=None, eixo_max=None, conectar_nulos=False, rotulo_nome=False,
          tooltip_proximo=None, extras_series=None, **extra):
    """Linha/area no tempo.
    x ........ rotulos do eixo X (use rotulos_data(...) para datas)
    series ... lista de numeros (1 serie) ou [dict(nome, dados, cor=None, fmt=None,
               tracejado=False, pontilhado=False, area=None, largura=2,
               conectar=None, sem_rotulo=False)]
    refs ..... [dict(valor, rotulo, cor=None)] -> linha tracejada com rotulo fora;
               o eixo Y estica sozinho para a referencia aparecer
    faixas ... [dict(de, ate, rotulo, cor=None)] -> faixa sombreada no eixo Y
    zoom_ .... None | 'inside' | 'slider' (padrao: pelo tamanho da serie)
    cab ...... rotulo completo por ponto para o topo do tooltip (ex. estilo='completo')
    conectar_nulos: liga a linha por cima de datas sem valor (series com calendarios
               diferentes alinhadas numa uniao de datas); por serie: conectar=True
    rotulo_nome: rotulo da ponta leva o nome da serie ("Long Bias +6,7%")
    tooltip_proximo: tooltip so da linha mais perto do mouse (ela acende, as outras
               apagam). Padrao: ligado com mais de 4 series - pedido dele em 01/10/2026
               ("e para aparecer so o que eu estou com o mouse").
    extras_series: {nome_da_serie: [(rotulo, valor_formatado), ...]} - linhas extras
               no tooltip_proximo (ex. nome completo, CNPJ)
    """
    t = tema or TEMA_ESCURO
    ss = _normalizar_series(series)
    n = len(ss)
    multi = n > 1
    area = (not multi) if area is None else area
    rotulo_final = (n <= 4) if rotulo_final is None else rotulo_final
    npts = len(x)
    if zoom_ is None:
        zoom_ = "slider" if npts > 90 else ("inside" if npts > 30 else None)
    mostra_leg = multi if legenda_ is None else legenda_

    fmts = {}
    series_ec = []
    for i, s in enumerate(ss):
        cor = s.get("cor") or (t["destaque"] if not multi else cor_categoria(i, t))
        fs = s.get("fmt") or fmt
        fmts[i] = fs
        dados = list(s["dados"])
        se = {
            "name": s.get("nome", "_serie"), "type": "line", "data": dados,
            "showSymbol": marcadores, "symbol": "circle", "symbolSize": 8,
            "smooth": suave,
            "connectNulls": bool(conectar_nulos if s.get("conectar") is None else s.get("conectar")),
            "lineStyle": {"width": s.get("largura", 2), "color": cor,
                          "type": ("dashed" if s.get("tracejado")
                                   else "dotted" if s.get("pontilhado") else "solid")},
            "itemStyle": {"color": cor, "borderColor": t["superficie"], "borderWidth": 2},
            "emphasis": {"focus": "series" if multi else "none", "lineStyle": {"width": 2.5}},
            "blur": {"lineStyle": {"opacity": 0.22}, "areaStyle": {"opacity": 0.05}},
            "z": 3,
        }
        if len(dados) > 1500:
            se["sampling"] = "lttb"
        a = s.get("area", area)
        if a:
            se["areaStyle"] = {"color": _degrade(cor, 0.22 if not multi else 0.10)}
        if empilhar:
            se["stack"] = "total"
        if rotulo_final and not s.get("sem_rotulo"):
            fjs = ("AWR.rotuloNome(%s)" if rotulo_nome else "AWR.rotuloCurto(%s)") % _js_fmt(fs)
            se["endLabel"] = {"show": True, "formatter": JS(fjs),
                              "color": t["texto1"], "fontFamily": t["fonte"], "fontWeight": 600,
                              "fontSize": 12, "distance": 6}
            se["labelLayout"] = {"moveOverlap": "shiftY"}
        series_ec.append(se)

    if series_ec:
        if refs:
            series_ec[0]["markLine"] = referencias(refs, t)
        if faixas:
            series_ec[0]["markArea"] = faixa(faixas, t)

    if refs and not empilhar:
        eixo_min, eixo_max = _esticar_para_refs(
            [v for s in ss for v in s["dados"]], refs, eixo_min, eixo_max, escala)

    topo = 16 + (28 if mostra_leg else 0) + (22 if titulo else 0)
    direita = (140 if rotulo_nome else 84) if (rotulo_final or refs) else 28   # 28: a ultima data nao corta
    opt = base(t)
    opt.update({
        "grid": grade(t, topo=topo, direita=direita, base_=(36 if zoom_ == "slider" else 8)),
        "xAxis": eixo_categoria(x, t, lacuna=False),
        "yAxis": eixo_valor(fmt_eixo or fmt, t, escala=escala,
                            **({"min": eixo_min} if eixo_min is not None else {}),
                            **({"max": eixo_max} if eixo_max is not None else {})),
        "tooltip": tooltip_eixo(fmt, t, fmts=fmts, cab=cab, rodape=rodape,
                                ordenar=(n > 4) if ordenar_tooltip is None else ordenar_tooltip),
        "series": series_ec,
    })
    if (n > 4) if tooltip_proximo is None else tooltip_proximo:
        o = {"fmt": fmt, "fmts": fmts}
        if cab is not None:
            o["cab"] = list(cab)
        if rodape is not None:
            o["rodape"] = list(rodape)
        if extras_series:
            o["extras"] = {str(k): [[str(r), str(v)] for r, v in vs] for k, vs in extras_series.items()}
        opt["tooltip"]["formatter"] = JS("AWR.tipProximo(%s)" % para_json(o))
        # sem isto o crosshair acende o ponto de TODAS as series na data e o
        # foco (as outras apagarem) nao acontece
        opt["tooltip"]["axisPointer"]["triggerEmphasis"] = False
        opt["xAxis"]["axisPointer"]["triggerEmphasis"] = False
    if zoom_:
        opt["dataZoom"] = zoom(zoom_, t)
    if mostra_leg:
        opt["legend"] = legenda(t, tipo="linha", top=22 if titulo else 0)
    if titulo:
        opt["title"] = _titulo(titulo, t)
    return mesclar(opt, extra)


def _titulo(texto, t, top=0, left=0):
    return {"text": texto, "left": left, "top": top,
            "textStyle": {"color": t["texto2"], "fontSize": 12, "fontWeight": 500, "fontFamily": t["fonte"]}}


def barras(categorias, valores=None, *, series=None, horizontal=False, fmt="num", fmt_eixo=None,
           tema=None, cores=None, cor=None, rotulos=None, limite=None, refs=None, empilhado=False,
           extras=None, notas=None, titulo=None, legenda_=None, zoom_=None, eixo_min=None,
           eixo_max=None, truncar=None, cab=None, rodape=None, rotulo_fmt=None, textos=None,
           margem_direita=None, vao=None, **extra):
    """Barras verticais ou horizontais.
    valores .. 1 serie (lista)   series .. [dict(nome, dados, cor=None, fmt=None)] agrupadas/empilhadas
    cores .... cor por barra (lista) ou 'sinal' (positivo/negativo do tema)
    limite ... dict(valor, rotulo, cor=None, lado='acima'|'abaixo') -> faixa sombreada
    refs ..... [dict(valor, rotulo, cor=None)] -> linha tracejada (o eixo estica para ela)
    extras ... por barra: [(rotulo, valor_formatado), ...] no tooltip
    notas .... por barra: 'texto' ou ('texto', cor) no rodape do tooltip
    truncar .. corta rotulo da categoria no eixo (tooltip mostra o nome inteiro)
    rotulo_fmt formato do rotulo na ponta da barra, se diferente do tooltip (ex.
               tooltip 'brl:2', rotulo 'brlc')
    textos ... texto pronto por barra no lugar do rotulo (ex. 'R$ 51 mil · 9d atraso')
    margem_direita: px a direita (rotulos longos em barra horizontal)
    vao ...... espaco entre categorias (barCategoryGap, padrao '30%')
    horizontal: 1a categoria em cima (ranking)."""
    t = tema or TEMA_ESCURO
    cats = list(categorias)
    ncat = len(cats)
    if series is None:
        ss = [{"nome": "_serie", "dados": list(valores)}]
    else:
        ss = [dict(s) for s in series]
    multi = len(ss) > 1
    rotulos = ((ncat <= 20) and not empilhado and len(ss) <= 2) if rotulos is None else rotulos
    if zoom_ is None:
        zoom_ = "slider" if ncat > 60 else None
    mostra_leg = multi if legenda_ is None else legenda_

    todos = [v for s in ss for v in s["dados"] if not _vazio(v)]
    if empilhado and todos:
        somas = [sum(v for v in (s["dados"][i] for s in ss) if not _vazio(v) and v > 0) for i in range(ncat)]
        vmax = max(somas) if somas else 0
    else:
        vmax = max(todos) if todos else 0
    vmin = min(todos) if todos else 0
    # folga do lado negativo para o rotulo da barra nao bater no nome da categoria
    folga_neg = bool(rotulos and vmin < 0 and eixo_min is None and not empilhado)
    if limite:
        lado = limite.get("lado", "acima")
        if eixo_max is None:
            eixo_max = _teto_bonito(max(vmax, limite["valor"]) * 1.12)
        if lado == "abaixo" and eixo_min is None and vmin < 0:
            eixo_min = -_teto_bonito(abs(vmin) * 1.12)
    if refs and not empilhado:
        eixo_min, eixo_max = _esticar_para_refs(todos, refs, eixo_min, eixo_max, False)

    raio_pos = [0, 4, 4, 0] if horizontal else [4, 4, 0, 0]
    raio_neg = [4, 0, 0, 4] if horizontal else [0, 0, 4, 4]
    pos_pos, pos_neg = ("right", "left") if horizontal else ("top", "bottom")

    series_ec = []
    for si, s in enumerate(ss):
        cor_s = s.get("cor") or cor or (t["destaque"] if not multi else cor_categoria(si, t))
        dados = []
        for i, v in enumerate(s["dados"]):
            item = {"value": None if _vazio(v) else v}
            neg = (not _vazio(v)) and v < 0
            c = None
            if not multi:
                if cores == "sinal":
                    c = t["negativo"] if neg else t["positivo"]
                elif isinstance(cores, (list, tuple)) and i < len(cores) and cores[i]:
                    c = cores[i]
            est = {"borderRadius": 0 if empilhado else (raio_neg if neg else raio_pos)}
            if c:
                est["color"] = c
            item["itemStyle"] = est
            if rotulos and neg:
                item["label"] = {"position": pos_neg}
            if rotulos and not multi and textos is not None and i < len(textos) and textos[i] is not None:
                item.setdefault("label", {})["formatter"] = str(textos[i]).replace("{", "(").replace("}", ")")
            if not multi:
                a = _awr_ponto(extras, notas, i)
                if a:
                    item["awr"] = a
            dados.append(item)
        se = {"name": s.get("nome", "_serie"), "type": "bar", "data": dados,
              "itemStyle": {"color": cor_s},
              "barMaxWidth": 28 if horizontal else 32, "barCategoryGap": vao or "30%",
              "emphasis": {"focus": "series" if multi else "self",
                           "label": {"color": t["texto1"], "fontWeight": 700}},
              "blur": {"itemStyle": {"opacity": 0.28}, "label": {"opacity": 0.35}}}
        if horizontal and not multi and ncat <= 20:
            se["barWidth"] = 14
        if empilhado:
            se["stack"] = "total"
            se["itemStyle"]["borderColor"] = t["superficie"]
            se["itemStyle"]["borderWidth"] = 1
        if rotulos:
            se["label"] = {"show": True, "position": pos_pos, "color": t["texto2"],
                           "fontFamily": t["fonte"], "fontSize": 11,
                           "formatter": JS("AWR.rotulo(%s)" % _js_fmt(rotulo_fmt or s.get("fmt") or fmt))}
        series_ec.append(se)

    if limite:
        cor_l = limite.get("cor") or t["perigo"]
        lado = limite.get("lado", "acima")
        de, ate = (limite["valor"], eixo_max) if lado == "acima" else (eixo_min or 0, limite["valor"])
        series_ec[0]["markArea"] = faixa([{"de": de, "ate": ate, "rotulo": limite.get("rotulo", ""),
                                           "cor": cor_l}], t, eixo="x" if horizontal else "y")
        if not horizontal:
            series_ec[0]["markArea"]["label"]["position"] = "insideTopRight"
    if refs:
        # horizontal: eixo Y invertido -> 'start' e o topo (fora dos rotulos do eixo X)
        series_ec[0]["markLine"] = referencias(refs, t, eixo="x" if horizontal else "y",
                                               posicao="start" if horizontal else "end")

    eixo_cat = eixo_categoria(cats, t, invertido=horizontal, truncar=truncar,
                              etiqueta=False)
    lim = {}
    if eixo_min is not None:
        lim["min"] = eixo_min
    if eixo_max is not None:
        lim["max"] = eixo_max
    eixo_val = eixo_valor(fmt_eixo or fmt, t, **lim)
    if folga_neg:
        eixo_val["boundaryGap"] = ["14%", "6%"]
    if horizontal:
        eixo_val["splitNumber"] = 5

    topo = (16 + (28 if mostra_leg else 0) + (22 if titulo else 0)
            + (18 if ((limite or refs) and horizontal) else 0))
    if margem_direita is not None:
        direita = margem_direita
    elif rotulos and horizontal:
        direita = max(60, 7 * max((len(str(x)) for x in (textos or []) if x is not None), default=0))
    else:
        direita = 84 if refs else 16
    fmts = {i: (s.get("fmt") or fmt) for i, s in enumerate(ss)}
    opt = base(t)
    opt.update({
        "grid": grade(t, topo=topo, direita=direita, base_=(36 if zoom_ == "slider" else 8)),
        "xAxis": eixo_val if horizontal else eixo_cat,
        "yAxis": eixo_cat if horizontal else eixo_val,
        "tooltip": tooltip_eixo(fmt, t, fmts=fmts, ponteiro="shadow", extras=not multi,
                                cab=cab, rodape=rodape,
                                total=("Total" if (empilhado and multi) else None)),
        "series": series_ec,
    })
    if zoom_:
        opt["dataZoom"] = zoom(zoom_, t, eixo="y" if horizontal else "x")
    if mostra_leg:
        opt["legend"] = legenda(t, tipo="barra", top=22 if titulo else 0)
    if titulo:
        opt["title"] = _titulo(titulo, t)
    return mesclar(opt, extra)


def paineis_ligados(x, superior, inferior, *, tema=None, zoom_="slider", cab=None, rodape=None,
                    altura_sup="34%", **extra):
    """Duas medidas de escala diferente, empilhadas, com o MESMO crosshair
    (substitui eixo duplo). superior/inferior: dict(tipo='barra'|'linha', nome,
    dados, fmt, cor=None, titulo=None, area=True, rotulo_final=True)."""
    t = tema or TEMA_ESCURO
    paineis = [superior, inferior]
    tem_zoom = bool(zoom_)
    series_ec, fmts = [], {}
    for i, p in enumerate(paineis):
        cor = p.get("cor") or (t["destaque"] if i == 0 else t["destaque_claro"])
        fs = p.get("fmt", "num")
        fmts[i] = fs
        if p.get("tipo", "linha") == "barra":
            se = {"name": p.get("nome", ""), "type": "bar", "xAxisIndex": i, "yAxisIndex": i,
                  "data": list(p["dados"]), "barCategoryGap": "30%", "barMaxWidth": 24,
                  "itemStyle": {"color": cor, "borderRadius": [4, 4, 0, 0]},
                  "emphasis": {"itemStyle": {"color": t["destaque_claro"] if i == 0 else cor}}}
        else:
            se = {"name": p.get("nome", ""), "type": "line", "xAxisIndex": i, "yAxisIndex": i,
                  "data": list(p["dados"]), "showSymbol": False, "symbol": "circle", "symbolSize": 8,
                  "lineStyle": {"width": 2, "color": cor},
                  "itemStyle": {"color": cor, "borderColor": t["superficie"], "borderWidth": 2}}
            if p.get("area", True):
                se["areaStyle"] = {"color": _degrade(cor, 0.12)}
            if p.get("rotulo_final", True):
                se["endLabel"] = {"show": True, "formatter": JS("AWR.rotuloCurto(%s)" % _js_fmt(fs)),
                                  "color": t["texto1"], "fontFamily": t["fonte"], "fontWeight": 600,
                                  "fontSize": 12}
        series_ec.append(se)

    # barras precisam de meia categoria de folga nas pontas; linhas encostam na borda.
    # Os dois eixos X usam a MESMA folga para as datas ficarem alinhadas.
    tem_barra = any(p.get("tipo", "linha") == "barra" for p in paineis)
    x_sup = eixo_categoria(x, t, grid=0, rotulos=False, etiqueta=False, lacuna=tem_barra)
    if superior.get("tipo", "linha") == "barra":
        x_sup["axisPointer"] = {"type": "shadow", "shadowStyle": {"color": t["sombra_barra"]},
                                "label": {"show": False}}
    else:
        x_sup["axisPointer"] = {"type": "line", "lineStyle": {"color": t["ponteiro"], "width": 1},
                                "label": {"show": False}}
    x_inf = eixo_categoria(x, t, grid=1, lacuna=tem_barra)
    if inferior.get("tipo", "linha") == "barra":
        x_inf["axisPointer"]["type"] = "shadow"
        x_inf["axisPointer"]["shadowStyle"] = {"color": t["sombra_barra"]}
    else:
        x_inf["axisPointer"]["type"] = "line"
        x_inf["axisPointer"]["lineStyle"] = {"color": t["ponteiro"], "width": 1}
    base_inf = 36 if tem_zoom else 8
    # altura_sup em %: titulo de baixo 13 pontos abaixo, painel de baixo 20 abaixo
    # (34% -> 47% / 54%, o layout aprovado)
    try:
        h_sup = float(str(altura_sup).rstrip("%"))
    except ValueError:
        h_sup = 34.0
    opt = base(t)
    opt.update({
        "axisPointer": {"link": [{"xAxisIndex": "all"}]},
        "title": [_titulo(superior.get("titulo", superior.get("nome", "")), t, top=0, left=8),
                  _titulo(inferior.get("titulo", inferior.get("nome", "")), t,
                          top=f"{h_sup + 13:g}%", left=8)],
        # esquerda fixa (sem containLabel) para os dois paineis ficarem alinhados no X
        "grid": [grade(t, topo=26, direita=84, esquerda=72, height=f"{h_sup:g}%", base_=None,
                       containLabel=False),
                 grade(t, topo=f"{h_sup + 20:g}%", direita=84, esquerda=72, base_=base_inf + 20,
                       containLabel=False)],
        "xAxis": [x_sup, x_inf],
        "yAxis": [eixo_valor(superior.get("fmt", "num"), t, grid=0, divisoes=3),
                  eixo_valor(inferior.get("fmt", "num"), t, grid=1, divisoes=3)],
        "tooltip": tooltip_eixo(superior.get("fmt", "num"), t, fmts=fmts, cab=cab, rodape=rodape,
                                ponteiro=None),
        "series": series_ec,
    })
    for g in opt["grid"]:
        if g.get("bottom") is None:
            g.pop("bottom")
    if tem_zoom:
        opt["dataZoom"] = zoom(zoom_, t, eixos=(0, 1))
    return mesclar(opt, extra)


def rosca(rotulos, valores, *, fmt="brl", tema=None, cores=None, centro=None, centro_sub=None,
          extras=None, notas=None, raio=("56%", "76%"), rotulos_fora=True, **extra):
    """Parte-de-um-todo com ate ~6 fatias (acima disso use barras)."""
    t = tema or TEMA_ESCURO
    dados = []
    for i, (r, v) in enumerate(zip(rotulos, valores)):
        c = (cores[i] if cores and i < len(cores) and cores[i] else cor_categoria(i, t))
        item = {"name": str(r), "value": None if _vazio(v) else v, "itemStyle": {"color": c}}
        a = _awr_ponto(extras, notas, i)
        if a:
            item["awr"] = a
        dados.append(item)
    se = {"name": "_serie", "type": "pie", "radius": list(raio), "center": ["50%", "52%"],
          "padAngle": 1.5, "minAngle": 2, "avoidLabelOverlap": True,
          "itemStyle": {"borderRadius": 4, "borderColor": t["superficie"], "borderWidth": 2},
          "data": dados,
          "label": {"show": rotulos_fora, "color": t["texto2"], "fontFamily": t["fonte"], "fontSize": 12,
                    "formatter": JS("AWR.rotuloRosca"), "lineHeight": 16,
                    "rich": {"v": {"color": t["texto1"], "fontWeight": 700, "fontSize": 13,
                                   "fontFamily": t["fonte"]}}},
          "labelLine": {"lineStyle": {"color": t["eixo"]}, "length": 10, "length2": 12},
          "emphasis": {"scale": True, "scaleSize": 6, "focus": "self",
                       "label": {"color": t["texto1"], "fontWeight": 600}},
          "blur": {"itemStyle": {"opacity": 0.35}}}
    opt = base(t)
    opt.update({"tooltip": tooltip_item(fmt, t), "series": [se]})
    if centro:
        opt["title"] = {"text": centro, "subtext": centro_sub or "", "left": "center", "top": "center",
                        "itemGap": 4,
                        "textStyle": {"color": t["texto1"], "fontSize": 18, "fontWeight": 700,
                                      "fontFamily": t["fonte"]},
                        "subtextStyle": {"color": t["texto3"], "fontSize": 11, "fontFamily": t["fonte"]}}
    return mesclar(opt, extra)


def dispersao(pontos, *, fmt_x="pct", fmt_y="pct", nome_x="", nome_y="", tema=None, rotulos=True,
              refs_x=None, refs_y=None, tamanho=12, **extra):
    """Pontos nomeados (ex.: risco x retorno). pontos: [dict(nome, x, y, cor=None,
    grupo=None, extras=None, nota=None)]. Com 'grupo' vira uma serie por grupo
    (legenda); sem grupo, uma serie com a cor de cada ponto."""
    t = tema or TEMA_ESCURO
    grupos = []
    for p in pontos:
        g = p.get("grupo")
        if g is not None and g not in grupos:
            grupos.append(g)

    def _item(p):
        it = {"name": str(p["nome"]), "value": [p["x"], p["y"]]}
        if p.get("cor"):
            it["itemStyle"] = {"color": p["cor"]}
        a = _awr_ponto([p.get("extras")], [p.get("nota")], 0)
        if a:
            it["awr"] = a
        return it

    comum = {"type": "scatter", "symbolSize": tamanho,
             "itemStyle": {"borderColor": t["superficie"], "borderWidth": 2, "opacity": 0.95},
             "emphasis": {"focus": "self", "scale": 1.4,
                          "label": {"show": True, "color": t["texto1"], "fontWeight": 700}},
             "blur": {"itemStyle": {"opacity": 0.25}, "label": {"opacity": 0.3}},
             "label": {"show": rotulos, "position": "right", "formatter": "{b}", "color": t["texto2"],
                       "fontFamily": t["fonte"], "fontSize": 11},
             # so hideOverlap: no 5.5.0, hideOverlap + moveOverlap juntos desligam os dois
             "labelLayout": {"hideOverlap": True}}
    series_ec = []
    if grupos:
        for gi, g in enumerate(grupos):
            se = dict(comum, name=str(g), data=[_item(p) for p in pontos if p.get("grupo") == g])
            se["itemStyle"] = dict(comum["itemStyle"], color=cor_categoria(gi, t))
            series_ec.append(se)
    else:
        se = dict(comum, name="_serie", data=[_item(p) for p in pontos])
        se["itemStyle"] = dict(comum["itemStyle"], color=t["destaque"])
        series_ec.append(se)
    if refs_x:
        series_ec[0]["markLine"] = referencias(refs_x, t, eixo="x")
    if refs_y:
        ml = referencias(refs_y, t, eixo="y")
        if "markLine" in series_ec[0]:
            series_ec[0]["markLine"]["data"] += ml["data"]
        else:
            series_ec[0]["markLine"] = ml

    o = {"fmtX": fmt_x, "fmtY": fmt_y, "nomeX": nome_x, "nomeY": nome_y}
    tip = _tooltip_base(t)
    tip.update({"trigger": "item", "formatter": JS("AWR.tipDispersao(%s)" % para_json(o))})
    opt = base(t)
    opt.update({
        "grid": grade(t, topo=16 + (28 if grupos else 0), direita=24, base_=28,
                      esquerda=40 if nome_y else 8),
        # boundaryGap: folga para ponto nenhum ficar colado na borda/eixo
        "xAxis": eixo_valor(fmt_x, t, escala=True, nome=nome_x or None, boundaryGap=["8%", "8%"],
                            splitLine={"show": True, "lineStyle": {"color": t["grade"]}}),
        "yAxis": eixo_valor(fmt_y, t, escala=True, nome=nome_y or None, nameGap=48,
                            boundaryGap=["8%", "8%"]),
        "tooltip": tip, "series": series_ec,
    })
    if grupos:
        opt["legend"] = legenda(t, tipo="barra")
    return mesclar(opt, extra)


def mapa_calor(x_rotulos, y_rotulos, matriz, *, fmt="num:2", minimo=None, maximo=None,
               divergente=True, tema=None, rotulos=True, escala_visivel=True, **extra):
    """Matriz (ex.: correlacao). matriz[linha_y][coluna_x]. divergente=True usa
    azul <-> cinza <-> vermelho com o meio no ponto medio de [minimo, maximo]."""
    t = tema or TEMA_ESCURO
    xs, ys = [str(v) for v in x_rotulos], [str(v) for v in y_rotulos]
    vals = [v for lin in matriz for v in lin if not _vazio(v)]
    lo = min(vals) if minimo is None and vals else (minimo if minimo is not None else 0)
    hi = max(vals) if maximo is None and vals else (maximo if maximo is not None else 1)
    cores = [t["div_neg"], t["div_meio"], t["div_pos"]] if divergente else list(t["seq"])

    def _cor_txt(v):
        # texto claro ou escuro, o que tiver mais contraste com a cor REAL da celula
        f = (v - lo) / ((hi - lo) or 1)
        fundo = _interpolar(cores, max(0.0, min(1.0, f)))
        return max(("#FFFFFF", "#0F172A"), key=lambda c: _contraste(c, fundo))

    dados = []
    for yi, lin in enumerate(matriz):
        for xi, v in enumerate(lin):
            if _vazio(v):
                dados.append({"value": [xi, yi, "-"]})
            else:
                dados.append({"value": [xi, yi, v], "label": {"color": _cor_txt(v)}})
    o = {"fmt": fmt, "x": xs, "y": ys}
    tip = _tooltip_base(t)
    tip.update({"trigger": "item", "formatter": JS("AWR.tipCalor(%s)" % para_json(o))})
    opt = base(t)
    opt.update({
        "grid": grade(t, topo=8, direita=16, base_=(48 if escala_visivel else 8)),
        "xAxis": eixo_categoria(xs, t, etiqueta=False, splitArea={"show": False},
                                axisLabel={"rotate": 30 if len(xs) > 8 else 0, "hideOverlap": False,
                                           "interval": 0}),
        "yAxis": eixo_categoria(ys, t, etiqueta=False, invertido=True,
                                axisLabel={"hideOverlap": False, "interval": 0}),
        "visualMap": {"min": lo, "max": hi, "calculable": False, "orient": "horizontal",
                      "left": "center", "bottom": 0, "itemHeight": 140, "itemWidth": 10,
                      "show": escala_visivel, "inRange": {"color": cores},
                      "text": [formatar(hi, fmt), formatar(lo, fmt)], "itemGap": 8,
                      "textStyle": {"color": t["texto3"], "fontFamily": t["fonte"], "fontSize": 11}},
        "tooltip": tip,
        "series": [{"name": "_serie", "type": "heatmap", "data": dados,
                    "itemStyle": {"borderColor": t["superficie"], "borderWidth": 2, "borderRadius": 3},
                    "label": {"show": rotulos, "color": t["texto1"], "fontFamily": t["fonte"],
                              "fontSize": 11, "formatter": JS("AWR.rotulo(%s)" % _js_fmt(fmt))},
                    "emphasis": {"itemStyle": {"borderColor": t["texto1"], "borderWidth": 1.5}}}],
    })
    return mesclar(opt, extra)


def cascata(categorias, valores, *, fmt="brl", tema=None, total="Total", inicial=None,
            rotulos=True, **extra):
    """Ponte/cascata: de um valor inicial (opcional) somando os deltas ate o total.
    Um valor None em `valores` vira barra de SUBTOTAL (mostra o acumulado ate ali).
    Funciona quando o acumulado cruza o zero (cada lado tem a sua base e as
    pilhas usam o sinal real)."""
    t = tema or TEMA_ESCURO
    cats, vals = list(categorias), list(valores)
    base_a, alta, base_b, baixa, tot_s, rod = [], [], [], [], [], []

    def _barra_total(v, nota=""):
        base_a.append("-"); alta.append("-"); base_b.append("-"); baixa.append("-")
        tot_s.append(v)
        rod.append(nota)

    corrente = 0.0
    if inicial is not None:
        cats = [inicial[0]] + cats
        corrente = float(inicial[1])
        _barra_total(corrente)
    for v in vals:
        if v is None:                      # subtotal
            _barra_total(corrente, "subtotal")
            continue
        v = 0.0 if _vazio(v) else float(v)
        novo = corrente + v
        piso = min(corrente, novo)
        if v >= 0:
            base_a.append(piso); alta.append(v); base_b.append("-"); baixa.append("-")
        else:
            base_a.append("-"); alta.append("-"); base_b.append(piso); baixa.append(-v)
        tot_s.append("-")
        rod.append("acumulado: " + formatar(novo, fmt))
        corrente = novo
    if total:
        cats.append(total)
        _barra_total(corrente)
    lbl = lambda cor_txt: {"show": rotulos, "position": "top", "color": cor_txt, "fontFamily": t["fonte"],
                           "fontSize": 11, "formatter": JS("AWR.rotulo(%s)" % _js_fmt(fmt))}
    comum = {"type": "bar", "barCategoryGap": "30%", "barGap": "-100%", "barMaxWidth": 40,
             "stackStrategy": "all",
             "emphasis": {"focus": "self"}, "blur": {"itemStyle": {"opacity": 0.3}}}
    invis = {"itemStyle": {"color": "transparent"}, "emphasis": {"disabled": True},
             "tooltip": {"show": False}, "silent": True, "label": {"show": False}}
    series_ec = [
        dict(comum, name="_base_alta", data=base_a, stack="alta", **invis),
        dict(comum, name="Alta", data=alta, stack="alta",
             itemStyle={"color": t["positivo"], "borderRadius": 3}, label=lbl(t["texto2"])),
        dict(comum, name="_base_baixa", data=base_b, stack="baixa", **invis),
        dict(comum, name="Baixa", data=baixa, stack="baixa",
             itemStyle={"color": t["negativo"], "borderRadius": 3},
             label=dict(lbl(t["texto2"]), formatter=JS("function(p){return '-'+AWR.rotulo(%s)(p);}" % _js_fmt(fmt)))),
        dict(comum, name="Total", data=tot_s, stack="total",
             itemStyle={"color": t["destaque"], "borderRadius": 3}, label=lbl(t["texto1"])),
    ]
    opt = base(t)
    opt.update({
        "grid": grade(t, topo=24, direita=16),
        "xAxis": eixo_categoria(cats, t, etiqueta=False, axisLabel={"interval": 0, "hideOverlap": False}),
        "yAxis": eixo_valor(fmt, t),
        "tooltip": mesclar(tooltip_eixo(fmt, t, rodape=rod, ponteiro="shadow"),
                           {"formatter": JS("AWR.tipCascata(%s)" % para_json({"fmt": fmt, "rodape": rod}))}),
        "series": series_ec,
    })
    return mesclar(opt, extra)


def histograma(valores, *, faixas=20, fmt_x="pct", tema=None, cor=None, refs=None, **extra):
    """Distribuicao de uma serie numerica em `faixas` intervalos iguais."""
    vs = [float(v) for v in valores if not _vazio(v)]
    if not vs:
        return barras([], [], tema=tema)
    lo, hi = min(vs), max(vs)
    if hi == lo:
        hi = lo + 1
    w = (hi - lo) / faixas
    cont = [0] * faixas
    for v in vs:
        k = min(int((v - lo) / w), faixas - 1)
        cont[k] += 1
    cats, ext = [], []
    tot = len(vs)
    for k in range(faixas):
        a, b = lo + k * w, lo + (k + 1) * w
        cats.append(formatar((a + b) / 2, fmt_x))
        ext.append([("faixa", f"{formatar(a, fmt_x)} a {formatar(b, fmt_x)}"),
                    ("do total", pct(cont[k] / tot * 100, 1))])
    return barras(cats, cont, fmt="num", tema=tema, cor=cor, rotulos=False, extras=ext, refs=refs,
                  **extra)


# =============================================================================
# RUNTIME JS (vai em toda pagina)
# =============================================================================
_RUNTIME = r"""
(function(){
var T = __TEMA__;
var NF = {};
function nf(d){ if(!NF[d]) NF[d]=new Intl.NumberFormat('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d}); return NF[d]; }
function vazio(v){ return v===null||v===undefined||v==='-'||v===''||(typeof v==='number'&&!isFinite(v)); }
function esc(x){ return String(x==null?'':x).replace(/[&<>"']/g,function(m){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m];}); }
function sem0(s){ return s.replace(/,0$/,''); }
function compacto(v, pre){
  if(vazio(v)) return '–';
  v=+v; var a=Math.abs(v), s=v<0?'-':''; pre=pre||'';
  if(a>=1e9) return s+pre+sem0(nf(1).format(a/1e9))+' bi';
  if(a>=1e6) return s+pre+sem0(nf(1).format(a/1e6))+' mi';
  if(a>=1e4) return s+pre+nf(0).format(a/1e3)+' mil';
  if(a>=1e3) return s+pre+sem0(nf(1).format(a/1e3))+' mil';
  return s+pre+nf(a>0&&a<10&&a%1?1:0).format(a);
}
function partes(spec){ spec=String(spec==null?'num':spec); var i=spec.indexOf(':'); return i<0?[spec,null]:[spec.slice(0,i),+spec.slice(i+1)]; }
function fmt(spec){
  if(typeof spec==='function') return spec;
  var p=partes(spec), k=p[0], d=p[1];
  function D(x){ return d==null?x:d; }
  switch(k){
    case 'brl': return function(v){ return vazio(v)?'–':(v<0?'-':'')+'R$ '+nf(D(0)).format(Math.abs(v)); };
    case 'brlc': return function(v){ return compacto(v,'R$ '); };
    case 'pct': return function(v){ return vazio(v)?'–':nf(D(1)).format(v)+'%'; };
    case 'pctf': return function(v){ return vazio(v)?'–':nf(D(1)).format(v*100)+'%'; };
    case 'varpct': return function(v){ return vazio(v)?'–':(v>0?'+':'')+nf(D(1)).format(v)+'%'; };
    case 'pp': return function(v){ return vazio(v)?'–':(v>0?'+':'')+nf(D(1)).format(v)+' p.p.'; };
    case 'numc': return function(v){ return compacto(v,''); };
    case 'mult': return function(v){ return vazio(v)?'–':nf(D(2)).format(v)+'x'; };
    case 'txt': return function(v){ return vazio(v)?'–':String(v); };
    default: return function(v){ return vazio(v)?'–':nf(D(0)).format(v); };
  }
}
function casas(v){ var a=Math.abs(+v); if(Math.abs(a-Math.round(a))<1e-9) return 0; if(Math.abs(a*10-Math.round(a*10))<1e-7) return 1; return 2; }
function eixo(spec){
  var k=partes(spec)[0];
  if(k==='brl'||k==='brlc') return function(v){ return compacto(v,'R$ '); };
  if(k==='num'||k==='numc') return function(v){ return Math.abs(v)>=1e3?compacto(v,''):nf(casas(v)).format(v); };
  if(k==='pct'||k==='varpct') return function(v){ return nf(casas(v)).format(v)+'%'; };
  if(k==='pctf') return function(v){ var x=+(v*100).toFixed(6); return nf(casas(x)).format(x)+'%'; };
  if(k==='pp') return function(v){ return nf(casas(v)).format(v)+' p.p.'; };
  if(k==='mult') return function(v){ return nf(casas(v)).format(v)+'x'; };
  return fmt(spec);
}
function valorDe(p){ var v=p.value; if(p.data&&typeof p.data==='object'&&!Array.isArray(p.data)&&p.data.value!==undefined) v=p.data.value; if(Array.isArray(v)) v=v[v.length-1]; return v; }
function rotulo(spec){ var f=fmt(spec); return function(p){ var v=(p&&typeof p==='object')?valorDe(p):p; return vazio(v)?'':f(v); }; }
function rotuloCurto(spec){ var k=partes(spec)[0]; var f=(k==='brl'||k==='brlc')?function(v){return compacto(v,'R$ ');}:(k==='num'&&partes(spec)[1]==null?function(v){return Math.abs(v)>=1e4?compacto(v,''):fmt(spec)(v);}:fmt(spec)); return function(p){ var v=valorDe(p); return vazio(v)?'':f(v); }; }
function rotuloNome(spec){ var f=rotuloCurto(spec); return function(p){ var s=f(p); return s===''?'':((p.seriesName&&p.seriesName.charAt(0)!=='_')?p.seriesName+' ':'')+s; }; }
function rotuloRosca(p){ return p.name+'\n{v|'+nf(1).format(p.percent||0)+'%}'; }
function corDe(p){ var c=p.color; if(c&&typeof c==='object') c=(c.colorStops&&c.colorStops[0]&&c.colorStops[0].color)||T.destaque; if(typeof c==='string'&&c.indexOf('rgba')===0&&/,\s*0(\.\d+)?\)$/.test(c)){ var m=/rgba\((\d+),(\d+),(\d+)/.exec(c.replace(/\s/g,'')); if(m) c='rgb('+m[1]+','+m[2]+','+m[3]+')'; } return c||T.destaque; }
function chave(cor){ return '<span style="display:inline-block;width:12px;height:0;border-top:2px solid '+cor+';flex:none"></span>'; }
function linha(cor, nome, valor){ return '<div style="display:flex;align-items:center;gap:8px;margin-top:5px">'+chave(cor)+'<b style="font-size:13px;font-weight:700;color:'+T.texto1+'">'+valor+'</b>'+(nome?'<span style="color:'+T.texto3+'">'+esc(nome)+'</span>':'')+'</div>'; }
function cab(t){ return '<div style="color:'+T.texto2+';font-size:11px;font-weight:600;letter-spacing:.02em">'+esc(t)+'</div>'; }
function nota(t, cor){ return '<div style="color:'+(cor||T.texto3)+';font-size:11px;margin-top:6px;'+(cor?'font-weight:600;':'')+'">'+esc(t)+'</div>'; }
function extras(d){ var h=''; if(d&&d.awr){ (d.awr.linhas||[]).forEach(function(l){ h+=linha('transparent', l[0], esc(l[1])); }); if(d.awr.nota) h+=nota(d.awr.nota, d.awr.nota_cor); } return h; }
function visivel(p){ return p.seriesName && p.seriesName.charAt(0)!=='_' ? p.seriesName : ''; }
function tipEixo(o){
  o=o||{};
  return function(ps){
    if(!Array.isArray(ps)) ps=[ps];
    ps=ps.filter(function(p){ return !(p.seriesName&&p.seriesName.charAt(0)==='_'&&p.seriesName!=='_serie'); });
    if(!ps.length) return '';
    var i=ps[0].dataIndex, h=cab(o.cab&&o.cab[i]!=null?o.cab[i]:ps[0].axisValueLabel), tot=0, n=0, rows=[];
    ps.forEach(function(p){
      var v=valorDe(p); if(vazio(v)) return;
      var f=fmt((o.fmts&&o.fmts[p.seriesIndex])||o.fmt);
      rows.push([+v, linha(corDe(p), visivel(p), f(v))]); tot+=+v; n++;
    });
    if(o.ordenar) rows.sort(function(a,b){ return b[0]-a[0]; });
    rows.forEach(function(r){ h+=r[1]; });
    if(o.total&&n>1) h+=linha('transparent', o.total, fmt(o.fmt)(tot));
    if(o.extras&&ps.length) h+=extras(ps[0].data);
    if(o.rodape&&o.rodape[i]) h+=nota(o.rodape[i]);
    return h;
  };
}
function tipItem(o){
  o=o||{};
  return function(p){
    var d=p.data, v=valorDe(p);
    var titulo=(d&&d.awr&&d.awr.titulo)||p.name||visivel(p);
    var nome=o.nome!=null?o.nome:(visivel(p)!==titulo?visivel(p):'');
    var h=cab(titulo)+linha(corDe(p), nome, fmt(o.fmt)(v));
    if(p.percent!=null&&o.pct!==false) h+=linha('transparent','do total', nf(1).format(p.percent)+'%');
    return h+extras(d);
  };
}
function tipDispersao(o){
  o=o||{};
  return function(p){
    var d=p.data||{}, v=(d.value||p.value||[]);
    var h=cab(d.name||p.name)+linha(corDe(p), o.nomeY||'', fmt(o.fmtY)(v[1]))+linha('transparent', o.nomeX||'', fmt(o.fmtX)(v[0]));
    if(visivel(p)) h+=nota(visivel(p));
    return h+extras(d);
  };
}
function tipCalor(o){
  o=o||{};
  return function(p){ var v=p.value||[]; return cab((o.y?o.y[v[1]]:'')+' × '+(o.x?o.x[v[0]]:''))+linha(corDe(p),'',vazio(v[2])?'–':fmt(o.fmt)(v[2])); };
}
function tipCascata(o){
  o=o||{};
  return function(ps){
    if(!Array.isArray(ps)) ps=[ps];
    var i=ps[0].dataIndex, h=cab(ps[0].axisValueLabel);
    ps.forEach(function(p){ if(p.seriesName&&p.seriesName.charAt(0)==='_') return; var v=valorDe(p); if(vazio(v)) return;
      var tot=p.seriesName==='Total', s=p.seriesName==='Baixa'?-v:v;
      h+=linha(corDe(p), tot?(o.rodape&&o.rodape[i]==='subtotal'?'subtotal':'total'):(s>=0?'entrada':'saída'), (tot?'':(s>0?'+':''))+fmt(o.fmt)(s)); });
    if(o.rodape&&o.rodape[i]==='subtotal') return h;
    if(o.rodape&&o.rodape[i]) h+=nota(o.rodape[i]);
    return h;
  };
}
// --- tooltip "so a linha do mouse": a serie mais perto do ponteiro (no Y) acende,
// as outras apagam, e o tooltip mostra so ela. Serve para linha com muitas series.
var _ativo=null, _mouse=null;
function proximo(ps){
  if(!Array.isArray(ps)) ps=[ps];
  var c=_ativo, melhor=null, dist=Infinity;
  ps.forEach(function(p){
    if(p.seriesName&&p.seriesName.charAt(0)==='_'&&p.seriesName!=='_serie') return;
    var v=valorDe(p); if(vazio(v)) return;
    var d=0;
    if(c&&_mouse){ var pt=c.convertToPixel({seriesIndex:p.seriesIndex},[p.dataIndex,+v]); d=pt?Math.abs(pt[1]-_mouse[1]):0; }
    if(d<dist){ dist=d; melhor=p; }
  });
  if(c&&melhor&&c.__awrFoco!==melhor.seriesIndex){
    var ant=c.__awrFoco, novo=melhor.seriesIndex; c.__awrFoco=novo;
    // o 'highlight' do ECharts so engrossa a linha; apagar as outras e feito aqui,
    // direto na opacidade (o blur nativo so dispara com o mouse EM CIMA da linha)
    setTimeout(function(){ if(c.__awrFoco!==novo) return; focar(c,novo);
      if(ant!=null) c.dispatchAction({type:'downplay',seriesIndex:ant});
      c.dispatchAction({type:'highlight',seriesIndex:novo}); },0);
  }
  return melhor;
}
function focar(c, idx){
  var n=c.__awrN||0, ss=[];
  for(var i=0;i<n;i++){ var a=(idx==null||i===idx)?1:0.16; ss.push({lineStyle:{opacity:a},itemStyle:{opacity:a},endLabel:{opacity:a}}); }
  if(n) c.setOption({series:ss},{lazyUpdate:true,silent:true});
}
function tipProximo(o){
  o=o||{};
  return function(ps){
    var p=proximo(ps); if(!p) return '';
    var i=p.dataIndex, f=fmt((o.fmts&&o.fmts[p.seriesIndex])||o.fmt);
    var h=cab(o.cab&&o.cab[i]!=null?o.cab[i]:p.axisValueLabel)+linha(corDe(p), visivel(p), f(valorDe(p)));
    var ex=o.extras&&o.extras[p.seriesName];
    if(ex) ex.forEach(function(l){ h+=linha('transparent', l[0], esc(l[1])); });
    if(o.rodape&&o.rodape[i]) h+=nota(o.rodape[i]);
    return h;
  };
}
function montar(el, opt){
  if(typeof el==='string') el=document.getElementById(el);
  if(!el) return null;
  var feito=false;
  function go(){
    if(feito) return; feito=true;
    var c=echarts.getInstanceByDom(el)||echarts.init(el,null,{renderer:'canvas'});
    c.setOption(opt,true);
    c.__awrN=(opt.series||[]).length;
    c.getZr().on('mousemove',function(e){ _ativo=c; _mouse=[e.offsetX,e.offsetY]; });
    c.getZr().on('globalout',function(){ if(c.__awrFoco!=null){ var f=c.__awrFoco; c.__awrFoco=null; focar(c,null); c.dispatchAction({type:'downplay',seriesIndex:f}); } });
    if(window.ResizeObserver) new ResizeObserver(function(){ c.resize(); }).observe(el);
    else window.addEventListener('resize',function(){ c.resize(); });
    el.__awr=c;
  }
  var fam=T.fonte_carregar;
  if(fam&&document.fonts&&document.fonts.load){
    Promise.all([400,500,600,700].map(function(w){ return document.fonts.load(w+' 12px "'+fam+'"'); })).then(go,go);
    setTimeout(go,1500);
  } else go();
  return el;
}
window.AWR={T:T,fmt:fmt,eixo:eixo,rotulo:rotulo,rotuloCurto:rotuloCurto,rotuloNome:rotuloNome,rotuloRosca:rotuloRosca,esc:esc,compacto:compacto,
  linha:linha,cab:cab,nota:nota,tipEixo:tipEixo,tipItem:tipItem,tipDispersao:tipDispersao,
  tipCalor:tipCalor,tipCascata:tipCascata,proximo:proximo,tipProximo:tipProximo,montar:montar};
})();
"""


def runtime_js(tema=None):
    """O JS do runtime AWR com o tema embutido (para colar num <script>)."""
    t = tema or TEMA_ESCURO
    return _RUNTIME.replace("__TEMA__", para_json(t))


def cabecalho_html(tema=None):
    """<link> da fonte + <script> do ECharts + runtime - uma vez por pagina."""
    t = tema or TEMA_ESCURO
    return (f'<link href="{t.get("fonte_css", FONTE_CSS)}" rel="stylesheet">\n'
            f'<script src="{ECHARTS_CDN}"></script>\n'
            f"<script>{runtime_js(tema)}</script>\n")


_contador = [0]


def trecho_html(option, altura=360, *, id=None, classe="grafico-awr"):
    """<div> + <script> que monta o grafico numa pagina que ja tem cabecalho_html()."""
    _contador[0] += 1
    gid = id or f"awr-g{_contador[0]}"
    return (f'<div id="{gid}" class="{classe}" style="width:100%;height:{int(altura)}px"></div>\n'
            f"<script>AWR.montar('{gid}', {para_json(option)});</script>\n")


def pagina_html(option, altura=360, tema=None):
    """Documento HTML completo com um grafico (iframe srcdoc / arquivo)."""
    t = tema or TEMA_ESCURO
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<style>html,body{{margin:0;padding:0;background:{t['fundo']};overflow:hidden}}"
        f"#g{{width:100%;height:{int(altura)}px}}</style>"
        + cabecalho_html(t) +
        "</head><body><div id=\"g\"></div>"
        f"<script>AWR.montar('g', {para_json(option)});</script>"
        "</body></html>"
    )


def salvar_html(option, caminho, altura=360, tema=None):
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(pagina_html(option, altura, tema))
    return caminho


def aviso(texto, tema=None, *, subtexto=None):
    """Option de estado vazio ('Sem dados no periodo', 'Selecione 2 fundos'...):
    texto centralizado, sem eixos. Serve em qualquer render (st_grafico, pagina_html...)."""
    t = tema or TEMA_ESCURO
    filhos = [{"type": "text", "left": "center", "top": "middle",
               "style": {"text": str(texto), "fill": t["texto2"], "font": f"500 14px {t['fonte']}",
                         "textAlign": "center"}}]
    if subtexto:
        filhos[0]["top"] = "42%"
        filhos.append({"type": "text", "left": "center", "top": "54%",
                       "style": {"text": str(subtexto), "fill": t["texto3"],
                                 "font": f"400 12px {t['fonte']}", "textAlign": "center",
                                 "lineHeight": 18}})
    opt = base(t)
    opt["graphic"] = filhos
    return opt


def pagina_aviso(texto, altura=360, tema=None, *, subtexto=None):
    """Documento HTML de estado vazio (Dash: devolva no lugar do grafico)."""
    return pagina_html(aviso(texto, tema, subtexto=subtexto), altura, tema)


def st_grafico(option, altura=360, tema=None, key=None):
    """Streamlit: desenha o grafico (iframe do components.html). `key` e aceito
    por compatibilidade e ignorado (components.html nao tem key)."""
    import streamlit.components.v1 as components
    components.html(pagina_html(option, altura, tema), height=int(altura), scrolling=False)


def dash_grafico(option, altura=360, tema=None, id=None, style=None):
    """Dash: html.Iframe com o grafico. Em callback, devolva
    pagina_html(option, altura, tema) para Output(<id>, 'srcDoc')."""
    from dash import html
    estilo = {"width": "100%", "height": f"{int(altura)}px", "border": "0", "display": "block",
              "background": "transparent"}
    estilo.update(style or {})
    kw = {"id": id} if id else {}
    return html.Iframe(srcDoc=pagina_html(option, altura, tema), style=estilo, **kw)


def dash_iframe_vazio(id, altura=360, style=None):
    """Iframe vazio para ser preenchido por callback (Output(id, 'srcDoc'))."""
    from dash import html
    estilo = {"width": "100%", "height": f"{int(altura)}px", "border": "0", "display": "block",
              "background": "transparent"}
    estilo.update(style or {})
    return html.Iframe(id=id, srcDoc="", style=estilo)


# =============================================================================
# TABELAS (Tabulator 6.3.1, MIT) - padrao aprovado em 01/10/2026
#
#   cols = [ea.coluna("nome", "Sacado", sub="cnpj", cresce=3),
#           ea.coluna("pct_pl", "% do PL", "barra", fmt="pct", limite=20, total="soma"),
#           ea.coluna("valor", "Valor", "brl", total="soma"),
#           ea.coluna("qtd", "Titulos", "num", total="soma"),
#           ea.coluna("status", "Situacao", "selo", selos={"Acima do limite": "ruim"})]
#   spec = ea.tabela(df, cols, ordem=("pct_pl", "desc"), busca="Buscar sacado ou CNPJ")
#   ea.st_tabela(spec)                         # Streamlit
#   ea.dash_tabela(spec, id=...)               # Dash (callback: ea.pagina_tabela(spec) -> srcDoc)
#
# Regras: o DADO vai cru (numero e numero, data e data) e a formatacao pt-BR e
# feita na tela - assim a ordenacao e numerica de verdade (string "R$ 9.000"
# nao ordena). Numero a direita com digitos tabulares; cabecalho fixo; busca sem
# acento; linha de total; status sempre com texto (selo), nunca so cor.
# =============================================================================
TABULATOR_JS = "https://cdnjs.cloudflare.com/ajax/libs/tabulator/6.3.1/js/tabulator.min.js"
TABULATOR_CSS = "https://cdnjs.cloudflare.com/ajax/libs/tabulator/6.3.1/css/tabulator.min.css"

_TIPOS_NUM = ("brl", "brlc", "pct", "pctf", "varpct", "pp", "num", "numc", "mult", "barra")


def coluna(campo, titulo=None, tipo="texto", *, largura=None, min_largura=None, cresce=None,
           total=None, sub=None, limite=None, escala=None, selos=None, cor_campo=None, fmt=None,
           sinal=None, ordenavel=True, fixa=False, dica=None, quebra=False, fmt_campo=None):
    """Uma coluna da tabela.
    tipo ...... 'texto' | 'data' | 'datahora' | 'selo' | 'entidade' | 'barra' | formato
                numerico ('brl', 'brl:2', 'brlc', 'pct', 'pct:2', 'pctf', 'varpct', 'pp',
                'num', 'num:2', 'numc', 'mult')
    fmt_campo . campo com o formato de CADA linha (ex. tabela com R$, % e x
                misturados): o valor continua numero e ordena certo
    sinal ..... 'inverso' = menor e melhor (positivo vermelho, negativo verde)
    min_largura padrao: calculada pelo conteudo (cabecalho, maior valor e total)
    sub ....... (texto/entidade) campo mostrado embaixo, em cinza (ex. CNPJ)
    total ..... 'soma' | 'media' | 'contagem' | texto fixo (ex. 'Total')
    barra ..... fmt= formato do numero ao lado (padrao 'pct'), limite= marca
                tracejada (acima dela a barra fica vermelha), escala= maximo da barra
    selo ...... selos={valor: 'ruim'|'atencao'|'bom'|'ok'}; o texto e o proprio valor
    entidade .. traco de cor (campo cor_campo) + nome - ex. fundo com a cor do grafico
    sinal ..... True: numero com + e verde/vermelho (padrao True para varpct/pp)
    fixa ...... congela a coluna na rolagem horizontal
    dica ...... campo com texto de tooltip ao parar o mouse na celula
    quebra .... texto longo quebra linha em vez de cortar com '...'"""
    k = str(tipo).partition(":")[0]
    c = {"campo": str(campo), "titulo": titulo if titulo is not None else str(campo), "tipo": tipo}
    for chave, val in (("largura", largura), ("min", min_largura), ("cresce", cresce),
                       ("total", total), ("sub", sub), ("limite", limite), ("escala", escala),
                       ("selos", selos), ("cor_campo", cor_campo), ("fmt", fmt), ("dica", dica),
                       ("fmt_campo", fmt_campo)):
        if val is not None:
            c[chave] = val
    c["sinal"] = ((k in ("varpct", "pp")) if sinal is None
                  else ("inverso" if sinal == "inverso" else bool(sinal)))
    c["ordenavel"] = bool(ordenavel)
    c["num"] = k in _TIPOS_NUM
    if fixa:
        c["fixa"] = True
    if quebra:
        c["quebra"] = True
    return c


def _registros(dados):
    """DataFrame / lista de dicts -> lista de dicts com valores JSON-limpos."""
    if hasattr(dados, "to_dict"):
        df = dados.reset_index(drop=True) if hasattr(dados, "reset_index") else dados
        return df.to_dict("records")
    return [dict(r) for r in (dados or [])]


def _data_iso(v):
    """Data -> 'AAAA-MM-DD' (ordena como texto; a tela mostra dd/mm/aaaa)."""
    if v is None or type(v).__name__ in ("NaTType", "NAType"):
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, str):
        return v[:10] or None
    if hasattr(v, "date") and callable(v.date):
        v = v.date()
    return v.isoformat()[:10] if hasattr(v, "isoformat") else str(v)


def _datahora_iso(v):
    """Data e hora -> 'AAAA-MM-DD HH:MM' (ordena como texto; tela: dd/mm/aaaa HH:MM)."""
    if v is None or type(v).__name__ in ("NaTType", "NAType"):
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, str):
        s = v.strip()
        for f in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
            try:
                return _dt.datetime.strptime(s, f).strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass
        return s.replace("T", " ")[:16] or None
    if isinstance(v, _dt.datetime) or hasattr(v, "to_pydatetime"):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, _dt.date):
        return v.isoformat() + " 00:00"
    return str(v)


def _largura_min(c, linhas):
    """Largura minima (px) para cabecalho, valores e total caberem sem corte."""
    k = str(c["tipo"]).partition(":")[0]
    cab = len(str(c["titulo"])) * 7.6 + 34          # maiusculas 10,5px + seta
    vals = [l.get(c["campo"]) for l in linhas[:3000]]
    vals = [v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
    px = 0
    if k == "barra":
        px = (c.get("rotulo_ch", 6)) * 7.4 + 10 + 70 + 20
    elif c.get("num"):
        textos = [formatar(v, c["tipo"]) if not isinstance(v, str) else v for v in vals]
        if c.get("total") in ("soma", "media") and vals:
            nums = [float(v) for v in vals if not isinstance(v, str)]
            if nums:
                tot = sum(nums) if c["total"] == "soma" else sum(nums) / len(nums)
                textos.append(formatar(tot, c["tipo"]))
        px = max((len(s) for s in textos), default=4) * 7.4 + (8 if c.get("sinal") else 0) + 24
    elif k == "data":
        px = 10 * 7.4 + 24
    elif k == "datahora":
        px = 16 * 7.4 + 24
    elif k == "selo":
        px = max((len(str(v)) for v in vals), default=4) * 6.8 + 46
    else:
        larg = max((len(str(v)) for v in vals), default=6)
        if c.get("sub"):
            larg = max(larg, max((len(str(l.get(c["sub"]) or "")) for l in linhas[:3000]), default=0) * 0.9)
        px = min(larg, 26) * 7.2 + 24 + (18 if k == "entidade" else 0)
        if isinstance(c.get("total"), str) and c["total"] not in ("soma", "media", "contagem"):
            px = max(px, len(c["total"]) * 7.6 + 24)
    return int(max(cab, px, 64))


def tabela(dados, colunas, *, tema=None, altura=None, max_altura=520, busca=True,
           busca_campos=None, ordem=None, destaque=None, vazio="Nenhum registro",
           layout=None, linha_classe=None, chave=None):
    """Monta a especificacao da tabela (dict) para st_tabela / dash_tabela / pagina_tabela.
    busca ......... True, False ou o placeholder (ex. 'Buscar sacado ou CNPJ')
    busca_campos .. campos em que a busca procura (padrao: texto + sub)
    ordem ......... (campo, 'asc'|'desc') ordenacao inicial
    destaque ...... (campo, valor): linha destacada em dourado (ex. o fundo AWR)
    linha_classe .. campo com 'ruim'/'atencao'/'bom' para marcar a linha na borda
    altura ........ px do iframe; None = cabe todas as linhas ate max_altura
    layout ........ 'ajustar' (colunas cabem na largura) | 'rolar' (rolagem
                    horizontal); padrao: 'ajustar' ate 8 colunas
    chave ......... nome unico: guarda a ordenacao e a busca do usuario na sessao do
                    navegador e restaura quando a tabela e redesenhada (ex. tabela que
                    se atualiza sozinha a cada 30 s)"""
    t = tema or TEMA_ESCURO
    regs = _registros(dados)
    cols = [dict(c) for c in colunas]
    campos_data = [c["campo"] for c in cols if c["tipo"] == "data"]
    campos_dh = [c["campo"] for c in cols if c["tipo"] == "datahora"]
    if busca_campos is None:
        busca_campos = [c["campo"] for c in cols if c["tipo"] in ("texto", "entidade", "selo")] + \
                       [c["sub"] for c in cols if c.get("sub")]
    # so os campos que a tabela usa vao para a pagina (menos peso no iframe)
    usados = {c["campo"] for c in cols} | {c.get("sub") for c in cols} | {c.get("cor_campo") for c in cols} \
        | {c.get("dica") for c in cols} | ({destaque[0]} if destaque else set()) | {linha_classe} \
        | {c.get("fmt_campo") for c in cols} | set(busca_campos)
    usados.discard(None)
    linhas = []
    for r in regs:
        lin = {k: v for k, v in r.items() if k in usados}
        for k in campos_data:
            lin[k] = _data_iso(r.get(k))
        for k in campos_dh:
            lin[k] = _datahora_iso(r.get(k))
        linhas.append(lin)
    for c in cols:                                   # escala e largura do rotulo da barra
        if c["tipo"] == "barra":
            vals = [float(l[c["campo"]]) for l in linhas
                    if not _vazio(l.get(c["campo"])) and not isinstance(l.get(c["campo"]), str)]
            if "escala" not in c:
                m = max(vals) if vals else 1
                c["escala"] = max(m * 1.08, float(c.get("limite") or 0) * 1.25, 1e-9)
            c["rotulo_ch"] = max([len(formatar(v, c.get("fmt", "pct"))) for v in vals] + [4])
    for c in cols:                                   # nada cortado no ajuste a largura
        if "min" not in c and "largura" not in c:
            c["min"] = _largura_min(c, linhas)
    tem_sub = any(c.get("sub") for c in cols)
    tem_total = any(c.get("total") for c in cols)
    n = len(linhas)
    alt_linha = 46 if tem_sub else 38
    barra_busca = 46 if busca else 0
    conteudo = 40 + max(n, 1) * alt_linha + (40 if tem_total else 0) + 4
    auto = altura is None and barra_busca + conteudo <= int(max_altura)
    if altura is None:
        altura = min(int(max_altura), barra_busca + conteudo)
    # cabe tudo: a tabela cresce do tamanho real (sem faixa vazia acima do total);
    # nao cabe: altura fixa com rolagem e cabecalho parado
    alt_tab = None if auto else int(altura) - barra_busca
    spec = {
        "colunas": cols, "dados": linhas, "altura": int(altura), "altura_tabela": alt_tab,
        "busca": bool(busca), "placeholder": busca if isinstance(busca, str) else "Buscar",
        "busca_campos": busca_campos, "vazio": vazio,
        "ordem": list(ordem) if ordem else None,
        "destaque": list(destaque) if destaque else None,
        "linha_classe": linha_classe,
        "chave": str(chave) if chave else None,
        "virtual": n > 150 and alt_tab is not None,
        "layout": "fitColumns" if (layout or ("ajustar" if len(cols) <= 8 else "rolar")) == "ajustar"
                  else "fitDataStretch",
        "_tema": t,
    }
    return spec


def _css_tabela(t):
    from string import Template
    sup = t["superficie"]
    return Template(r"""
html,body{margin:0;padding:0;background:$fundo;overflow:hidden;font-family:$fonte;color:$texto1}
.awr-tbar{display:flex;align-items:center;justify-content:flex-end;gap:10px;height:38px;margin:2px 6px 6px 2px}
.awr-busca{background:$campo;border:1px solid $borda;border-radius:8px;color:$texto1;font:500 12.5px $fonte;
 padding:7px 10px 7px 30px;width:240px;max-width:60%;outline:none;
 background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%2398A7C2' stroke-width='2' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cpath d='m20 20-3.5-3.5'/%3E%3C/svg%3E");
 background-repeat:no-repeat;background-position:10px center}
.awr-busca:focus{border-color:$destaque_escuro}
.awr-busca::placeholder{color:$texto3}
.awr-cont{font-size:11.5px;color:$texto3;font-variant-numeric:tabular-nums;white-space:nowrap}
.tabulator{background:transparent;border:none;font-family:$fonte;font-size:12.5px;color:$texto1}
.tabulator .tabulator-header{background:$sup;border-bottom:1px solid $borda_forte;color:$texto3}
.tabulator .tabulator-header .tabulator-col{background:$sup;border-right:none}
.tabulator .tabulator-header .tabulator-col .tabulator-col-content{padding:8px 10px}
.tabulator .tabulator-header .tabulator-col .tabulator-col-content .tabulator-col-title-holder{display:flex;align-items:center;gap:6px}
.tabulator .tabulator-header .tabulator-col.num .tabulator-col-title-holder{justify-content:flex-end}
.tabulator .tabulator-col-title{font-size:10.5px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;overflow:visible;text-overflow:clip;white-space:nowrap;padding-right:0!important}
.tabulator .tabulator-header .tabulator-col .tabulator-col-content .tabulator-col-sorter{position:static;margin:0}
.tabulator .tabulator-header .tabulator-col.tabulator-sortable:hover,
.tabulator .tabulator-header .tabulator-col.tabulator-sortable.tabulator-col-sorter-element:hover{background:$hover_cab!important;background-color:$hover_cab!important;color:$texto1}
.tabulator .tabulator-header .tabulator-col.tabulator-sortable[aria-sort=none] .tabulator-col-content .tabulator-col-sorter.tabulator-col-sorter-element .tabulator-arrow:hover{border-bottom:6px solid $texto2}
.tabulator .tabulator-header .tabulator-col.tabulator-sortable[aria-sort=ascending] .tabulator-col-content .tabulator-col-sorter.tabulator-col-sorter-element .tabulator-arrow:hover{border-bottom:6px solid $destaque}
.tabulator .tabulator-header .tabulator-col.tabulator-sortable[aria-sort=descending] .tabulator-col-content .tabulator-col-sorter.tabulator-col-sorter-element .tabulator-arrow:hover{border-top:6px solid $destaque}
.tabulator-row.tabulator-selectable:hover,.tabulator-row.tabulator-selected:hover{background-color:$hover!important}
.tabulator .tabulator-header .tabulator-col[aria-sort="ascending"],.tabulator .tabulator-header .tabulator-col[aria-sort="descending"]{color:$destaque_claro}
.tabulator .tabulator-col .tabulator-col-sorter .tabulator-arrow{border-bottom-color:$texto3}
.tabulator .tabulator-col:not([aria-sort="ascending"]):not([aria-sort="descending"]) .tabulator-arrow{opacity:0;transition:opacity .15s}
.tabulator .tabulator-col.tabulator-sortable:hover .tabulator-arrow{opacity:.7}
.tabulator .tabulator-col[aria-sort="ascending"] .tabulator-col-sorter .tabulator-arrow{border-bottom-color:$destaque}
.tabulator .tabulator-col[aria-sort="descending"] .tabulator-col-sorter .tabulator-arrow{border-top-color:$destaque;border-bottom-color:transparent}
.tabulator .tabulator-col-resize-handle{opacity:0}
.tabulator .tabulator-tableholder{background:transparent}
.tabulator .tabulator-tableholder .tabulator-table{background:transparent;color:$texto1}
.tabulator-row{background:transparent;border-bottom:1px solid $linha;min-height:36px}
.tabulator-row.tabulator-row-even{background:transparent}
.tabulator-row:hover{background:$hover!important;cursor:default}
.tabulator-row .tabulator-cell{border-right:none;padding:8px 10px;display:inline-flex;align-items:center;user-select:text}
.tabulator-row .tabulator-cell.tabulator-frozen{background:$sup}
.tabulator-row:hover .tabulator-cell.tabulator-frozen{background:$sup_hover}
.tabulator-cell.num{font-variant-numeric:tabular-nums;justify-content:flex-end;text-align:right;white-space:nowrap}
.tabulator-cell .corta{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;display:block}
.tabulator-cell.quebra{white-space:normal;line-height:1.3}
.tabulator .tabulator-footer{background:$sup;border-top:1px solid $borda_forte;color:$texto1}
.tabulator .tabulator-footer .tabulator-calcs-holder{background:$sup;border:none}
.tabulator .tabulator-footer .tabulator-calcs-holder .tabulator-row{background:$sup!important;border:none;font-weight:700}
.tabulator .tabulator-placeholder span,.tabulator .tabulator-tableholder .tabulator-placeholder .tabulator-placeholder-contents{color:$texto3!important;font-weight:500!important;font-size:13px!important;padding:18px 10px}
.tabulator .tabulator-tableholder::-webkit-scrollbar{width:8px;height:8px}
.tabulator .tabulator-tableholder::-webkit-scrollbar-thumb{background:$borda;border-radius:4px}
.tabulator .tabulator-tableholder::-webkit-scrollbar-track{background:transparent}
.awr-nm{display:flex;flex-direction:column;min-width:0;line-height:1.25}
.awr-nm b{font-weight:600;color:$texto1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.awr-nm i{font-style:normal;font-size:11px;color:$texto3;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.awr-pl{display:flex;align-items:center;gap:10px;width:100%}
.awr-trilho{position:relative;flex:1;height:6px;border-radius:3px;background:$trilho;min-width:50px}
.awr-enche{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:$destaque}
.awr-enche.ruim{background:$perigo}
.awr-marco{position:absolute;top:-4px;bottom:-4px;width:0;border-left:1.5px dashed $perigo_marco}
.awr-pl span{font-variant-numeric:tabular-nums;min-width:46px;text-align:right;font-weight:600}
.awr-selo{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:600;padding:3px 8px;border-radius:999px;white-space:nowrap;color:$texto2;background:$selo_ok}
.awr-selo:before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor;flex:none}
.awr-selo.ruim{color:$perigo_txt;background:$perigo_fundo}
.awr-selo.atencao{color:$alerta_txt;background:$alerta_fundo}
.awr-selo.bom{color:$sucesso_txt;background:$sucesso_fundo}
.awr-pos{color:$sucesso_txt}.awr-neg{color:$perigo_txt}.awr-nulo{color:$texto3}
.awr-ent{display:flex;align-items:center;gap:8px;min-width:0}
.awr-ent .k{width:10px;height:3px;border-radius:2px;flex:none}
.awr-ent .awr-nm b{font-weight:500}
.tabulator-row .tabulator-cell.tabulator-frozen.tabulator-frozen-left{border-right:1px solid $borda}
.tabulator-row.awr-destaque{background:$destaque_fundo!important}
.tabulator-row.awr-destaque .tabulator-cell.tabulator-frozen{background:$sup_hover}
.tabulator-row.awr-destaque > .tabulator-cell:first-child{box-shadow:inset 3px 0 0 $destaque}
.tabulator-row.awr-destaque .awr-nm b,.tabulator-row.awr-destaque .awr-ent b{font-weight:700;color:$destaque_claro}
.tabulator-row.awr-linha-ruim > .tabulator-cell:first-child{box-shadow:inset 3px 0 0 $perigo}
.tabulator-row.awr-linha-atencao > .tabulator-cell:first-child{box-shadow:inset 3px 0 0 $alerta}
.tabulator-row.awr-linha-bom > .tabulator-cell:first-child{box-shadow:inset 3px 0 0 $sucesso}
""").safe_substitute(
        fundo=t["fundo"], fonte=t["fonte"], texto1=t["texto1"], texto2=t["texto2"], texto3=t["texto3"],
        sup=sup, sup_hover=_misturar(sup, t["destaque"], 0.06),
        campo=_misturar(sup, "#000000", 0.25) if t["nome"] == "escuro" else "#FFFFFF",
        borda=_hex_mpl(t["tooltip_borda"]) if t["nome"] == "escuro" else "#D8DEE8",
        borda_forte=t["etiqueta_fundo"] if t["nome"] == "escuro" else "#CBD5E1",
        linha=_rgba(t["texto3"], 0.14) if t["texto3"].startswith("#") else t["grade"],
        hover=_rgba(t["destaque"], 0.06), hover_cab=_misturar(sup, "#FFFFFF", 0.04),
        trilho=_rgba(t["texto3"], 0.16) if t["texto3"].startswith("#") else t["grade"],
        destaque=t["destaque"], destaque_claro=t["destaque_claro"], destaque_escuro=t["destaque_escuro"],
        destaque_fundo=_rgba(t["destaque"], 0.08),
        perigo=t["perigo"], perigo_marco=_rgba(t["perigo"], 0.7),
        perigo_txt=_misturar(t["perigo"], "#FFFFFF", 0.35) if t["nome"] == "escuro" else t["perigo"],
        perigo_fundo=_rgba(t["perigo"], 0.13),
        alerta=t["alerta"],
        alerta_txt=_misturar(t["alerta"], "#FFFFFF", 0.3) if t["nome"] == "escuro" else "#9A6700",
        alerta_fundo=_rgba(t["alerta"], 0.13),
        sucesso=t["sucesso"],
        sucesso_txt=_misturar(t["sucesso"], "#FFFFFF", 0.25) if t["nome"] == "escuro" else t["sucesso"],
        sucesso_fundo=_rgba(t["sucesso"], 0.13),
        selo_ok=_rgba(t["texto3"], 0.12) if t["texto3"].startswith("#") else t["grade"],
    )


def _misturar(a, b, f):
    """Cor a misturada com b na fracao f (0..1)."""
    ra, rb = _hex_rgb(a), _hex_rgb(b)
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * f) for x, y in zip(ra, rb))


_RUNTIME_TABELA = r"""
(function(){
var A=window.AWR, T=A.T;
function sem(s){ return String(s==null?'':s).normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase(); }
function nulo(){ return '<span class="awr-nulo">–</span>'; }
function vazio(v){ return v===null||v===undefined||v===''||(typeof v==='number'&&!isFinite(v)); }
function dataBR(v){ if(vazio(v)) return nulo(); var m=/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(String(v));
  return m?m[3]+'/'+m[2]+'/'+m[1]+(m[4]?' '+m[4]+':'+m[5]:''):A.esc(v); }
function numFmt(c){ var base=c.tipo==='barra'?(c.fmt||'pct'):c.tipo, f0=A.fmt(base), cache={};
  return function(v, d){ if(vazio(v)) return nulo(); if(typeof v==='string') return A.esc(v);
    var f=f0; if(c.fmt_campo&&d&&d[c.fmt_campo]){ var sp=d[c.fmt_campo]; f=cache[sp]||(cache[sp]=A.fmt(sp)); }
    var s=f(v); if(c.sinal){ if(!/^[+-]/.test(s)&&v>0) s='+'+s; var bom=c.sinal==='inverso'?v<0:v>0, ruim=c.sinal==='inverso'?v>0:v<0;
      return '<span class="'+(bom?'awr-pos':(ruim?'awr-neg':''))+'">'+s+'</span>'; } return s; }; }
function formatador(c){
  if(c.tipo==='data'||c.tipo==='datahora') return function(cell){ return dataBR(cell.getValue()); };
  if(c.tipo==='selo') return function(cell){ var v=cell.getValue(); if(vazio(v)) return nulo(); var k=(c.selos&&c.selos[v])||'ok'; return '<span class="awr-selo '+k+'">'+A.esc(v)+'</span>'; };
  if(c.tipo==='barra'){ var f=numFmt(c); return function(cell){ var v=cell.getValue(); if(vazio(v)||typeof v==='string') return f(v);
      var esc=c.escala||1, ruim=(c.limite!=null&&v>c.limite);
      var h='<div class="awr-pl"><div class="awr-trilho"><div class="awr-enche'+(ruim?' ruim':'')+'" style="width:'+Math.max(0,Math.min(100,v/esc*100))+'%"></div>';
      if(c.limite!=null) h+='<div class="awr-marco" style="left:'+Math.min(100,c.limite/esc*100)+'%"></div>';
      return h+'</div><span style="min-width:'+(c.rotulo_ch||6)+'ch">'+A.fmt(c.fmt||'pct')(v)+'</span></div>'; }; }
  if(c.num) return (function(f){ return function(cell){ return f(cell.getValue(), cell.getData()); }; })(numFmt(c));
  return function(cell){ var d=cell.getData(), v=cell.getValue(), txt=vazio(v)?'':A.esc(v);
    var dica=c.dica&&d[c.dica]?' title="'+A.esc(d[c.dica])+'"':(txt?' title="'+txt+'"':'');
    var corpo;
    if(c.sub) corpo='<div class="awr-nm"><b'+dica+'>'+(txt||'–')+'</b><i>'+(vazio(d[c.sub])?'':A.esc(d[c.sub]))+'</i></div>';
    else if(c.quebra) corpo=txt||nulo();
    else corpo='<span class="corta"'+dica+'>'+(txt||'–')+'</span>';
    if(c.tipo==='entidade'){ var cor=(c.cor_campo&&d[c.cor_campo])||T.outros;
      if(!c.sub) corpo='<div class="awr-nm"><b'+dica+'>'+(txt||'–')+'</b></div>';
      return '<div class="awr-ent"><span class="k" style="background:'+A.esc(cor)+'"></span>'+corpo+'</div>'; }
    return corpo; };
}
function ordenador(c){
  if(c.num) return function(a,b){ var x=vazio(a)||typeof a==='string'?-Infinity:+a, y=vazio(b)||typeof b==='string'?-Infinity:+b; return x-y; };
  return function(a,b){ return String(a==null?'':a).localeCompare(String(b==null?'':b),'pt-BR',{sensitivity:'base',numeric:true}); };
}
function totalCalc(c){
  if(!c.total) return undefined;
  if(c.total==='soma') return 'sum'; if(c.total==='media') return 'avg'; if(c.total==='contagem') return 'count';
  var txt=String(c.total); return function(){ return txt; };
}
function totalFmt(c){
  if(!c.total) return undefined;
  if(c.total==='contagem') return function(cell){ return A.fmt('num')(cell.getValue()); };
  if(c.total==='soma'||c.total==='media'){ var f=A.fmt(c.tipo==='barra'?(c.fmt||'pct'):c.tipo), barra=c.tipo==='barra';
    return function(cell){ var v=cell.getValue(); if(vazio(v)) return ''; var s=f(+v);
      return barra?'<span style="margin-left:auto;font-variant-numeric:tabular-nums">'+s+'</span>':s; }; }
  return function(cell){ return '<span class="corta">'+A.esc(cell.getValue())+'</span>'; };
}
function coluna(c){
  var o={title:c.titulo, field:c.campo, formatter:formatador(c), sorter:ordenador(c),
         headerSort:c.ordenavel!==false, headerSortStartingDir:c.num?'desc':'asc', resizable:true,
         minWidth:c.min||(c.num?Math.max(76, String(c.titulo).length*8+34):90)};
  if(c.num){ o.cssClass='num'; o.hozAlign='right'; o.headerHozAlign='right'; }
  if(c.tipo==='barra'){ o.cssClass=''; o.hozAlign='left'; o.headerHozAlign='left'; o.minWidth=c.min||150; }
  if(c.quebra) o.cssClass=(o.cssClass?o.cssClass+' ':'')+'quebra';
  if(c.largura) o.width=c.largura;
  if(c.cresce) o.widthGrow=c.cresce;
  if(c.fixa) o.frozen=true;
  var bc=totalCalc(c); if(bc){ o.bottomCalc=bc; o.bottomCalcFormatter=totalFmt(c);
    if(bc==='avg') o.bottomCalcParams={precision:false}; }   // media sem arredondar em 2 casas
  return o;
}
function guardar(chave){
  var k='awr_tab_'+chave, s=null;
  try{ s=JSON.parse(window.sessionStorage.getItem(k)||'null'); }catch(e){ s=null; }
  return { lido:s||{}, salvar:function(o){ try{ var a=JSON.parse(window.sessionStorage.getItem(k)||'{}'); for(var x in o) a[x]=o[x]; window.sessionStorage.setItem(k, JSON.stringify(a)); }catch(e){} } };
}
function tabela(el, spec){
  if(typeof el==='string') el=document.getElementById(el);
  var inp=null, cont=null, total=spec.dados.length;
  if(spec.busca){
    var bar=document.createElement('div'); bar.className='awr-tbar';
    inp=document.createElement('input'); inp.className='awr-busca'; inp.type='search';
    inp.placeholder=spec.placeholder||'Buscar'; inp.setAttribute('aria-label',inp.placeholder);
    cont=document.createElement('span'); cont.className='awr-cont';
    bar.appendChild(inp); bar.appendChild(cont); el.appendChild(bar);
  }
  var box=document.createElement('div'); el.appendChild(box);
  var cols=spec.colunas.map(coluna);
  if(!total) cols.forEach(function(o){ delete o.bottomCalc; delete o.bottomCalcFormatter; });  // vazia: sem linha de total
  var mem=spec.chave?guardar(spec.chave):null;
  var opts={data:spec.dados, columns:cols, layout:spec.layout||'fitColumns',
    renderVertical:spec.virtual?'virtual':'basic',
    placeholder:spec.vazio||'Nenhum registro', columnHeaderVertAlign:'middle',
    rowFormatter:function(row){ var d=row.getData(), e=row.getElement();
      if(spec.destaque&&d[spec.destaque[0]]===spec.destaque[1]) e.classList.add('awr-destaque');
      if(spec.linha_classe&&d[spec.linha_classe]) e.classList.add('awr-linha-'+d[spec.linha_classe]); }};
  if(spec.altura_tabela) opts.height=spec.altura_tabela;     // sem altura = cresce do tamanho real
  if(spec.ordem) opts.initialSort=[{column:spec.ordem[0], dir:spec.ordem[1]||'asc'}];
  if(mem&&mem.lido.ordem&&mem.lido.ordem.length) opts.initialSort=mem.lido.ordem;
  var tab=new Tabulator(box, opts);
  if(mem) tab.on('dataSorted',function(sorters){ mem.salvar({ordem:sorters.map(function(s){ return {column:s.field, dir:s.dir}; })}); });
  if(inp){
    var campos=spec.busca_campos||[];
    var conta=function(n){ cont.textContent=(n==null?total:n)+' de '+total; };
    var filtrar=function(){ var q=sem(inp.value.trim()); if(mem) mem.salvar({busca:inp.value});
      if(!q) tab.clearFilter(); else tab.setFilter(function(d){ for(var i=0;i<campos.length;i++){ if(sem(d[campos[i]]).indexOf(q)>=0) return true; } return false; }); };
    inp.addEventListener('input',filtrar);
    tab.on('dataFiltered',function(f,rows){ conta(rows.length); });
    tab.on('tableBuilt',function(){ conta(total); if(mem&&mem.lido.busca){ inp.value=mem.lido.busca; filtrar(); } });
  }
  el.__awrTabela=tab;
  return tab;
}
function montarTabela(el, spec){
  var feito=false; function go(){ if(feito) return; feito=true; tabela(el, spec); }
  var fam=T.fonte_carregar;
  if(fam&&document.fonts&&document.fonts.load){
    Promise.all([400,500,600,700].map(function(w){ return document.fonts.load(w+' 12px "'+fam+'"'); })).then(go,go);
    setTimeout(go,1500);
  } else go();
}
A.tabela=montarTabela;
})();
"""


def pagina_tabela(spec, tema=None):
    """Documento HTML completo com a tabela (iframe srcdoc / arquivo)."""
    t = tema or spec.get("_tema") or TEMA_ESCURO
    corpo = {k: v for k, v in spec.items() if not k.startswith("_")}
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f'<link href="{t.get("fonte_css", FONTE_CSS)}" rel="stylesheet">'
        f'<link href="{TABULATOR_CSS}" rel="stylesheet">'
        f"<style>{_css_tabela(t)}</style>"
        f'<script src="{TABULATOR_JS}"></script>'
        f"<script>{runtime_js(t)}</script><script>{_RUNTIME_TABELA}</script>"
        f"</head><body><div id=\"t\" style=\"height:{int(spec['altura'])}px\"></div>"
        f"<script>AWR.tabela('t', {para_json(corpo)});</script>"
        "</body></html>"
    )


def st_tabela(spec, tema=None, key=None):
    """Streamlit: desenha a tabela (iframe do components.html). Substitui st.dataframe
    de leitura. `key` aceito e ignorado. Edicao (st.data_editor) continua no Streamlit."""
    import streamlit.components.v1 as components
    components.html(pagina_tabela(spec, tema), height=int(spec["altura"]), scrolling=False)


def dash_tabela(spec, tema=None, id=None, style=None):
    """Dash: html.Iframe com a tabela. Em callback, devolva pagina_tabela(spec)
    para Output(<id>, 'srcDoc') de um dash_iframe_vazio(id, altura)."""
    from dash import html
    estilo = {"width": "100%", "height": f"{int(spec['altura'])}px", "border": "0", "display": "block",
              "background": "transparent"}
    estilo.update(style or {})
    kw = {"id": id} if id else {}
    return html.Iframe(srcDoc=pagina_tabela(spec, tema), style=estilo, **kw)


# =============================================================================
# MATPLOTLIB (PDF / PNG / e-mail) - o MESMO visual, sem interacao (vira imagem)
#
#   with plt.rc_context(ea.mpl_estilo()):          # TEMA_CLARO por padrao (papel)
#       fig, ax = plt.subplots(figsize=(9, 4))
#       ax.plot(x, y, color=ea.mpl_cor("destaque"))
#       ea.mpl_eixo_fmt(ax, "brl")                  # R$ 300 mil, R$ 1,2 mi ...
#       ea.mpl_rotulo_final(ax, x, y, "brl")        # valor escrito na ponta da linha
#       ea.mpl_rotular_barras(ax, barras, "brl")    # valor na ponta de cada barra
#
# Regras iguais as do ECharts: grade em hairline so no eixo de valor, sem
# moldura, sem eixo duplo, rotulo seletivo, legenda sem caixa, titulo a esquerda.
# =============================================================================
def _hex_mpl(c):
    """'rgba(r,g,b,a)' -> '#RRGGBBAA' (matplotlib nao le rgba())."""
    c = str(c).strip()
    if c.startswith("rgba(") or c.startswith("rgb("):
        partes = [p.strip() for p in c[c.index("(") + 1:c.index(")")].split(",")]
        r, g, b = (int(float(p)) for p in partes[:3])
        a = float(partes[3]) if len(partes) > 3 else 1.0
        return "#%02X%02X%02X%02X" % (r, g, b, round(a * 255))
    return c


def _familia_mpl():
    try:
        from matplotlib import font_manager as fm
        nomes = {f.name for f in fm.fontManager.ttflist}
    except Exception:
        return ["DejaVu Sans"]
    for fam in ("Manrope", "Segoe UI", "Inter", "Arial", "DejaVu Sans"):
        if fam in nomes:
            return [fam, "DejaVu Sans"]
    return ["DejaVu Sans"]


def mpl_estilo(tema=None, *, tamanho=9.5):
    """rcParams do padrao AWR para usar em plt.rc_context(...)."""
    from cycler import cycler
    t = tema or TEMA_CLARO
    sup = t["superficie"] if t["fundo"] == "transparent" else t["fundo"]
    return {
        "font.family": _familia_mpl(), "font.size": tamanho,
        "text.color": t["texto1"], "axes.labelcolor": t["texto2"], "axes.titlecolor": t["texto1"],
        "axes.titlesize": tamanho + 2, "axes.titleweight": "semibold", "axes.titlelocation": "left",
        "axes.titlepad": 12, "axes.labelsize": tamanho - 0.5,
        "axes.facecolor": sup, "figure.facecolor": sup, "savefig.facecolor": sup,
        "axes.edgecolor": _hex_mpl(t["eixo"]), "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
        "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True,
        "grid.color": _hex_mpl(t["grade"]), "grid.linewidth": 0.7, "grid.linestyle": "-",
        "xtick.color": t["texto3"], "ytick.color": t["texto3"],
        "xtick.labelsize": tamanho - 1, "ytick.labelsize": tamanho - 1,
        "xtick.major.size": 0, "ytick.major.size": 0, "xtick.major.pad": 6, "ytick.major.pad": 6,
        "axes.prop_cycle": cycler(color=list(t["categorias"])),
        "lines.linewidth": 2.0, "lines.solid_capstyle": "round", "lines.markersize": 5,
        "patch.linewidth": 0, "legend.frameon": False, "legend.fontsize": tamanho - 1,
        "legend.labelcolor": t["texto2"], "legend.handlelength": 1.4, "legend.borderaxespad": 0.2,
        "figure.dpi": 110, "savefig.dpi": 180, "savefig.bbox": "tight",
    }


def mpl_cor(chave="destaque", tema=None):
    """Cor do tema para matplotlib: mpl_cor('destaque'), mpl_cor('perigo'), mpl_cor(2) = 3a categoria."""
    t = tema or TEMA_CLARO
    if isinstance(chave, int):
        return _hex_mpl(cor_categoria(chave, t))
    return _hex_mpl(t[chave])


def formatar_eixo(v, spec="num"):
    """Rotulo de eixo compacto (mesma regra do AWR.eixo no JS)."""
    k = str(spec).partition(":")[0]

    def _cas(x):
        a = abs(x)
        if abs(a - round(a)) < 1e-9:
            return 0
        return 1 if abs(a * 10 - round(a * 10)) < 1e-7 else 2
    if _vazio(v):
        return ""
    if k in ("brl", "brlc"):
        return compacto(v, "R$ ")
    if k in ("num", "numc"):
        return compacto(v) if abs(v) >= 1e3 else num(v, _cas(v))
    if k in ("pct", "varpct"):
        return pct(v, _cas(v))
    if k == "pctf":
        x = round(v * 100, 6)
        return pct(x, _cas(x))
    if k == "pp":
        return _br(v, _cas(v)) + " p.p."
    if k == "mult":
        return num(v, _cas(v)) + "x"
    return formatar(v, spec)


def mpl_eixo_fmt(ax, spec="num", eixo="y"):
    """Formata os ticks do eixo em pt-BR compacto (R$ 1,2 mi / 12% / 1.234)."""
    from matplotlib.ticker import FuncFormatter
    f = FuncFormatter(lambda v, _pos: formatar_eixo(v, spec))
    (ax.yaxis if eixo == "y" else ax.xaxis).set_major_formatter(f)


def mpl_rotulo_final(ax, x, y, spec="num", *, texto=None, cor=None, tema=None, dx=6):
    """Escreve o ultimo valor na ponta da linha (texto na cor de texto, nao da serie)."""
    t = tema or TEMA_CLARO
    xs, ys = list(x), list(y)
    for i in range(len(ys) - 1, -1, -1):
        if not _vazio(ys[i]):
            rot = texto if texto is not None else (compacto(ys[i], "R$ ") if str(spec).startswith("brl")
                                                   else formatar(ys[i], spec))
            ax.annotate(rot, (xs[i], ys[i]), xytext=(dx, 0), textcoords="offset points",
                        va="center", ha="left", fontsize=9, fontweight="bold",
                        color=cor or t["texto1"], annotation_clip=False)
            ax.plot([xs[i]], [ys[i]], "o", ms=5, color=ax.lines[-1].get_color() if ax.lines else t["destaque"],
                    mec=_hex_mpl(t["superficie"]), mew=1.5, zorder=5)
            return


def mpl_rotular_barras(ax, barras, spec="num", *, tema=None, horizontal=False, tamanho=8.5, cor=None):
    """Valor na ponta de cada barra (negativa: do outro lado). `barras` = retorno de ax.bar/ax.barh."""
    t = tema or TEMA_CLARO
    for b in barras:
        if horizontal:
            v = b.get_width()
            x = b.get_x() + v
            ax.annotate(formatar(v, spec), (x, b.get_y() + b.get_height() / 2),
                        xytext=(4 if v >= 0 else -4, 0), textcoords="offset points",
                        ha="left" if v >= 0 else "right", va="center", fontsize=tamanho,
                        color=cor or t["texto2"], annotation_clip=False)
        else:
            v = b.get_height()
            y = b.get_y() + v
            ax.annotate(formatar(v, spec), (b.get_x() + b.get_width() / 2, y),
                        xytext=(0, 3 if v >= 0 else -3), textcoords="offset points",
                        ha="center", va="bottom" if v >= 0 else "top", fontsize=tamanho,
                        color=cor or t["texto2"], annotation_clip=False)


def mpl_legenda(ax, **kw):
    """Legenda sem caixa, em cima a esquerda, fora da area de plot."""
    op = {"loc": "lower left", "bbox_to_anchor": (0, 1.0), "ncol": 6, "frameon": False,
          "handlelength": 1.4, "columnspacing": 1.4}
    op.update(kw)
    return ax.legend(**op)
