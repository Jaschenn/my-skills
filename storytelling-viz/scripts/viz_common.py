"""storytelling-viz low-level module: fonts & language, palette, theme, number / CJK text
helpers, rich text, panels, page composition (figure / build_slide), export (svg / pdf / png)
and automatic layout QA. High-level, data-driven chart functions live in charts.py.

Import side effects (intentional): picks a CJK and a Latin font, prints them, sets matplotlib
font rcParams (and pdf.fonttype = 42 so PDFs embed TrueType fonts, as journals require).
"""
import re

import matplotlib as mpl
from plotnine import (
    theme, theme_minimal, element_text, element_line, element_blank, element_rect,
)

# ====================================================================== fonts & language
# CJK: Simplified-Chinese first. On Linux matplotlib registers only the FIRST face of a .ttc
# collection, so "Noto Sans CJK" often shows up as "Noto Sans CJK JP" (late fallback).
CJK_FONTS = [
    "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC",
    "Source Han Sans SC", "Noto Sans SC", "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
    "Noto Sans CJK JP", "Source Han Sans", "Arial Unicode MS",
]
FONTS = CJK_FONTS                      # back-compat name
LATIN_FONTS = [
    "Inter", "Helvetica Neue", "Helvetica", "Arial", "Source Sans 3", "Source Sans Pro",
    "Roboto", "Liberation Sans", "DejaVu Sans",
]
_CJK_HINTS = ("CJK", "Hei", "YaHei", "PingFang", "Han Sans", "Song", "Ming", "Kai")


def _installed():
    from matplotlib import font_manager as fm
    return {f.name for f in fm.fontManager.ttflist}


def pick_font() -> str:
    """Return the first CJK-capable font matplotlib can actually find (by name)."""
    installed = _installed()
    for name in CJK_FONTS:
        if name in installed:
            if not name.endswith(("SC", "GB", "YaHei", "Hei")) and "PingFang" not in name:
                print(f"NOTE: using {name}; a few characters may show non-Simplified glyph "
                      "shapes. Install a Simplified-Chinese font (e.g. Noto Sans SC) if it matters.")
            return name
    cands = sorted(n for n in installed if any(k in n for k in _CJK_HINTS))
    cands.sort(key=lambda n: ("Serif" in n or "Song" in n or "Ming" in n, n))  # prefer sans
    if cands:
        return cands[0]
    print("WARNING: no CJK font found; Chinese will render as boxes. "
          "Install e.g. Noto Sans SC / Noto Sans CJK SC, or edit CJK_FONTS.")
    return "DejaVu Sans"


def pick_latin_font() -> str:
    installed = _installed()
    return next((n for n in LATIN_FONTS if n in installed), "DejaVu Sans")


FONT_CJK = pick_font()
FONT_LATIN = pick_latin_font()
LANG = "zh"
FONT = FONT_CJK                        # default text font for the current language


def _apply_rc():
    mpl.rcParams["font.sans-serif"] = [FONT, FONT_CJK, FONT_LATIN, "DejaVu Sans"]
    mpl.rcParams["font.family"] = [FONT]
    mpl.rcParams["axes.unicode_minus"] = False
    mpl.rcParams["svg.fonttype"] = "path"   # outlined glyphs by default; _editable.svg uses "none"
    mpl.rcParams["pdf.fonttype"] = 42       # embed TrueType (no Type 3 fonts: journals reject them)
    mpl.rcParams["ps.fonttype"] = 42


def set_lang(lang: str = "zh", latin: str | None = None, cjk: str | None = None):
    """Language of the figure text: 'zh' (default) or 'en'.
    Affects the default font, month labels and the default "Other" label. Amounts stay in
    K / M / B in both languages (house style); use set_number_style("cn") for 万 / 亿. Text containing CJK characters always uses the CJK font, so a
    mixed label (e.g. a Chinese city name in an English chart) still renders.
    latin / cjk: override the font family names."""
    global LANG, FONT, FONT_LATIN, FONT_CJK
    if lang not in ("zh", "en"):
        raise ValueError("lang must be 'zh' or 'en'")
    FONT_LATIN = latin or FONT_LATIN
    FONT_CJK = cjk or FONT_CJK
    LANG = lang
    FONT = FONT_CJK if lang == "zh" else FONT_LATIN
    _apply_rc()


_NEEDS_CJK_FONT = re.compile(r"[\u2190-\u21ff\u2460-\u27bf\u2e80-\u9fff\uf900-\uffef]")


def font_for(text) -> str:
    """Font family for one string: the CJK font if it contains CJK characters or symbols
    Latin fonts often lack (●○■▲→①…), else FONT."""
    return FONT_CJK if (text and _NEEDS_CJK_FONT.search(str(text))) else FONT


def T(zh_text: str, en_text: str) -> str:
    """Pick the string for the current language: T("其他", "Other")."""
    return zh_text if LANG == "zh" else en_text


import logging as _logging
_logging.getLogger("matplotlib.font_manager").setLevel(_logging.ERROR)   # "findfont: weight 600" noise
print("using fonts:", FONT_CJK, "(CJK) /", FONT_LATIN, "(Latin)")
_apply_rc()

INK = "#1f2937"      # primary text
MUTED = "#6b7280"    # secondary text (also the lightest allowed for de-emphasised TEXT, 4.8:1)
GRID = "#e5e7eb"     # hairlines


# ====================================================================== palette
def mix(c1: str, c2: str, t: float) -> str:
    """Linear blend of two hex colours: t=0 -> c1, t=1 -> c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _lum(c):
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda x: x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(c1: str, c2: str = "#ffffff") -> float:
    """WCAG contrast ratio between two hex colours (1 … 21)."""
    a, b = sorted((_lum(c1), _lum(c2)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def readable(color: str, bg: str = "#ffffff", target: float = 4.5) -> str:
    """Darken `color` just enough to reach `target` contrast on `bg` (keeps the hue).
    Use for text that should share a mark's colour (focus orange is ~3:1 on white)."""
    if not (isinstance(color, str) and color.startswith("#") and len(color) == 7):
        return color
    c, t = color, 0.0
    while contrast(c, bg) < target and t < 1.0:
        t += 0.05
        c = mix(color, "#000000", t)
    return c


def ink_on(fill: str) -> str:
    """Readable text colour on a filled background: white on dark fills, INK on light."""
    return "#ffffff" if contrast("#ffffff", fill) >= contrast(INK, fill) else INK


_WARNED = set()


def check_contrast(color, size=12, bold=False, label="", bg="#ffffff"):
    """Warn once per colour when text would be hard to read on `bg` (WCAG: 4.5:1 for normal
    text, 3:1 for large/bold text). White/near-white text is assumed to sit on a fill."""
    if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
        return
    if _lum(color) > 0.8:
        return
    need = 3.0 if (size >= 14 or (bold and size >= 11)) else 4.5
    r = contrast(color, bg)
    if r < need and color not in _WARNED:
        _WARNED.add(color)
        print(f"WARNING contrast: text colour {color} on {bg} is {r:.1f}:1 (< {need}:1), "
              f"e.g. '{str(label)[:20]}'. Use a darker colour (MUTED or darker) for text.")


class _Palette:
    """Three tiers + semantic colours. Mutate via set_palette(); read as PAL.focus etc.

    focus    - the ONE thing to look at (attention colour, carries no good/bad meaning)
    brand    - base hue of the deck (normal series, "current period")
    support  - tint of brand: ordinary data that should stay visible
    context  - very light tint: comparison/history, reference bands
    good/bad - ONLY when direction has business meaning (red = bad, green = good).
               Never rely on red/green alone: pair with sign / arrow / words (colour-blind).
    """
    def __init__(self):
        self.set(None, None)

    def set(self, brand=None, focus=None):
        if brand and not focus:           # user brand colour becomes the attention colour;
            self.brand = "#475569"        # the deck's base hue stays a neutral slate
            self.focus = brand
        else:
            self.brand = brand or "#2b5c8a"
            self.focus = focus or "#e07b39"
        self.support = mix(self.brand, "#ffffff", 0.45)
        self.context = mix(self.brand, "#ffffff", 0.80)
        self.good, self.bad = "#2e9e6b", "#c8382f"

    def categorical(self, n: int):
        """Muted categorical colours (n <= 5). First = brand, second = focus."""
        base = [self.brand, self.focus, "#4a9a9a", "#8e7cc3", self.support]
        if n > len(base):
            raise ValueError(f"categorical({n}): at most {len(base)} categories. Merge the "
                             "small ones into '其他', or facet / rank instead of colouring.")
        return base[:n]

    def sequential(self, n: int, color=None):
        """n tints from light to full `color` (default brand), for intensity."""
        c = color or self.brand
        return [mix("#ffffff", c, 0.25 + 0.75 * i / max(n - 1, 1)) for i in range(n)]


PAL = _Palette()


def set_palette(brand: str | None = None, focus: str | None = None):
    """Let the user choose brand colours. Only `brand` given -> it becomes the focus colour
    on a neutral slate base. Both given -> brand = base hue, focus = attention colour."""
    PAL.set(brand, focus)


# ====================================================================== theme
def theme_story(base: int = 12, panel: bool = False):
    """Quiet theme: no legend, no vertical grid, no axis clutter, left-aligned title.

    panel=True: this plot is one panel inside a slide; its title is a small panel label.
    """
    title_size = base + 1 if panel else base + 5
    return theme_minimal(base_size=base, base_family=FONT) + theme(
        plot_title_position="plot",
        plot_title=element_text(size=title_size, weight="bold", color=INK, ha="left",
                                margin={"b": 10}),
        plot_subtitle=element_text(size=base, color=MUTED, ha="left", margin={"b": 12}),
        plot_caption=element_text(size=base - 3, color=MUTED, ha="left"),
        axis_title=element_blank(),
        axis_text=element_text(size=base - 1, color=MUTED),
        axis_ticks=element_blank(),
        panel_grid_major_x=element_blank(),
        panel_grid_minor=element_blank(),
        panel_grid_major_y=element_line(color=GRID, size=0.5),
        legend_position="none",
        **({"plot_margin": 0} if panel else {}),
        plot_background=element_rect(fill="white", color="white"),
        panel_background=element_rect(fill="white", color="white"),
    )


# ====================================================================== numbers
def _signed(s: str, v: float, signed: bool) -> str:
    if signed and v > 0:
        s = "+" + s
    return "−" + s[1:] if s.startswith("-") else s    # true minus sign (leading only)


def pct(v: float, signed: bool = False, nd: int = 1) -> str:
    """Ratio -> percent text with a true minus sign. 0.153 -> '15.3%'.
    signed=True adds '+' for positives; values that round to 0 get no sign.
    Always build titles/labels from data with this (never hand-type numbers)."""
    r = round(v * 100, nd) + 0.0          # + 0.0 turns -0.0 into 0.0
    return _signed(f"{r:.{nd}f}%", r, signed)


def pp(delta: float, signed: bool = True, nd: int = 1) -> str:
    """Difference of two ratios -> percentage points. 0.021 -> '+2.1pp'."""
    r = round(delta * 100, nd) + 0.0
    return _signed(f"{r:.{nd}f}pp", r, signed)


NUM_STYLE = "kmb"      # house style: amounts in K / M / B in every language


def set_number_style(style: str = "kmb"):
    """'kmb' (default house style: 71.6M, 1.2B) or 'cn' (万 / 亿)."""
    global NUM_STYLE
    if style not in ("kmb", "cn"):
        raise ValueError("style must be 'kmb' or 'cn'")
    NUM_STYLE = style


def num(v: float, unit: str | None = "auto", nd: int = 1, signed: bool = False,
        style: str | None = None) -> str:
    """Compact magnitude. style: 'kmb' (default, set_number_style) -> >=1e9 B, >=1e6 M,
    >=1e4 K;  'cn' -> >=1e8 亿, >=1e4 万. Force a unit with unit='亿'/'万'/'B'/'M'/'K';
    unit=None -> thousands separators only. num(123456789) -> '123.5M'; num(1234, None) -> '1,234'."""
    style = style or NUM_STYLE
    style = "en" if style in ("en", "kmb") else "zh"
    a = abs(v)
    if unit == "auto":
        if style == "en":
            unit = "B" if a >= 1e9 else "M" if a >= 1e6 else "K" if a >= 1e4 else None
        else:
            unit = "亿" if a >= 1e8 else "万" if a >= 1e4 else None
    div = {"亿": 1e8, "万": 1e4, "B": 1e9, "M": 1e6, "K": 1e3}.get(unit)
    if div:
        r = round(v / div, nd) + 0.0
        s = f"{r:,.{nd}f}{unit}"
    else:
        r = round(v, nd if a < 100 else 0) + 0.0
        s = f"{r:,.{nd}f}" if a < 100 and r != int(r) else f"{r:,.0f}"
    return _signed(s, r, signed)


def fmt_value(v, fmt="num", nd=None):
    """Format one value for a label. fmt: 'num' | 'pct' | 'pp' | 'int' | 'raw' | a format
    string like '{:.2f}' | a callable."""
    import math
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    if callable(fmt):
        return fmt(v)
    if fmt == "pct":
        return pct(v, nd=1 if nd is None else nd)
    if fmt == "pp":
        return pp(v, nd=1 if nd is None else nd)
    if fmt == "int":
        return _signed(f"{round(v):,}", v, False)
    if fmt == "raw":
        return str(v)
    if fmt == "num":
        return num(v, nd=1 if nd is None else nd)
    return _signed(fmt.format(v), v, False)


# ====================================================================== business helpers
ARROW_UP, ARROW_DOWN, FLAT = "▲", "▼", "–"


def delta(cur, prev, kind="growth", nd=1):
    """Change of cur vs prev as (text, signed value). kind: 'growth' -> '▲ 2.0%' (relative to
    |prev|, so the arrow always follows the direction of the change, also for negative bases);
    'pp' (both are ratios) -> '▼ 2.8pp'; 'abs' -> '▲ 1.2M'. House style: arrows + neutral
    colour; colour only when is_anomaly() says so."""
    if cur is None or prev is None:
        return "", None
    if kind == "growth":
        d = (cur - prev) / abs(prev) if prev else None   # abs(): -10 -> -5 is a rise
        if d is None:
            return "", None
        s = pct(abs(d), nd=nd)
    elif kind == "pp":
        d = cur - prev
        s = pp(abs(d), signed=False, nd=nd)
    else:
        d = cur - prev
        s = num(abs(d), nd=nd)
    r = round(d * (100 if kind in ("growth", "pp") else 1), nd)
    arrow = ARROW_UP if r > 0 else ARROW_DOWN if r < 0 else FLAT
    return f"{arrow} {s}", d


def time_progress(as_of, start, end) -> float:
    """Share of the period elapsed, counting whole days inclusive (10/09 in October -> 9/31)."""
    import pandas as pd
    a, s0, e = (pd.Timestamp(x) for x in (as_of, start, end))
    return max(0.0, min(1.0, ((a - s0).days + 1) / ((e - s0).days + 1)))


def is_anomaly(value=None, change=None, history=None, target=None, progress=None,
               threshold=None, sigma=2.0, higher_is_better=True, min_history=4):
    """House rules for "colour only the abnormal":
      1. behind pace   -- value / target < progress (time elapsed share);
      2. fixed threshold -- |change| > threshold (same unit as change: ratio for growth, ratio for pp);
      3. outside history -- value outside mean ± sigma·sd of `history` (e.g. last 8 periods).
    Returns (flag, bad, reasons): bad=True when the deviation goes the wrong way."""
    import numpy as np
    reasons, bad = [], False
    if target and progress is not None and value is not None:
        ach = value / target
        if (ach < progress - 1e-9) if higher_is_better else (ach > progress + 1e-9):
            reasons.append(T("落后时间进度", "behind pace"))
            bad = True
    if threshold is not None and change is not None and abs(change) > threshold:
        reasons.append(T("超过阈值", "beyond threshold"))
        bad = bad or ((change < 0) if higher_is_better else (change > 0))
    if history is not None and value is not None:
        h = np.asarray([x for x in history if x is not None], float)
        h = h[np.isfinite(h)]
        if len(h) >= min_history and h.std(ddof=1) > 0:
            m, sd = h.mean(), h.std(ddof=1)
            if abs(value - m) > sigma * sd:
                reasons.append(T(f"超出历史 ±{sigma:g}σ", f"outside ±{sigma:g}σ"))
                bad = bad or ((value < m) if higher_is_better else (value > m))
    return bool(reasons), bad, reasons


def prior_values(dates, values, compare="month", align="weekday"):
    """Comparable prior value for each date (daily data).
    align='weekday': same weekday 4 weeks (month) / 52 weeks (year) earlier -- use for daily
    flow metrics (orders, active users, visits) that have a weekly rhythm.
    align='dom': same day-of-month one month / year earlier -- use for month-to-date
    cumulatives and for metrics tied to calendar dates (billing / due dates, balances)."""
    import pandas as pd
    s = pd.Series(list(values), index=pd.to_datetime(list(dates))).groupby(level=0).sum()
    if align == "weekday":
        off = pd.Timedelta(days=28 if compare == "month" else 364)
        idx = s.index - off
    else:
        off = pd.DateOffset(months=1) if compare == "month" else pd.DateOffset(years=1)
        idx = s.index - off
    return pd.Series(s.reindex(idx).values, index=s.index)


# ====================================================================== Chinese text
_CJK = re.compile(r"[㐀-鿿豈-﫿]")
_PROTECT = re.compile(
    r"(?:https?://|www\.)[^\s　-〿＀-￯一-鿿]+"   # URLs
    r"|[\w.+-]+@[\w-]+\.[\w.]+"                                           # e-mails
    r"|\b(?:[A-Za-z]\.){2,}"                                              # e.g. i.e. U.S.
    r"|\b(?:etc|vs|Inc|Ltd|Co|No|Fig|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\."
)
_FW = {",": "，", ";": "；", ":": "：", "!": "！", "?": "？", "(": "（", ")": "）"}
_FW_OPEN = "（《「『【〔“‘"
_FW_CLOSE = "，。、；：！？）》」』】〕”’"


def zh(text):
    """Normalise punctuation in Chinese text. Call on every Chinese string you write.

    - ASCII , ; : ! ? -> full-width, except between digits (1,000 / 12:30)
    - ASCII ( ) -> full-width （ ） (consistently, also for 34.8%(+2.1pp))
    - '.' that ends a sentence -> 。 (decimals like 3.5 untouched)
    - spaces next to full-width punctuation are removed ('A, B' -> 'A，B')
    - URLs, e-mails and abbreviations (e.g. / etc. / U.S.) are left alone
    Strings without any CJK character are returned unchanged.
    """
    if not text or not _CJK.search(text):
        return text
    keep = []

    def stash(m):
        keep.append(m.group())
        return f"\x00{len(keep) - 1}\x00"

    t = _PROTECT.sub(stash, text)

    def sub(m):
        i, ch = m.start(), m.group()
        prev = t[i - 1] if i else ""
        nxt = t[i + 1] if i + 1 < len(t) else ""
        if ch in ",:" and prev.isdigit() and nxt.isdigit():
            return ch
        return _FW[ch]

    t = re.sub(r"[,;:!?()]", sub, t)
    # sentence-final '.' : not part of a number (next char is space / CJK / end)
    t = re.sub(r"(?<=\S)\.(?=\s|$|[㐀-鿿])", "。", t)
    t = re.sub(r"[ \t]+(?=[" + _FW_CLOSE + "。（《「『【])", "", t)
    t = re.sub(r"(?<=[" + _FW_CLOSE + _FW_OPEN + "。])[ \t]+", "", t)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], t)


_NO_START = set(_FW_CLOSE + "。%％·…—‐-,.;:!?)]}")   # never begin a line
_NO_END = set(_FW_OPEN + "([{")                        # never end a line
_ATOM = re.compile(r"[\x21-\x7e−–]+|\s|.")   # ASCII run (number/word) = one unit


def _w(s: str) -> int:
    return sum(2 if ord(c) > 0x2E80 else 1 for c in s)


def wrap_cjk(text: str, width: int = 34) -> str:
    """Wrap mixed CJK/ASCII text to `width` units (CJK = 2, ASCII = 1).

    - numbers / English words (e.g. '17.5%', 'GMV') are never split, unless a single
      token is longer than a whole line
    - kinsoku: closing punctuation never starts a line (it overflows onto the previous
      line); opening brackets/quotes never end a line (they move to the next line)
    - existing '\\n' are kept
    """
    out = []
    for para in text.split("\n"):
        lines, line = [], ""
        for atom in _ATOM.findall(para):
            if atom.isspace() and not line:
                continue
            aw = _w(atom)
            if line and _w(line) + aw > width and not atom.isspace():
                if atom[0] in _NO_START:
                    if len(atom) == 1 or atom[0] not in "-‐":   # e.g. '，' / '%,' overflow
                        line += atom
                        continue
                carry = ""
                while line and line[-1] in _NO_END:
                    carry, line = line[-1] + carry, line[:-1]
                lines.append(line.rstrip())
                line = carry
            if aw > width and not line:                # overlong token: hard split
                while _w(atom) > width:
                    cut = 0
                    while _w(atom[:cut + 1]) <= width:
                        cut += 1
                    lines.append(atom[:cut])
                    atom = atom[cut:]
            line += atom
        lines.append(line.rstrip())
        out.extend(lines)
    return "\n".join(out)


def _fit(text: str, w_in: float, size_pt: float) -> str:
    """Wrap text to a box `w_in` inches wide at `size_pt` (CJK glyph ~= 1.05 em)."""
    chars = max(4, int(w_in * 72 / (size_pt * 1.05)))
    return wrap_cjk(text, chars * 2)



# ====================================================================== rich text
# Markup (Chinese punctuation is normalised with zh() first; both () and （） work):
#   **粗体**                  bold, same colour as the surrounding text
#   [关键短语](focus)          bold + colour. colour = PAL name (focus/brand/support/context/
#                              good/bad), ink / muted / white / black, or a hex like #2b5c8a
#   [关键短语](focus,normal)   colour, regular weight
#   \n                         hard line break
# Typical SWD two-tone title: "线上增速 [约为门店的 2.2 倍](focus)，新品类体量仍小"
_MD = re.compile(r"\*\*(.+?)\*\*"
                 r"|\[([^\]]+)\]\x01\s*(#[0-9A-Fa-f]{6}|[A-Za-z_]+)\s*(?:[,，]\s*(normal))?\s*\x02")


def _protect_md(s):
    """Hide the '(colour)' part of [text](colour) from zh() (it would turn the parens
    full-width and eat neighbouring spaces)."""
    return re.sub(r"\]\s*[(（]([^)）]*)[)）]", lambda m: "]\x01" + m.group(1) + "\x02", s)
_WCACHE = {}


def _colour(c):
    if c.startswith("#"):
        return c
    named = {"ink": INK, "muted": MUTED, "grid": GRID, "white": "#ffffff", "black": "#000000"}
    if c in named:
        return named[c]
    if c in ("focus", "brand", "support", "context", "good", "bad"):
        return getattr(PAL, c)        # resolved at render time -> follows set_palette()
    raise ValueError(f"unknown colour '{c}' in markup; use a PAL name, ink/muted/white/black or #hex")


def has_markup(s) -> bool:
    return bool(s) and bool(_MD.search(_protect_md(s)))


def rich(md: str, color=None, bold=False):
    """Parse markup -> runs [(text, colour, bold)]. Applies zh() to the whole string."""
    color = color or INK
    s = zh(_protect_md(md))
    runs, pos = [], 0
    for m in _MD.finditer(s):
        if m.start() > pos:
            runs.append((s[pos:m.start()], color, bold))
        if m.group(1) is not None:
            runs.append((m.group(1), color, True))
        else:
            runs.append((m.group(2), _colour(m.group(3)), m.group(4) is None))
        pos = m.end()
    if pos < len(s):
        runs.append((s[pos:], color, bold))
    return runs


def strip_markup(md: str) -> str:
    return "".join(t for t, _, _ in rich(md))


_MDPI = 720           # measure at high dpi: 72-dpi metrics are hinted / rounded to whole points


def _font_prop(fam, size, bold):
    from matplotlib.font_manager import FontProperties
    return FontProperties(family=fam, size=size, weight="bold" if bold else "normal")


def text_width(s: str, size: float, bold: bool = False) -> float:
    """Rendered width of `s` in inches (same font/size matplotlib will use)."""
    fam = font_for(s)
    key = (s, size, bold, fam)
    if key not in _WCACHE:
        from matplotlib.backends.backend_agg import RendererAgg
        r = _WCACHE.setdefault("_r", RendererAgg(10, 10, _MDPI))
        _WCACHE[key] = r.get_text_width_height_descent(
            s, _font_prop(fam, size, bold), ismath=False)[0] / _MDPI
    return _WCACHE[key]


def _rich_lines(runs, max_w, size):
    """Greedy wrap of styled runs. Returns lines = [[(text, colour, bold, x_in), ...], ...].
    Same rules as wrap_cjk: numbers/words never split, kinsoku on both ends."""
    out, cur, x = [], [], 0.0
    for t, c, b in runs:
        for a in _ATOM.findall(t):
            if a == "\n":
                out.append(cur)
                cur, x = [], 0.0
                continue
            if a.isspace() and not cur:
                continue
            aw = text_width(a, size, b)
            if cur and x + aw > max_w and not a.isspace():
                if a[0] in _NO_START and (len(a) == 1 or a[0] not in "-‐"):
                    cur.append((a, c, b, x))
                    x += aw
                    continue
                carry = []
                while cur and cur[-1][0] in _NO_END:
                    carry.insert(0, cur.pop())
                while cur and cur[-1][0].isspace():
                    cur.pop()
                out.append(cur)
                cur, x = [], 0.0
                for ca, cc, cb, _ in carry:
                    cur.append((ca, cc, cb, x))
                    x += text_width(ca, size, cb)
            cur.append((a, c, b, x))
            x += aw
    out.append(cur)
    merged = []                                   # join neighbours with the same style
    for line in out:
        segs = []
        for a, c, b, ax in line:
            if segs and segs[-1][1] == c and segs[-1][2] == b:
                segs[-1][0] += a
            else:
                segs.append([a, c, b, ax])
        merged.append([tuple(s) for s in segs])
    return merged


class Para:
    """One paragraph for text_panel(). md may contain markup."""
    def __init__(self, md, size=13, color=None, bold=False, lh=1.45, space_after=0.12,
                 x=0.0, ha="left"):
        self.md, self.size, self.color, self.bold = md, size, color, bold
        self.lh, self.space_after, self.x, self.ha = lh, space_after, x, ha

    def lines(self, w):
        return _rich_lines(rich(self.md, self.color or INK, self.bold), w - self.x, self.size)

    def height(self, w):
        return _layout_para(self, w, 0.0)[1]


def para(md, **kw) -> Para:
    """para("文字 [关键](focus)", size=13, color=None, bold=False, lh=1.45, space_after=0.12)"""
    return Para(md, **kw)


_LINESPACING = 1.2    # plotnine's geom_text lineheight default; text panels pass it explicitly


def vmetrics(text, size, bold=False):
    """(ascent, descent) in inches of the box matplotlib itself reports for `text` (the same
    box the layout QA checks), so text panels are sized to what will actually be measured.
    The box depends on the matplotlib version (3.11 changed text layout) and on the line
    spacing, so it is measured through a real Text with plotnine's numeric line spacing."""
    fam = font_for(text)
    key = ("vm", text, size, bold, fam)
    if key not in _WCACHE:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        fig = _WCACHE.get("_vfig")
        if fig is None:
            fig = _WCACHE["_vfig"] = Figure(figsize=(4, 4), dpi=_MDPI)
            FigureCanvasAgg(fig)
        r = fig.canvas.get_renderer()
        asc = desc = 0.0
        for s in (text or "lp", "lp"):
            t = fig.text(0, 0.5, s, fontproperties=_font_prop(fam, size, bold), va="baseline",
                         linespacing=_LINESPACING)
            bb = t.get_window_extent(r)
            t.remove()
            base = 0.5 * fig.bbox.height
            asc, desc = max(asc, (bb.y1 - base) / _MDPI), max(desc, (base - bb.y0) / _MDPI)
        _WCACHE[key] = (asc, desc)
    return _WCACHE[key]


def line_height(text, size, bold=False):
    """Height in inches of one line of `text` as matplotlib boxes it (ascent + descent)."""
    a, d = vmetrics(text, size, bold)
    return a + d


def _layout_para(p, w, top):
    """Baselines for each line of a Para (font-metric based). Returns (blocks, height)."""
    lines = p.lines(w)
    blocks, base, prev_d, first_a = [], None, 0.0, 0.0
    for segs in lines:
        segs = segs or [("", INK, False, 0.0)]
        a = max(vmetrics(t, p.size, b)[0] for t, _, b, _ in segs)
        d = max(vmetrics(t, p.size, b)[1] for t, _, b, _ in segs)
        if base is None:
            base, first_a = top - a, a
        else:
            base -= max(p.lh * p.size / 72, prev_d + a)
        line_w = sum(text_width(t, p.size, b) for t, _, b, _ in segs if t)
        off = {"left": 0, "center": (w - p.x - line_w) / 2, "right": w - p.x - line_w}[p.ha]
        for t, c, b, ax in segs:
            if t:
                blocks.append(dict(t=t, x=p.x + off + ax, y=base, size=p.size, color=c, bold=b))
        prev_d = d
    height = (top - base + prev_d) if base is not None else 0.0
    return blocks, height


def _blocks_for(paras, w, top):
    """Lay paragraphs out from y=top downwards. Returns (blocks, y_bottom)."""
    blocks, y = [], top
    for p in paras:
        if p is None:
            continue
        b, hgt = _layout_para(p, w, y)
        blocks += b
        y -= hgt + p.space_after
    return blocks, y


def _text_plot(blocks, w, h, rule_x=None, bg=None, hrules=None):
    """Absolute-inch text plot. blocks: dicts(t, x, y[baseline], size, color, bold) or legacy
    tuples (text, x, y_top, size, color, bold, lh). hrules: [(x0, x1, y, colour, size)]."""
    import pandas as pd
    from plotnine import (ggplot, aes, geom_text, geom_segment, geom_rect,
                          scale_x_continuous, scale_y_continuous, theme_void, theme)
    from plotnine import geom_blank
    one = pd.DataFrame({"a": [0]})
    p = ggplot() + geom_blank(aes(x=0, y=0), data=one)      # never an empty plot
    if bg:
        p = p + geom_rect(aes(xmin=0, xmax=w, ymin=0, ymax=h), data=one, fill=bg, color=bg)
    if rule_x is not None:
        p = p + geom_segment(aes(x=rule_x, xend=rule_x, y=0.05, yend=h - 0.05),
                             data=one, color=GRID, size=0.8)
    for x0, x1, y, col, sz in hrules or []:
        p = p + geom_segment(aes(x=x0, xend=x1, y=y, yend=y), data=one, color=col, size=sz)
    for b in blocks:
        if isinstance(b, tuple):                  # legacy: top-anchored multi-line text
            text, x, y, size, color, bold, lh = b
            p = p + geom_text(aes(x=x, y=y, label=[text]), data=one, ha="left", va="top",
                              size=size, color=color, family=font_for(text),
                              fontweight="bold" if bold else "normal", lineheight=lh)
        else:
            p = p + geom_text(aes(x=b["x"], y=b["y"], label=[b["t"]]), data=one,
                              ha="left", va="baseline", size=b["size"], color=b["color"],
                              family=font_for(b["t"]), fontweight="bold" if b["bold"] else "normal",
                              lineheight=_LINESPACING)
    return (p + scale_x_continuous(limits=(0, w), expand=(0, 0))
              + scale_y_continuous(limits=(0, h), expand=(0, 0))
              + theme_void() + theme(plot_margin=0))


def _text_panel(blocks, w, h):
    """Back-compat: blocks = [(text, y_top_in, size_pt, color, bold)] at x = 0."""
    return _text_plot([(t, 0, y, s, c, b, 1.25) for t, y, s, c, b in blocks], w, h)


# ====================================================================== panels & layout
class SizedPanel:
    """A panel built only once its final size (inches) is known. build_slide / save call
    `.at(w, h)`, which returns a plotnine plot OR a list of (panel, dx, dy, w, h) children."""
    def __init__(self, fn):
        self.fn = fn

    def at(self, w, h):
        return self.fn(w, h)


class TextPanel(SizedPanel):
    """Paragraphs of rich text, top-aligned. height_for(w) = height it needs."""
    def __init__(self, paras, rule=False, bg=None, pad=0.0):
        self.paras = [p if isinstance(p, Para) or p is None else Para(p) for p in paras]
        self.rule, self.bg, self.pad = rule, bg, pad

    def _x0(self):
        return 0.2 if self.rule else 0.0

    def height_for(self, w):
        _, y = _blocks_for(self.paras, w - self._x0() - 2 * self.pad, 0)
        last = next((p for p in reversed(self.paras) if p is not None), None)
        return -y - (last.space_after if last else 0) + 2 * self.pad

    def at(self, w, h):
        x0 = self._x0() + self.pad
        blocks, y = _blocks_for(self.paras, w - x0 - self.pad, h - self.pad)
        for b in blocks:
            b["x"] += x0
        last = next((p for p in reversed(self.paras) if p is not None), None)
        if y + (last.space_after if last else 0) < -0.01:
            print(f"WARNING text panel overflows its box by {-y:.2f} in: shorten the text, "
                  "give the panel more room, or use a smaller size.")
        return _text_plot(blocks, w, h, rule_x=0.02 if self.rule else None, bg=self.bg)


def text_panel(*paras, rule=False, bg=None, pad=0.0) -> TextPanel:
    """A panel of paragraphs. Each item: a markup string (13pt ink) or para(...).
    rule=True draws a thin vertical rule on the left (side-column look)."""
    return TextPanel(paras, rule=rule, bg=bg, pad=pad)


class Column(SizedPanel):
    """Stack panels vertically in one cell. TextPanels take the height they need; plots
    (or (plot, weight)) share the rest."""
    def __init__(self, children, gap=0.12):
        self.children = [c if isinstance(c, tuple) else (c, 1) for c in children]
        self.gap = gap

    def at(self, w, h):
        fixed = [c.height_for(w) if isinstance(c, TextPanel) else None for c, _ in self.children]
        flex_w = sum(wt for (c, wt), f in zip(self.children, fixed) if f is None)
        rest = h - sum(f for f in fixed if f) - self.gap * (len(self.children) - 1)
        if flex_w and rest < 1.0:
            print(f"WARNING column: only {rest:.2f} in left for the chart(s); shorten the text.")
        out, y = [], 0.0
        for (c, wt), f in zip(self.children, fixed):
            hh = f if f is not None else max(rest, 0.5) * wt / flex_w
            out.append((c, 0.0, y, w, hh))
            y += hh + self.gap
        return out


def column(*children, gap=0.12) -> Column:
    """column(text_panel(...), plot) -> paragraph above chart in the same cell."""
    return Column(children, gap=gap)


def legend_md(*items, prefix=None, sep=" | "):
    """Coloured-word legend line, e.g. legend_md(("通过人数", "brand"), ("额度", "bad"),
    prefix="指标") -> '指标 | [通过人数](brand) | [额度](bad)'. Put it in titled(legend=...)."""
    parts = ([prefix] if prefix else []) + [f"[{t}]({c})" for t, c in items]
    return sep.join(parts)


class _Titled(SizedPanel):
    """titled() result: built at render time so default sizes follow the current spec."""
    def __init__(self, plot, title, legend, note, title_pt, legend_pt, gap):
        self.args = (plot, title, legend, note, title_pt, legend_pt, gap)

    def at(self, w, h):
        plot, title, legend, note, title_pt, legend_pt, gap = self.args
        b = cur().get("base", 12)
        title_pt = title_pt or b * 1.15
        legend_pt = legend_pt or b * 0.88
        gap = b / 12 * 0.06 if gap is None else gap
        paras = []
        if title:
            paras.append(Para(title, size=title_pt, bold=not has_markup(title), lh=1.3,
                              space_after=0.04 * b / 12))
        if legend:
            paras.append(Para(legend, size=legend_pt, color=MUTED, lh=1.3, space_after=0.02))
        if note:
            paras.append(Para(note, size=legend_pt, color=MUTED, lh=1.3, space_after=0.02))
        return Column([TextPanel(paras), plot], gap=gap).at(w, h) if paras else [(plot, 0, 0, w, h)]


def titled(plot, title=None, legend=None, note=None, title_pt=None, legend_pt=None, gap=None):
    """Panel header above a chart: bold title (markup ok), an optional coloured-word legend
    line (charts expose one as chart.legend) and an optional grey note. Sizes default to the
    current spec (title = 1.15 × base, legend/note = 0.88 × base)."""
    if legend is None and hasattr(plot, "legend"):
        legend = plot.legend
    return _Titled(plot, title, legend, note, title_pt, legend_pt, gap)


def takeaway_panel(kpis, so_what: str, heading: str | None = None, wrap: int | None = None,
                   big_pt: float = 30, label_pt: float = 12, text_pt: float = 13):
    """Text-only side column: big numbers (kpis = [(big, label, color), ...]) + one so-what.
    so_what may use markup (colour the phrase that matches the data). `wrap` is ignored
    (kept for back-compat): wrapping follows the panel's real width.
    Rule: don't repeat the big numbers again inside `so_what`."""
    heading = heading or T("所以呢", "So what")
    paras = []
    for big, lab, col in kpis:
        paras.append(Para(f"[{big}]({col})", size=big_pt, lh=1.1, space_after=0.02))
        paras.append(Para(lab, size=label_pt, color=MUTED, lh=1.3, space_after=0.22))
    if so_what:
        paras.append(Para(heading, size=11, color=MUTED, lh=1.3, space_after=0.04))
        paras.append(Para(so_what, size=text_pt, lh=1.5, space_after=0))
    return TextPanel(paras, rule=True)


class TablePanel(TextPanel):
    """A small, quiet table (header rule + light row rules, no grid). Fixed height ->
    works inside column(). Cells may use markup ("[+2.1pp](bad)")."""
    def __init__(self, rows, header=None, align=None, bold_rows=(), size=10.5, row_h=1.9,
                 col_widths=None):
        self.rows = [[str(c) for c in r] for r in rows]
        self.header = [str(c) for c in header] if header else None
        ncol = len(self.header or self.rows[0])
        if align is None:                      # numbers right, text left
            numre = re.compile(r"^[\s+\-−–$€¥£]*[\d.,]+\s*(%|pp|x|倍|亿|万|[KMB])?\s*$")
            def is_num(c):
                return bool(numre.match(strip_markup(c).replace("*", "")))
            align = ["right" if all(is_num(r[j]) for r in self.rows if j < len(r)) else "left"
                     for j in range(ncol)]
        self.align = align
        self.bold_rows, self.size, self.row_h, self.col_widths = set(bold_rows), size, row_h, col_widths
        self.paras, self.rule, self.bg, self.pad = [], False, None, 0.0

    def _lines(self):
        return ([self.header] if self.header else []) + self.rows

    def height_for(self, w):
        return len(self._lines()) * self.size * self.row_h / 72 + 0.04

    def _runs(self, cell, i_line):
        is_head = self.header is not None and i_line == 0
        bold = (not is_head) and (i_line - (1 if self.header else 0)) in self.bold_rows
        color = MUTED if is_head else INK
        return _rich_lines(rich(cell, color, bold), 1e9, self.size * (0.92 if is_head else 1))[0]

    def at(self, w, h):
        lines = self._lines()
        ncol = len(lines[0])
        seg_lines = [[self._runs(c, i) for c in ln] for i, ln in enumerate(lines)]
        width = [max(sum(text_width(t, self.size, b) for t, _, b, _ in segs[j]) for segs in seg_lines)
                 for j in range(ncol)]
        if self.col_widths:
            cw = [w * f / sum(self.col_widths) for f in self.col_widths]
        else:
            need = [x + 0.25 for x in width]
            cw = [x * w / sum(need) for x in need]          # fill the panel width
        rh = self.size * self.row_h / 72
        blocks, rules = [], []
        y_top = h - 0.02
        for i, segs_row in enumerate(seg_lines):
            base = y_top - i * rh - rh * 0.68
            x0 = 0.0
            for j, segs in enumerate(segs_row):
                tw = sum(text_width(t, self.size, b) for t, _, b, _ in segs)
                start = x0 + (0.04 if self.align[j] == "left" else cw[j] - tw - 0.04)
                for t, c, b, ax in segs:
                    sz = self.size * (0.92 if (self.header and i == 0) else 1)
                    blocks.append(dict(t=t, x=start + ax, y=base, size=sz, color=c, bold=b))
                x0 += cw[j]
            yl = y_top - (i + 1) * rh
            if self.header and i == 0:
                rules.append((0, w, yl, MUTED, 0.6))
            elif i < len(seg_lines) - 1:
                rules.append((0, w, yl, GRID, 0.4))
        return _text_plot(blocks, w, h, hrules=rules)


def table_panel(rows, header=None, align=None, bold_rows=(), size=10.5, col_widths=None):
    """Small table for reports: table_panel([["线上", "42.1", "[+4.1%](brand)"], ...],
    header=["渠道", "GMV / $m", "较同期"]). First column left-aligned, others right-aligned.
    bold_rows: indexes (0-based, excluding header) to set in bold. Use for <= ~8 rows;
    anything longer belongs in an appendix or a chart. align=None -> numeric columns right,
    text columns left."""
    return TablePanel(rows, header, align, bold_rows, size, col_widths=col_widths)


# ====================================================================== chart helpers
def theme_canvas(base: int = 12):
    """theme_story(panel=True) with NO axis text/grid: for charts that draw their own
    category labels / value labels with geom_text (full control of colour and weight)."""
    return theme_story(base, panel=True) + theme(
        axis_text=element_blank(), panel_grid_major_x=element_blank(),
        panel_grid_major_y=element_blank(), panel_grid_minor=element_blank())


def _one(**cols):
    import pandas as pd
    return pd.DataFrame({k: [v] for k, v in cols.items()})


def txt(x, y, label, color=None, size=12, bold=False, ha="left", va="center",
        italic=False, lh=1.25):
    """One text label in data coordinates (a geom_text layer). Chinese is passed through zh()."""
    from plotnine import geom_text, aes
    kw = dict(fontstyle="italic") if italic else {}
    label = zh(str(label))
    check_contrast(color or INK, size, bold, label)
    return geom_text(aes(x="x", y="y", label="label"), data=_one(x=x, y=y, label=label),
                     inherit_aes=False, color=color or INK, size=size, ha=ha, va=va,
                     fontweight="bold" if bold else "normal", family=font_for(label),
                     lineheight=lh, **kw)


def rect(xmin, xmax, ymin, ymax, fill, color=None, size=0.0, linetype="solid"):
    """One rectangle (bar segment, shaded band, ghost box) in data coordinates."""
    from plotnine import geom_rect, aes
    return geom_rect(aes(xmin="a", xmax="b", ymin="c", ymax="d"),
                     data=_one(a=xmin, b=xmax, c=ymin, d=ymax), inherit_aes=False,
                     fill=fill, color=color if color else fill, size=size, linetype=linetype)


def seg(x, xend, y, yend, color=None, size=0.6, linetype="solid"):
    """One line segment in data coordinates (leader line, rule, range bar)."""
    from plotnine import geom_segment, aes
    return geom_segment(aes(x="a", xend="b", y="c", yend="d"),
                        data=_one(a=x, b=xend, c=y, d=yend), inherit_aes=False,
                        color=color or MUTED, size=size, linetype=linetype)


def dot(x, y, color=None, fill=None, size=4, stroke=1.0):
    """One point. fill='white' -> hollow dot (earlier period / not-in-focus)."""
    from plotnine import geom_point, aes
    color = color or INK
    return geom_point(aes(x="a", y="b"), data=_one(a=x, b=y), inherit_aes=False, shape="o",
                      color=color, fill=fill or color, size=size, stroke=stroke)


def month_labels(periods, lang: str | None = None):
    """periods: iterable of (year, month). Two-tier labels: the year only on the first period
    and every January. zh: '1月\\n2025', '2月' …;  en: 'Jan\\n2025', 'Feb' …"""
    import calendar
    lang = lang or LANG
    out, prev = [], None
    for y, m in periods:
        lab = f"{m}月" if lang == "zh" else calendar.month_abbr[m]
        out.append(f"{lab}\n{y}" if prev is None or y != prev else lab)
        prev = y
    return out


def dodge(values, min_gap):
    """Nudge label positions apart so end labels of close lines don't overlap. Only labels
    that collide move; each colliding cluster stays centred on its original mean.
    Returns new positions in the same order as `values`."""
    vals = [float(v) for v in values]
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    clusters = [[i] for i in order]

    def place(c):
        mid = sum(vals[i] for i in c) / len(c)
        start = mid - min_gap * (len(c) - 1) / 2
        return [start + k * min_gap for k in range(len(c))]

    changed = True
    while changed:
        changed = False
        for k in range(len(clusters) - 1):
            a, b = clusters[k], clusters[k + 1]
            if place(b)[0] - place(a)[-1] < min_gap - 1e-12:
                clusters[k:k + 2] = [a + b]
                changed = True
                break
    out = vals[:]
    for c in clusters:
        for i, pos in zip(c, place(c)):
            out[i] = pos
    return out


# ====================================================================== output specs
# One spec per target medium. W/H in inches; *_pt = page title / subtitle / caption sizes;
# base = chart text size (pt) used by charts.py; lw = line-width multiplier; dpi = PNG dpi.
_SLIDE_T = dict(top=0.45, bottom=0.35, side=0.55, gap=0.35, title_pt=26, sub_pt=14, cap_pt=10)
_DOC_T = dict(top=0.10, bottom=0.06, side=0.06, gap=0.25, title_pt=12, sub_pt=9.5, cap_pt=8)
_JOUR_T = dict(top=0.06, bottom=0.04, side=0.04, gap=0.15, title_pt=8.5, sub_pt=7, cap_pt=6.5)
SPECS = {
    # business presentations
    "slide":     dict(W=13.333, H=7.5, base=12, lw=1.0, dpi=150,
                      formats=("svg", "editable", "png"), **_SLIDE_T),
    "slide-4x3": dict(W=10.0, H=7.5, base=11.5, lw=1.0, dpi=150,
                      formats=("svg", "editable", "png"), **_SLIDE_T),
    "web":       dict(W=8.0, H=4.5, base=10.5, lw=0.9, dpi=200, formats=("svg", "png"),
                      top=0.25, bottom=0.2, side=0.25, gap=0.3, title_pt=16, sub_pt=11, cap_pt=8.5),
    # documents / reports (full pages, or one figure inside a 6.5in text column)
    "a4":        dict(W=8.27, H=11.69, base=10, lw=0.9, dpi=200, formats=("pdf", "svg", "png"),
                      top=0.6, bottom=0.45, side=0.6, gap=0.3, title_pt=20, sub_pt=11.5, cap_pt=8.5),
    "letter":    dict(W=8.5, H=11.0, base=10, lw=0.9, dpi=200, formats=("pdf", "svg", "png"),
                      top=0.6, bottom=0.45, side=0.6, gap=0.3, title_pt=20, sub_pt=11.5, cap_pt=8.5),
    "doc":       dict(W=6.5, H=4.0, base=9, lw=0.8, dpi=300, formats=("pdf", "svg", "png"), **_DOC_T),
    # journals / formal publication (Nature-style widths: 89 / 136 / 183 mm)
    "journal-1col":   dict(W=3.5, H=2.6, base=7, lw=0.6, dpi=600, formats=("pdf", "svg", "png"), **_JOUR_T),
    "journal-1.5col": dict(W=5.35, H=3.6, base=7, lw=0.6, dpi=600, formats=("pdf", "svg", "png"), **_JOUR_T),
    "journal-2col":   dict(W=7.2, H=4.2, base=7.5, lw=0.65, dpi=600, formats=("pdf", "svg", "png"), **_JOUR_T),
}
PAGES = {"16:9": "slide", "A4": "a4"}          # back-compat names for build_slide(page=...)
SLIDE_W, SLIDE_H = SPECS["slide"]["W"], SPECS["slide"]["H"]
_CUR = dict(SPECS["slide"])


def cur() -> dict:
    """The spec being rendered right now (charts.py reads base font size / line width)."""
    return _CUR


def use_spec(spec="slide", **override):
    """Set the current spec explicitly (figure()/save() do this for you)."""
    global _CUR
    d = dict(SPECS[spec] if isinstance(spec, str) else spec)
    d.update(override)
    _CUR = d
    return d


# ====================================================================== export
FORMATS = ("svg", "editable", "png", "pdf")


def _prefix_svg_ids(root, pre: str):
    """Make ids unique when several matplotlib SVGs are nested into one document
    (glyph defs, clipPaths ... would otherwise collide; breaks Figma/Illustrator import)."""
    ids = {}
    for el in root.iter():
        i = el.get("id")
        if i:
            ids[i] = pre + i
            el.set("id", pre + i)
    if not ids:
        return
    url = re.compile(r"url\(\s*#([^)\s]+)\s*\)")

    def fix(s):
        return url.sub(lambda m: f"url(#{ids.get(m.group(1), m.group(1))})", s)

    for el in root.iter():
        for k, v in list(el.attrib.items()):
            if k.endswith("href") and v.startswith("#"):
                el.set(k, "#" + ids.get(v[1:], v[1:]))
            elif "url(" in v:
                el.set(k, fix(v))
        if el.text and "url(" in el.text:
            el.text = fix(el.text)


def _resolve(items):
    """Expand SizedPanels (recursively) into plain (plot, x, y, w, h)."""
    out = []
    for p, x, y, w, h in items:
        r = p.at(w, h) if isinstance(p, SizedPanel) else p
        if isinstance(r, list):
            out.extend(_resolve([(c, x + dx, y + dy, cw, ch) for c, dx, dy, cw, ch in r]))
        else:
            out.append((r, x, y, w, h))
    return out


def _draw(plot, w, h):
    """plotnine plot -> matplotlib Figure at exactly w x h inches. Returns None only for
    objects without .draw() (then the page is saved without layout QA, with a WARNING);
    errors raised while drawing propagate instead of silently skipping QA."""
    if not hasattr(plot, "draw"):
        return None
    fig = (plot + theme(figure_size=(w, h))).draw()
    try:
        fig.set_size_inches(w, h)
    except Exception:
        pass
    return fig


def _renderer(fig):
    """A renderer for measuring text. plotnine's draw() returns a figure whose canvas is the
    abstract FigureCanvasBase (no get_renderer) -> attach an Agg canvas first."""
    if not hasattr(fig.canvas, "get_renderer"):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        FigureCanvasAgg(fig)
    return fig.canvas.get_renderer()


def _text_boxes(fig, k, x0, y0, w, h, issues):
    """Collect every visible text's box in page inches (top-left origin); flag clipping."""
    from matplotlib.text import Text
    r = _renderer(fig)
    dpi = fig.dpi
    boxes = []
    for t in fig.findobj(Text):
        s = t.get_text()
        if not t.get_visible() or not s.strip():
            continue
        try:
            bb = t.get_window_extent(r)
        except Exception:
            continue
        if bb.width <= 0 or bb.height <= 0:
            continue
        lab = s.replace("\n", " ")[:24]
        tol = 1.5   # px
        if (bb.x0 < -tol or bb.y0 < -tol or bb.x1 > w * dpi + tol or bb.y1 > h * dpi + tol):
            issues.append(f"text runs outside its panel: '{lab}'")
        elif t.get_clip_on() and t.axes is not None:
            ab = t.axes.get_window_extent(r)
            if bb.x0 < ab.x0 - tol or bb.x1 > ab.x1 + tol or bb.y0 < ab.y0 - tol or bb.y1 > ab.y1 + tol:
                issues.append(f"text clipped by the plot area: '{lab}' (widen limits / margins)")
        boxes.append((x0 + bb.x0 / dpi, y0 + h - bb.y1 / dpi,
                      x0 + bb.x1 / dpi, y0 + h - bb.y0 / dpi, lab, k))
    return boxes


def _overlaps(boxes, issues, shrink=0.012):
    """Pairwise text overlap (boxes shrunk by ~1pt so touching neighbours don't count)."""
    bx = [(a + shrink, b + shrink, c - shrink, d - shrink, l, k) for a, b, c, d, l, k in boxes]
    seen = set()
    for i in range(len(bx)):
        a0, b0, c0, d0, l0, k0 = bx[i]
        if c0 <= a0 or d0 <= b0:
            continue
        for j in range(i + 1, len(bx)):
            a1, b1, c1, d1, l1, k1 = bx[j]
            ix = min(c0, c1) - max(a0, a1)
            iy = min(d0, d1) - max(b0, b1)
            if ix > 0.02 and iy > 0.02:                 # > ~1.5pt in both directions
                small = min((c0 - a0) * (d0 - b0), (c1 - a1) * (d1 - b1))
                if small > 0 and ix * iy / small > 0.08 and (l0, l1) not in seen:
                    seen.add((l0, l1))
                    issues.append(f"text overlaps: '{l0}' / '{l1}'")


class Output(list):
    """Paths written by figure() / save() (a plain list, for back-compat) plus `.qa`: the
    list of layout-QA issues (empty = "QA … ok"). Check `out.qa` instead of parsing stdout."""
    qa: list = []


def _compose(items, W, H, name, outdir, formats=None, dpi=None, qa=True):
    """Render each (plot, x, y, w, h) once at its exact size (inches), check the layout, and
    write one page in every requested format. Returns an Output (paths, with .qa issues)."""
    import os, shutil, tempfile
    tmp = tempfile.mkdtemp()
    try:
        return _compose_in(items, W, H, name, outdir, formats, dpi, qa, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _compose_in(items, W, H, name, outdir, formats, dpi, qa, tmp):
    import os
    import xml.etree.ElementTree as ET
    import matplotlib.pyplot as plt
    formats = tuple(formats or cur().get("formats", ("svg", "editable", "png")))
    dpi = dpi or cur().get("dpi", 150)
    unknown = set(formats) - set(FORMATS)
    if unknown:
        raise ValueError(f"unknown formats {unknown}; choose from {FORMATS}")
    _WARNED.clear()                    # contrast warnings: once per colour per page
    items = _resolve(items)
    os.makedirs(outdir, exist_ok=True)
    files = {f: [] for f in formats}
    issues, boxes = [], []
    for k, (plot, x, y, w, h) in enumerate(items):
        fig = _draw(plot, w, h)
        if fig is None:                                    # fallback: old save path, no QA
            print(f"WARNING {name}: panel {k} ({type(plot).__name__}) cannot be drawn directly; "
                  "saved without layout QA.")
            for f in formats:
                ext = "svg" if f in ("svg", "editable") else f
                fn = f"{tmp}/{k}_{f}.{ext}"
                rc = {"svg.fonttype": "none" if f == "editable" else "path"}
                with mpl.rc_context(rc):
                    kw = dict(dpi=dpi, transparent=True) if f == "png" else {}
                    plot.save(fn, width=w, height=h, verbose=False, **kw)
                files[f].append(fn)
            continue
        if qa:
            pi = []
            boxes += _text_boxes(fig, k, x, y, w, h, pi)
            issues += [f"panel {k}: {m}" for m in pi]
        for f in formats:
            ext = "svg" if f in ("svg", "editable") else f
            fn = f"{tmp}/{k}_{f}.{ext}"
            if f == "png":
                fig.savefig(fn, dpi=dpi, transparent=True)
            elif f == "pdf":
                with mpl.rc_context({"pdf.fonttype": 42}):
                    fig.savefig(fn, format="pdf")
            else:
                with mpl.rc_context({"svg.fonttype": "none" if f == "editable" else "path"}):
                    fig.savefig(fn, format="svg")
            files[f].append(fn)
        plt.close(fig)
    if qa:
        _overlaps(boxes, issues)
    outs = []
    SVG = "http://www.w3.org/2000/svg"
    ET.register_namespace("", SVG)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    for f, suffix in (("svg", ""), ("editable", "_editable")):
        if f not in formats:
            continue
        root = ET.Element(f"{{{SVG}}}svg", width=f"{W*72}pt", height=f"{H*72}pt",
                          viewBox=f"0 0 {W*72} {H*72}", version="1.1")
        ET.SubElement(root, f"{{{SVG}}}rect", x="0", y="0", width=str(W * 72),
                      height=str(H * 72), fill="white")
        for k, ((plot, x, y, w, h), fn) in enumerate(zip(items, files[f])):
            child = ET.parse(fn).getroot()
            _prefix_svg_ids(child, f"p{k}-")
            child.set("x", f"{x*72:.2f}"); child.set("y", f"{y*72:.2f}")
            child.set("width", f"{w*72:.2f}"); child.set("height", f"{h*72:.2f}")
            root.append(child)
        path = f"{outdir}/{name}{suffix}.svg"
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        outs.append(path)
    if "pdf" in formats:
        try:
            from pypdf import PdfReader, PdfWriter, PageObject, Transformation
            page = PageObject.create_blank_page(width=W * 72, height=H * 72)
            for (plot, x, y, w, h), fn in zip(items, files["pdf"]):
                src = PdfReader(fn).pages[0]
                page.merge_transformed_page(src, Transformation().translate(x * 72, (H - y - h) * 72))
            wr = PdfWriter()
            wr.add_page(page)
            path = f"{outdir}/{name}.pdf"
            with open(path, "wb") as fh:
                wr.write(fh)
            outs.append(path)
        except ImportError:
            print("WARNING: pdf skipped -- add 'pypdf' to the script dependencies.")
    if "png" in formats:
        from PIL import Image
        canvas = Image.new("RGB", (round(W * dpi), round(H * dpi)), "white")
        for (plot, x, y, w, h), fn in zip(items, files["png"]):
            im = Image.open(fn).convert("RGBA")
            canvas.paste(im, (round(x * dpi), round(y * dpi)), im)
        path = f"{outdir}/{name}.png"
        canvas.save(path, dpi=(dpi, dpi))
        outs.append(path)
    print("saved", *outs)
    if issues:
        print(f"QA {name}: {len(issues)} issue(s)")
        for m in issues[:30]:
            print("  WARNING", m)
    else:
        print(f"QA {name}: ok")
    out = Output(outs)
    out.qa = issues
    return out


def save(p, name: str, w: float | None = None, h: float | None = None, outdir: str = "out",
         formats=None, dpi=None, spec="doc", qa=True):
    """Export ONE chart/panel as its own file (no page title), e.g. a journal figure:
    save(chart, "fig2", spec="journal-1col")   or with an explicit size  w=..., h=...
    Default spec "doc" = 6.5 x 4 in (a figure for a document text column).
    Returns the written paths; `.qa` holds the layout-QA issues (empty list = ok)."""
    d = use_spec(spec)
    w, h = w or d["W"], h or d["H"]
    return _compose([(p, 0, 0, w, h)], w, h, name, outdir, formats, dpi, qa)


def figure(rows, title=None, subtitle=None, caption=None, name="figure", outdir="out",
           spec="slide", size=None, row_heights=None, top=None, bottom=None, side=None,
           gap=None, dpi=None, title_pt=None, sub_pt=None, cap_pt=None, formats=None,
           header_bar=None, bar_text="#ffffff", qa=True):
    """Compose one page / figure from panels and export it.

    spec: a key of SPECS -- 'slide', 'slide-4x3', 'web', 'a4', 'letter', 'doc',
          'journal-1col', 'journal-1.5col', 'journal-2col' (sets size, typography, dpi,
          formats). size=(w, h) overrides the page size (e.g. a taller journal figure).
    rows: [[(panel, span), ...], ...]. panel = a chart from charts.py, a plotnine plot, or
          any SizedPanel (text_panel, table_panel, column, titled ...). span = relative width.
    row_heights: relative heights; None (default) -> rows that hold only text/table panels
          take their natural height, the other rows share the rest equally.
    title / subtitle / caption: optional (journal figures usually have none -- the caption
          lives in the manuscript). Markup allowed: "... [key phrase](focus) ...".
    header_bar: a colour -> the title sits in a full-width dark bar.
    Every panel is rendered at its exact final size, so font sizes are true points.
    After rendering, an automatic QA pass reports overlapping, clipped or overflowing text.
    Returns the written paths; `.qa` holds the QA issues (empty list = ok).
    """
    d = use_spec(spec)
    W, H = size or (d["W"], d["H"])
    top = d["top"] if top is None else top
    bottom = d["bottom"] if bottom is None else bottom
    side = d["side"] if side is None else side
    gap = d["gap"] if gap is None else gap
    title_pt = d["title_pt"] if title_pt is None else title_pt
    sub_pt = d["sub_pt"] if sub_pt is None else sub_pt
    cap_pt = d["cap_pt"] if cap_pt is None else cap_pt
    inner_w = W - 2 * side
    items = []
    y = top
    if title:
        t_para = Para(title, size=title_pt, bold=not has_markup(title), lh=1.3,
                      color=bar_text if header_bar else INK, space_after=0)
        s_para = Para(subtitle, size=sub_pt, color=MUTED, lh=1.4, space_after=0) if subtitle else None
        if header_bar:
            pad = 0.2
            th = t_para.height(inner_w)
            bar_h = top + th + pad
            blocks, _ = _blocks_for([t_para], inner_w, bar_h - top)
            for b in blocks:
                b["x"] += side
            items.append((_text_plot(blocks, W, bar_h, bg=header_bar), 0, 0, W, bar_h))
            y = bar_h + 0.18
            if s_para:
                sh = s_para.height(inner_w)
                items.append((TextPanel([s_para]), side, y, inner_w, sh))
                y += sh
        else:
            if s_para:
                t_para.space_after = 0.1
            hp = TextPanel([t_para, s_para])
            hh = hp.height_for(inner_w)
            items.append((hp, side, top, inner_w, hh))
            y = top + hh
        y += 0.25 * (title_pt / 26) ** 0.5
    elif subtitle:
        sp = TextPanel([Para(subtitle, size=sub_pt, color=MUTED, lh=1.4, space_after=0)])
        sh = sp.height_for(inner_w)
        items.append((sp, side, top, inner_w, sh))
        y = top + sh + 0.1
    if not caption and any(_has_biz(p) for row in rows for p, _ in row):
        print(f"WARNING {name}: business chart without a basis caption -- pass caption= with "
              "numerator/denominator, currency, time window and comparison base.")
    fh = 0
    if caption:
        cp = TextPanel([Para(caption, size=cap_pt, color=MUTED, lh=1.4, space_after=0)])
        fh = cp.height_for(inner_w)
        items.append((cp, side, H - bottom - fh, inner_w, fh))
        fh += 0.12
    # ---- body rows
    body_top = y
    body_h = (H - bottom - fh) - body_top
    avail_h = body_h - gap * (len(rows) - 1)
    rh = list(row_heights) if row_heights else [None] * len(rows)
    widths = []
    for row in rows:
        total = sum(sp for _, sp in row)
        avail_w = inner_w - gap * (len(row) - 1)
        widths.append([avail_w * sp / total for _, sp in row])
    fixed = [None] * len(rows)
    for r_i, (row, hw) in enumerate(zip(rows, rh)):
        if hw is None and all(isinstance(p, TextPanel) for p, _ in row):
            fixed[r_i] = max(p.height_for(wi) for (p, _), wi in zip(row, widths[r_i]))
    flex = [(1 if hw is None else hw) for hw, fx in zip(rh, fixed) if fx is None]
    rest = avail_h - sum(fx for fx in fixed if fx is not None)
    min_row = 0.6 if d["base"] <= 8 else 1.2
    if flex and rest < min_row * len(flex):
        raise ValueError(f"only {rest:.2f} in left for {len(flex)} chart row(s): shorten the "
                         "title/subtitle/caption/text, use a larger size, or fewer rows.")
    y = body_top
    for r_i, row in enumerate(rows):
        hw = 1 if rh[r_i] is None else rh[r_i]
        h_i = fixed[r_i] if fixed[r_i] is not None else rest * hw / sum(flex)
        x = side
        for (plot, sp), w_i in zip(row, widths[r_i]):
            items.append((plot, x, y, w_i, h_i))
            x += w_i + gap
        y += h_i + gap
    return _compose(items, W, H, name, outdir, formats, dpi or d["dpi"], qa)


def _has_biz(obj, depth=0):
    if getattr(obj, "biz", False):
        return True
    if depth > 4 or not hasattr(obj, "__dict__"):
        return False
    for v in vars(obj).values():
        vs = v if isinstance(v, (list, tuple)) else [v]
        if any(_has_biz(x, depth + 1) for x in vs if hasattr(x, "__dict__")):
            return True
    return False


def build_slide(rows, title=None, subtitle=None, caption=None, name="slide", outdir="out",
                page="16:9", spec=None, **kw):
    """Back-compat wrapper: build_slide(..., page="16:9" | "A4") == figure(..., spec=...)."""
    return figure(rows, title, subtitle, caption, name=name, outdir=outdir,
                  spec=spec or PAGES.get(page, page), **kw)


# ====================================================================== emphasis beyond colour
def callout(x, y, text, color=None, xend=None, yend=None, ha="left", size=12, shrink=0.12,
            bold=True):
    """Direct annotation (text, optional arrow to a point). Returns a list of layers:
    p = p + callout(...)  (plotnine accepts lists of layers). Positions are data units
    (for a discrete axis use the 1-based category position).
    shrink: fraction of the text->point vector skipped at the start so the arrow
    doesn't run through the text."""
    import pandas as pd
    from plotnine import geom_text, geom_segment, aes, arrow
    color = color or INK
    one = pd.DataFrame({"a": [0]})
    layers = [geom_text(aes(x=x, y=y, label=[zh(text)]), data=one,
                        ha=ha, va="center", size=size, color=color,
                        fontweight="bold" if bold else "normal",
                        family=font_for(text), inherit_aes=False)]
    if xend is not None:
        x0 = x + (xend - x) * shrink
        y0 = y + (yend - y) * shrink
        layers.append(geom_segment(
            aes(x=x0, xend=xend, y=y0, yend=yend), data=one,
            color=color, size=0.6, arrow=arrow(length=0.06), inherit_aes=False))
    return layers


def ref_line(y, label, x_label, color=None, ha="right", size=11):
    """Horizontal reference line (average / target / same period last year) with a label."""
    import pandas as pd
    from plotnine import geom_hline, geom_text, aes
    color = color or MUTED
    return [
        geom_hline(yintercept=y, color=color, linetype="dashed", size=0.6),
        geom_text(aes(x=x_label, y=y, label=[zh(label)]), data=pd.DataFrame({"a": [0]}),
                  ha=ha, va="bottom", size=size, color=color, family=font_for(label),
                  inherit_aes=False),
    ]
