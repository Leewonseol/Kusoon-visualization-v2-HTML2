"""구순 temporal network 시각화 (Plotly, 자체 포함 HTML — 외부 CDN 로딩 없음).

X축은 모두 '명목 음력 소수연도'(DERIVED_FOR_VISUALIZATION)다. 양력 날짜가 아니며,
불확실한 시점은 점이 아니라 구간(막대·빗금·열린 삼각형)으로 그린다.
"""
from __future__ import annotations

import html
import math

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import gusun_pipeline as gp

OUT = gp.OUT
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
FONT = 'system-ui, -apple-system, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif'

# 관계군 → 고정 순서 범주색 (validate_palette.js 통과; OTHER는 중립 회색)
GROUP_COLOR = {"OFFICIAL": "#2a78d6", "CONFLICT": "#eb6834", "INVESTIGATION": "#1baf7a",
               "PRIVATE_SOCIAL": "#eda100", "HOUSEHOLD": "#e87ba4", "KINSHIP": "#008300",
               "PUNISHMENT": "#4a3aa7", "OTHER": MUTED}
GROUP_KO = {"OFFICIAL": "관료(OFFICIAL)", "CONFLICT": "갈등·고발(CONFLICT)",
            "INVESTIGATION": "수사·증언·보고(INVESTIGATION)", "PRIVATE_SOCIAL": "이웃·친교(PRIVATE_SOCIAL)",
            "HOUSEHOLD": "가내(HOUSEHOLD)", "KINSHIP": "친족(KINSHIP)", "PUNISHMENT": "처벌(PUNISHMENT)",
            "OTHER": "기타(OTHER)"}
# 같은 관계군 안의 세부 유형은 선 모양으로 구분 (색만으로 식별하지 않기 위한 보조 인코딩)
REL_DASH = {"ACCUSATION": "dash", "TESTIMONY": "dot", "DETENTION": "dashdot", "REPORT": "longdash",
            "REEXAMINATION": "longdashdot", "NEIGHBOR": "dot", "COMMAND": "dash",
            "OFFICIAL_COLLEAGUE": "dot", "OFFICIAL_SUBORDINATE": "longdash"}
STATE_COLOR = {"ACTIVE": "#2a78d6", "UNDER_INVESTIGATION": "#eda100", "IMPRISONED": "#e34948",
               "EXILED": "#4a3aa7", "RELEASED": "#1baf7a", "FORMER_OFFICIAL": "#e87ba4",
               "UNKNOWN": MUTED}
STATE_KO = {"ACTIVE": "현직", "UNDER_INVESTIGATION": "조사 중", "IMPRISONED": "수감",
            "EXILED": "정배", "RELEASED": "방송(석방)", "FORMER_OFFICIAL": "전직(비현직)",
            "UNKNOWN": "미상"}
KIND_SYMBOL = {"PERSON": "circle", "PERSON_IDENTITY_SEGMENT": "star", "INSTITUTION": "square",
               "COLLECTIVE": "diamond", "COLLECTIVE_OR_UNNAMED": "diamond", "UNNAMED_PERSON": "circle-open"}
LANES = ["COURT · 선전관", "COURT · 별군직", "MILITARY · 백령첨사", "LOCAL · 중화부사",
         "LOCAL · 벽동군수", "LOCAL · 영흥부사", "NONE · 전 부사(비현직)"]
UNDATED_X = 1776.4   # '시점 미상' 열 (시간값 아님)


def lx(v):
    return gp.lx(v) if gp.is_day(v) else None


def esc(v) -> str:
    return html.escape(str(v))


def base_layout(fig, title, height):
    fig.update_layout(
        title=dict(text=title, x=0.01, font=dict(size=17, color=INK)),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, height=height,
        font=dict(family=FONT, size=12, color=INK2),
        hoverlabel=dict(bgcolor="white", font=dict(family=FONT, size=12, color=INK), align="left"),
        margin=dict(l=170, r=30, t=60, b=170),
        legend=dict(orientation="h", yanchor="top", y=-0.09, xanchor="left", x=0,
                    font=dict(size=11)),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor="#c3c2b7", tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor="#c3c2b7", tickfont=dict(color=INK2))


def year_axis(fig, lo, hi, row=None, col=None, title=True):
    kw = dict(range=[lo, hi], tickmode="array", tickvals=list(range(math.ceil(lo), int(hi) + 1)),
              ticktext=[str(y) for y in range(math.ceil(lo), int(hi) + 1)])
    if title:
        kw["title"] = dict(text="연도 (음력 날짜의 명목 소수연도 — 시각화용 파생값, 양력 환산 아님)",
                           font=dict(size=11, color=MUTED))
    if row:
        fig.update_xaxes(row=row, col=col, **kw)
    else:
        fig.update_xaxes(**kw)


def page(title: str, intro_html: str, figs: list, tail_html: str = "") -> str:
    parts = []
    for i, f in enumerate(figs):
        parts.append(f.to_html(full_html=False, include_plotlyjs=(i == 0), auto_play=False,
                               config={"responsive": True, "displaylogo": False}))
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
:root {{ color-scheme: light; --surface:{SURFACE}; --ink:{INK}; --ink2:{INK2}; --muted:{MUTED};
        --grid:{GRID}; --page:#f9f9f7; }}
body {{ margin:0; background:var(--page); color:var(--ink); font-family:{FONT}; line-height:1.55; }}
main {{ max-width:1320px; margin:0 auto; padding:20px 16px 48px; }}
h1 {{ font-size:1.45rem; margin:.2rem 0 .4rem; }}
h2 {{ font-size:1.1rem; margin:1.6rem 0 .4rem; }}
p, li {{ color:var(--ink2); font-size:.93rem; }}
.card {{ background:var(--surface); border:1px solid rgba(11,11,11,.10); border-radius:10px;
        padding:8px; margin:14px 0; overflow-x:auto; }}
.note {{ border-left:3px solid #eb6834; padding:6px 12px; background:#fff7f2; font-size:.9rem; }}
table {{ border-collapse:collapse; font-size:.84rem; width:100%; }}
th, td {{ border-bottom:1px solid var(--grid); padding:5px 8px; text-align:left; vertical-align:top; }}
th {{ color:var(--ink); font-weight:600; background:#f3f2ee; }}
td {{ color:var(--ink2); font-variant-numeric: tabular-nums; }}
code {{ font-size:.85em; background:#f0efec; padding:1px 4px; border-radius:4px; }}
</style></head>
<body><main>
<h1>{esc(title)}</h1>
{intro_html}
{''.join(f'<div class="card">{p}</div>' for p in parts)}
{tail_html}
</main></body></html>"""


def df_table(df: pd.DataFrame, cols: list[str], max_rows: int = 200) -> str:
    head = "".join(f"<th>{esc(c)}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{esc(r[c])}</td>" for c in cols) + "</tr>"
                   for _, r in df.head(max_rows).iterrows())
    return f'<div class="card"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


# ───────────────────────── Visualization 1: career storyline ─────────────────────────
def career_figure(res) -> go.Figure:
    ev = res["events"]
    career = res["career"]
    links = res["links"]
    E = ev.set_index("event_id")
    g = ev[ev.person_id.isin(gp.EGO) & ~ev.event_id.isin(gp.KIN_CONTEXT_ROWS)
           & ev.office_name.isin(gp.OFFICE_LANE.keys())].copy()
    g["lane"] = g.office_name.map(gp.OFFICE_LANE)

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        row_heights=[0.58, 0.27, 0.15],
                        subplot_titles=("① 관직·제도적 위치 (품계 순서 아님 — CSV에 품계 없음)",
                                        "② career_state 구간 (관직 level과 분리)",
                                        "③ 동일인 판단 세그먼트"))

    # ① storyline: EXACT_DAY 관측만 시간순으로 점선 연결 (사이 구간은 '미관측')
    exact = g[g.time_precision == "EXACT_DAY"].sort_values("plot_x_start")
    for seg, sub in exact.groupby("person_id"):
        fig.add_trace(go.Scatter(
            x=sub.plot_x_start, y=sub.lane, mode="lines",
            line=dict(color="#c3c2b7", width=1.5, dash="dot"), hoverinfo="skip",
            name="관측 간 연결선 (사이 재임 여부 미관측)", legendgroup="story",
            showlegend=seg == "GUSUN_PRE1793"), row=1, col=1)
    for state, sub in exact.groupby("career_state"):
        fig.add_trace(go.Scatter(
            x=sub.plot_x_start, y=sub.lane, mode="markers",
            marker=dict(size=11, color=STATE_COLOR[state], line=dict(color=SURFACE, width=2)),
            name=f"관측(일자 확정) · {STATE_KO[state]}", legendgroup=f"st_{state}",
            customdata=sub[["event_id", "record_date_raw", "office_name", "administrative_scope",
                            "court_proximity", "command_scope", "career_state", "career_state_after",
                            "location", "event_description", "source_title",
                            "evidence_grade"]].values,
            hovertemplate=("<b>%{customdata[2]}</b> · %{customdata[0]}<br>음력 %{customdata[1]} (EXACT_DAY)"
                           "<br>scope=%{customdata[3]} · court_proximity=%{customdata[4]}"
                           "<br>command_scope=%{customdata[5]}<br>career_state=%{customdata[6]}"
                           " → %{customdata[7]}<br>장소: %{customdata[8]}<br>%{customdata[9]}"
                           "<br>출처: %{customdata[10]} (grade %{customdata[11]})<extra></extra>")),
            row=1, col=1)
    # 월 단위 관측: 구간 막대 (중간점을 찍지 않음)
    month = g[g.time_precision == "YEAR_MONTH"]
    for _, r in month.iterrows():
        fig.add_trace(go.Scatter(
            x=[r.plot_x_start, r.plot_x_end], y=[r.lane, r.lane], mode="lines+markers",
            line=dict(color=STATE_COLOR[r.career_state], width=7),
            marker=dict(symbol="line-ns", size=14, line=dict(width=2, color=STATE_COLOR[r.career_state])),
            opacity=0.55, name="관측(월 단위 구간)", legendgroup="month",
            showlegend=bool(r.event_id == month.event_id.iloc[0]),
            hovertemplate=(f"<b>{esc(r.office_name)}</b> · {r.event_id}<br>음력 {r.record_date_raw} "
                           f"(YEAR_MONTH: {r.earliest_possible}~{r.latest_possible})"
                           f"<br>{esc(r.event_description)}<extra></extra>")), row=1, col=1)

    # ② career_state spells
    for _, s in career.iterrows():
        start = s.start if gp.is_day(s.start) else E.loc[s.evidence_start.split(";")[0], "earliest_possible"]
        x0, x_e1 = lx(start), lx(s.earliest_end)
        x_e2 = lx(s.latest_end)
        color = STATE_COLOR[s.career_state]
        yrow = "재임 상태" if s.career_state in ("ACTIVE", "FORMER_OFFICIAL") else "조사·처벌 상태"
        label = f"{STATE_KO[s.career_state]} · {s.location}"
        hover = (f"<b>{s.spell_id} {STATE_KO[s.career_state]} ({s.career_state})</b><br>"
                 f"{esc(s.office_or_status)} · {esc(s.location)}<br>"
                 f"시작: {s.start} ({s.start_precision})<br>종료: [{s.earliest_end}, {s.latest_end}]<br>"
                 f"근거: {s.evidence_start} → {s.evidence_end}<br>{esc(s.notes)}")
        if x_e1 is not None and x_e1 > x0:
            fig.add_trace(go.Bar(base=[x0], x=[x_e1 - x0], y=[yrow], orientation="h",
                                 marker=dict(color=color, line=dict(color=SURFACE, width=1)),
                                 width=0.6, text=[label] if (x_e1 - x0) > 1.2 else None,
                                 textposition="inside", insidetextanchor="start", textangle=0,
                                 textfont=dict(color="white", size=10), showlegend=False,
                                 hovertemplate=hover + "<extra></extra>"), row=2, col=1)
        else:
            fig.add_trace(go.Scatter(x=[x0], y=[yrow], mode="markers",
                                     marker=dict(symbol="line-ns", size=18,
                                                 line=dict(width=3, color=color)),
                                     showlegend=False, hovertemplate=hover + "<extra></extra>"),
                          row=2, col=1)
        if x_e1 is not None and x_e2 is not None and x_e2 > x_e1:
            fig.add_trace(go.Bar(base=[x_e1], x=[x_e2 - x_e1], y=[yrow], orientation="h",
                                 marker=dict(color="rgba(0,0,0,0)", line=dict(color=color, width=1),
                                             pattern=dict(shape="/", fgcolor=color, size=6, solidity=0.3)),
                                 width=0.6, showlegend=False,
                                 text=[f"{STATE_KO[s.career_state]} 종료 시점 미상"] if (x_e2 - x_e1) > 1.5 else None,
                                 textposition="inside", textangle=0, textfont=dict(color=INK2, size=10),
                                 hovertemplate=hover + "<br><i>빗금 = 종료 가능 구간</i><extra></extra>"),
                          row=2, col=1)
        if s.start_precision == "BEFORE":
            fig.add_trace(go.Scatter(x=[x0], y=[yrow], mode="markers",
                                     marker=dict(symbol="triangle-left-open", size=12, color=color),
                                     showlegend=False,
                                     hovertemplate=f"{s.spell_id}: 시작 미상 (≤ {start})<extra></extra>"),
                          row=2, col=1)
        if s.latest_end == gp.UNKNOWN:
            fig.add_trace(go.Scatter(x=[x0 + 0.15], y=[yrow], mode="markers",
                                     marker=dict(symbol="triangle-right-open", size=12, color=color),
                                     showlegend=False,
                                     hovertemplate=f"{s.spell_id}: 이후 OPEN (E083)<extra></extra>"),
                          row=2, col=1)
    for st in ["ACTIVE", "UNDER_INVESTIGATION", "IMPRISONED", "EXILED", "RELEASED", "FORMER_OFFICIAL"]:
        fig.add_trace(go.Bar(x=[None], y=[None], marker=dict(color=STATE_COLOR[st]),
                             name=f"상태: {STATE_KO[st]} ({st})", legendgroup=f"st_{st}"), row=2, col=1)
    fig.add_trace(go.Bar(x=[None], y=[None], name="빗금: 종료 가능 구간(미상)",
                         marker=dict(color="rgba(0,0,0,0)", line=dict(color=INK2, width=1),
                                     pattern=dict(shape="/", fgcolor=INK2, size=6, solidity=0.3))),
                  row=2, col=1)

    # ③ identity segments
    l00 = links[links.link_id == "L00"].iloc[0]
    seg_spans = [("GUSUN_PRE1793", "1777-09-11", "1787-01-03", "#2a78d6"),
                 ("GUSUN_1793PLUS", "1793-02-01", "1798-02-21", "#4a3aa7")]
    for name, a, b, c in seg_spans:
        fig.add_trace(go.Bar(base=[lx(a)], x=[lx(b) - lx(a)], y=["identity"], orientation="h",
                             marker=dict(color=c, opacity=0.35, line=dict(color=c, width=1)),
                             width=0.55, text=[name], textposition="inside",
                             textfont=dict(color=INK, size=11), showlegend=False,
                             hovertemplate=f"<b>{name}</b><br>기록 범위 {a} ~ {b}<extra></extra>"),
                      row=3, col=1)
    xa, xb = lx("1787-01-03"), lx("1793-02-22")
    fig.add_trace(go.Bar(base=[xa], x=[xb - xa], y=["identity"], orientation="h", width=0.55,
                         marker=dict(color="rgba(0,0,0,0)", line=dict(color="#eb6834", width=1),
                                     pattern=dict(shape="x", fgcolor="#eb6834", size=7, solidity=0.15)),
                         text=[f"L00 {l00.same_person_status} · T_release ∈ (1787-01-03, 1793-02-22) 미관측"],
                         textposition="inside", textfont=dict(color=INK, size=11), showlegend=False,
                         hovertemplate=(f"<b>동일인 연결 L00: {l00.same_person_status}</b><br>"
                                        f"지지: {esc(l00.supporting_evidence)}<br>"
                                        f"반대 증거: {esc(l00.contradicting_evidence)}<br>"
                                        f"긴장: {esc(l00.tension_evidence)}<br>"
                                        f"결락: {esc(l00.missing_evidence)}<extra></extra>")),
                  row=3, col=1)
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(LANES)), row=1, col=1)
    fig.update_yaxes(categoryorder="array", categoryarray=["조사·처벌 상태", "재임 상태"], row=2, col=1)
    base_layout(fig, "구순(具純) Temporal Career Storyline — 관직·career_state·동일인 세그먼트", 980)
    fig.update_layout(barmode="overlay", bargap=0.1)
    for r in (1, 2, 3):
        year_axis(fig, 1777, 1799, row=r, col=1, title=(r == 3))
    return fig


# ───────────────────────── Visualization 2: multiplex ego network ─────────────────────────
def edge_hover(e, names) -> str:
    return (f"<b>{esc(names.get(e.source_person, e.source_person))} → "
            f"{esc(names.get(e.target_person, e.target_person))}</b><br>"
            f"relation_type: {e.relation_type} ({e.relation_group})<br>subtype: {esc(e.relation_subtype)}<br>"
            f"start: {e.start_date} [{e.earliest_start}, {e.latest_start}]<br>"
            f"end: {e.end_date} [{e.earliest_end}, {e.latest_end}]<br>"
            f"time_precision: {e.time_precision} · record_date: {e.record_date}<br>"
            f"confidence: {esc(e.confidence)} · evidence_status: {esc(e.evidence_status)}<br>"
            f"source_event: {e.source_event_id} · {esc(e.source_title)}<br>"
            f"<i>{esc(str(e.evidence_summary)[:160])}</i>")


def alter_timeline(res, zoom: bool = False) -> go.Figure:
    edges, persons = res["edges"], res["persons"]
    names = persons.set_index("person_id").name_ko.to_dict()
    ego_e = edges[edges.source_person.isin(gp.EGO) | edges.target_person.isin(gp.EGO)].copy()
    if zoom:  # 1793 사건만 확대 (세그먼트 1793+, 1793년 기록)
        ego_e = ego_e[(ego_e.source_person == "GUSUN_1793PLUS") | (ego_e.target_person == "GUSUN_1793PLUS")]
        ego_e = ego_e[ego_e.phase == "kim_case_1793"]
    ego_e["alter"] = ego_e.apply(lambda e: e.target_person if e.source_person in gp.EGO else e.source_person,
                                 axis=1)
    ego_e["ego"] = ego_e.apply(lambda e: e.source_person if e.source_person in gp.EGO else e.target_person,
                               axis=1)

    def first_x(sub):
        xs = [lx(v) for v in list(sub.earliest_start) + list(sub.latest_start) + list(sub.record_date)]
        xs = [x for x in xs if x is not None]
        return min(xs) if xs else 0

    order = (ego_e.groupby(["ego", "alter"]).apply(first_x, include_groups=False)
             .reset_index(name="fx").sort_values(["ego", "fx"], ascending=[True, True]))
    order["ego_rank"] = order.ego.map({"GUSUN_PRE1793": 0, "GUSUN_1793PLUS": 1})
    order = order.sort_values(["ego_rank", "fx"])
    rows = [f"{a}|{e}" for e, a in zip(order.ego, order.alter)]
    ypos = {k: len(rows) - i for i, k in enumerate(rows)}
    ylabels = [f"{names.get(k.split('|')[0], k.split('|')[0])}  ({'PRE1793' if 'PRE' in k else '1793+'})"
               for k in rows]
    goff = {g: (i - 3.5) * 0.09 for i, g in enumerate(gp.GROUP_ORDER)}

    fig = go.Figure()
    undated_x = gp.lx("1793-01-20") if zoom else UNDATED_X
    half = 0.04 if zoom else 0.5
    fig.add_vrect(x0=undated_x - half, x1=undated_x + half, fillcolor="#f0efec", line_width=0, layer="below",
                  annotation_text="시점 미상", annotation_position="top left",
                  annotation_font=dict(size=10, color=MUTED))
    if not zoom:
        fig.add_vrect(x0=gp.lx("1787-01-03"), x1=gp.lx("1793-02-22"), fillcolor="#fff1ea", line_width=0, layer="below",
                      opacity=0.6, annotation_text="1787→1793 미관측 구간 (해배 기록 없음)",
                      annotation_position="top left", annotation_font=dict(size=10, color=INK2))
    else:
        for d, lab in [("1793-02-22", "도난 보고"), ("1793-03-04", "김명신 체포명령"),
                       ("1793-05-12", "관찰사 장계"), ("1793-05-27", "암행어사 보고"),
                       ("1793-06-13", "최종 판정")]:
            fig.add_vline(x=gp.lx(d), line=dict(color="#c3c2b7", width=1, dash="dot"), layer="below",
                          annotation_text=f"{d} {lab}", annotation_position="top",
                          annotation_font=dict(size=9, color=MUTED), annotation_textangle=-30)
    shown = set()
    for _, e in ego_e.iterrows():
        y = ypos[f"{e.alter}|{e.ego}"] + goff[e.relation_group]
        col = GROUP_COLOR[e.relation_group]
        dash = REL_DASH.get(e.relation_type, "solid")
        es, ls_, ee, le = (lx(e.earliest_start), lx(e.latest_start), lx(e.earliest_end), lx(e.latest_end))
        hov = edge_hover(e, names) + "<extra></extra>"
        leg = e.relation_group not in shown
        shown.add(e.relation_group)
        common = dict(name=GROUP_KO[e.relation_group], legendgroup=e.relation_group, showlegend=leg)
        lo = es if es is not None else ls_
        hi = le if le is not None else (ee if ee is not None else ls_)
        if lo is None and hi is None and gp.MONTH_RE.match(str(e.record_date)):
            # 관계 시점 미상 + 월 단위 관측: 관측 월 전체를 가는 점선으로만 표시
            m0, m1 = gp.month_bounds(e.record_date)
            fig.add_trace(go.Scatter(x=[lx(m0), lx(m1)], y=[y, y], mode="lines+markers",
                                     line=dict(color=col, width=2, dash="dot"),
                                     marker=dict(symbol="diamond-open", size=9, color=col),
                                     hovertemplate=hov.replace("<extra>", "<br><b>관계 시작·종료 미상</b> — "
                                                               "표시 구간=관측(기록) 월<extra>"), **common))
            continue
        if lo is None and hi is None:  # 완전 무시점 관계
            rx = lx(e.record_date)
            x, sym = (rx, "diamond-open") if rx is not None else (undated_x, "x-open")
            fig.add_trace(go.Scatter(x=[x], y=[y], mode="markers",
                                     marker=dict(symbol=sym, size=12, color=col, line=dict(width=2)),
                                     hovertemplate=hov.replace("<extra>", "<br><b>관계 시작·종료 미상</b> — "
                                                               + ("표시 위치=관측(기록) 시점" if rx else
                                                                  "표시 위치는 시간값 아님") + "<extra>"),
                                     **common))
            continue
        if lo is not None and hi is not None and hi > lo + 1e-9:
            fig.add_trace(go.Scatter(x=[lo, hi], y=[y, y], mode="lines",
                                     line=dict(color=col, width=5, dash=dash), opacity=0.6,
                                     hovertemplate=hov, **common))
            common["showlegend"] = False
        else:
            x = lo if lo is not None else hi
            fig.add_trace(go.Scatter(x=[x], y=[y], mode="markers",
                                     marker=dict(symbol="circle", size=9, color=col,
                                                 line=dict(color=SURFACE, width=1.5)),
                                     hovertemplate=hov, **common))
            common["showlegend"] = False
        if es is None and ls_ is not None:  # 시작 미상
            fig.add_trace(go.Scatter(x=[ls_], y=[y], mode="markers",
                                     marker=dict(symbol="triangle-left-open", size=11, color=col),
                                     hovertemplate=f"시작 미상 (≤ {e.latest_start})<extra></extra>",
                                     **common))
        if e.end_date == gp.OPEN:
            xx = hi if hi is not None else lo
            fig.add_trace(go.Scatter(x=[xx], y=[y], mode="markers",
                                     marker=dict(symbol="triangle-right-open", size=11, color=col),
                                     hovertemplate="종료 OPEN (종료 기록 없음)<extra></extra>", **common))
    if zoom:
        base_layout(fig, "②-b 1793년 김명신 사건 확대 (1793-01 ~ 1793-07, 음력) — 구순 1793+ 세그먼트",
                    max(520, 30 * len(rows) + 260))
        months = [f"1793-{m:02d}-01" for m in range(1, 8)]
        fig.update_xaxes(range=[undated_x - 0.06, gp.lx("1793-06-30")], tickmode="array",
                         tickvals=[gp.lx(m) for m in months], ticktext=[m[:7] for m in months],
                         title=dict(text="음력 월 (명목 축)", font=dict(size=11, color=MUTED)))
        fig.update_layout(margin=dict(t=120))
    else:
        base_layout(fig, "②-a Temporal Multiplex Ego Timeline — 구순과 각 인물의 관계 (X=시간, 행=상대 인물)",
                    max(560, 26 * len(rows) + 230))
        year_axis(fig, UNDATED_X - 0.6, 1799)
    fig.update_yaxes(tickmode="array", tickvals=[ypos[k] for k in rows], ticktext=ylabels,
                     range=[0.3, len(rows) + 0.7])
    return fig


def layout_positions(edges: pd.DataFrame) -> dict:
    G = nx.Graph()
    for _, e in edges.iterrows():
        G.add_edge(e.source_person, e.target_person)
    fixed = {"GUSUN_PRE1793": (-1.0, 0.0), "GUSUN_1793PLUS": (1.0, 0.0), "P_JEONGJO": (0.0, 0.55)}
    pos = nx.spring_layout(G, pos=fixed, fixed=list(fixed), seed=7, k=0.45, iterations=300)
    return {k: (float(v[0]), float(v[1])) for k, v in pos.items()}


def node_hover(p) -> str:
    st = str(p.known_status)
    st = st if len(st) < 260 else st[:260] + "…"
    return (f"<b>{esc(p.name_ko)}</b> {esc(p.name_hanja) if p.name_hanja != 'NA' else ''}<br>"
            f"id: {p.person_id} · kind: {p.node_kind}<br>당시 관직/신분(CSV): {esc(st)}<br>"
            f"관측: {p.first_seen} ~ {p.last_seen} · CSV 행 {p.n_csv_rows}<br>"
            f"biographical_coverage_score: {p.biographical_coverage_score} (관측 밀도, 중요도 아님)<br>"
            f"identity: {esc(p.identity_confidence)}<br>{esc(p.notes) if p.notes != 'NA' else ''}")


def multiplex_graph(res, pos) -> go.Figure:
    edges, persons = res["edges"], res["persons"]
    P = persons.set_index("person_id")
    names = P.name_ko.to_dict()
    fig = go.Figure()
    pair_count = {}
    for g in gp.GROUP_ORDER:
        sub = edges[edges.relation_group == g]
        xs, ys, mx, my, mh, ang, sym = [], [], [], [], [], [], []
        for _, e in sub.iterrows():
            (x0, y0), (x1, y1) = pos[e.source_person], pos[e.target_person]
            key = tuple(sorted([e.source_person, e.target_person]))
            k = pair_count.get(key, 0)
            pair_count[key] = k + 1
            # 같은 인물쌍의 여러 관계(multiplex)는 곡선 오프셋으로 분리
            off = (k - 0) * 0.035 * (1 if k % 2 == 0 else -1)
            dx, dy = x1 - x0, y1 - y0
            L = math.hypot(dx, dy) or 1
            nx_, ny_ = -dy / L, dx / L
            cx, cy = (x0 + x1) / 2 + nx_ * off * 3, (y0 + y1) / 2 + ny_ * off * 3
            for t in [i / 8 for i in range(9)]:
                xs.append((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t ** 2 * x1)
                ys.append((1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t ** 2 * y1)
            xs.append(None)
            ys.append(None)
            mx.append(0.25 * x0 + 0.5 * cx + 0.25 * x1)
            my.append(0.25 * y0 + 0.5 * cy + 0.25 * y1)
            mh.append(edge_hover(e, names))
            ang.append(math.degrees(math.atan2(dx, dy)))
            sym.append("arrow" if e.directed else "circle")
        if not len(sub):
            continue
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=GROUP_COLOR[g], width=1.6),
                                 opacity=0.7, hoverinfo="skip", name=GROUP_KO[g], legendgroup=g))
        fig.add_trace(go.Scatter(x=mx, y=my, mode="markers",
                                 marker=dict(symbol=sym, angle=ang, size=10, color=GROUP_COLOR[g],
                                             line=dict(color=SURFACE, width=1)),
                                 hovertemplate="%{text}<extra></extra>", text=mh, showlegend=False,
                                 legendgroup=g))
    (ax, ay), (bx, by) = pos["GUSUN_PRE1793"], pos["GUSUN_1793PLUS"]
    l00 = res["links"].set_index("link_id").loc["L00"]
    fig.add_trace(go.Scatter(x=[ax, bx], y=[ay, by], mode="lines",
                             line=dict(color="#eb6834", width=2.5, dash="dash"),
                             name=f"동일인 연결 L00 ({l00.same_person_status}, 병합 안 함)",
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[(ax + bx) / 2], y=[(ay + by) / 2 - 0.04], mode="text",
                             text=[f"L00 {l00.same_person_status}"], textfont=dict(color="#eb6834", size=11),
                             showlegend=False, hoverinfo="skip"))
    for kind, sub in persons[persons.in_network].groupby("node_kind"):
        xs = [pos[p][0] for p in sub.person_id]
        ys = [pos[p][1] for p in sub.person_id]
        ego = kind == "PERSON_IDENTITY_SEGMENT"
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers+text",
            marker=dict(symbol=KIND_SYMBOL.get(kind, "circle"), size=24 if ego else 13,
                        color="#0b0b0b" if ego else "white", line=dict(color=INK, width=1.5)),
            text=[("구순 " + ("PRE1793" if "PRE" in p else "1793+")) if ego else names[p]
                  for p in sub.person_id],
            textposition="top center", textfont=dict(size=11 if ego else 10, color=INK),
            hovertemplate="%{customdata}<extra></extra>",
            customdata=[node_hover(r) for _, r in sub.iterrows()],
            name=f"노드: {kind}", legendgroup="nodes"))
    base_layout(fig, "③ Multiplex Ego Network (전체 기간 집계 · 범례 클릭으로 관계 layer 켜고 끄기)", 820)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    fig.update_layout(margin=dict(l=20, r=20, t=60, b=150))
    return fig


def composition_figure(res) -> go.Figure:
    comp = res["comp"]
    fig = go.Figure()
    for g in gp.GROUP_ORDER:
        fig.add_trace(go.Bar(x=comp.period, y=comp[f"ego_{g}"], name=GROUP_KO[g],
                             marker=dict(color=GROUP_COLOR[g], line=dict(color=SURFACE, width=2)),
                             hovertemplate=f"{GROUP_KO[g]}<br>%{{x}}: %{{y}}건<extra></extra>"))
    fig.update_layout(barmode="stack")
    base_layout(fig, "④ 시기별 구순 ego edge 구성 (관계군별 건수 — 관측량이지 실제 관계량이 아님)", 470)
    fig.update_layout(margin=dict(l=60, r=20, t=60, b=230))
    fig.update_yaxes(title=dict(text="ego edge 수", font=dict(size=11, color=MUTED)))
    return fig


# ───────────────────────── Visualization 3: dynamic network ─────────────────────────
def frame_key(e_record: str):
    """(정렬용 서수, 라벨). 월 단위 프레임의 월 내 위치는 미정 → early=1일, late·무한정어=30일로 배치."""
    if gp.is_day(e_record):
        return gp.lord(e_record), e_record
    m = gp.QUAL_RE.match(e_record or "")
    if m:
        y, mo, q = m.groups()
        d = "01" if q == "early" else "30"
        return gp.lord(f"{y}-{mo}-{d}"), f"{y}-{mo} ({q}; 월 단위)"
    if gp.MONTH_RE.match(e_record or ""):
        return gp.lord(f"{e_record}-30"), f"{e_record} (월 단위 · 월 내 순서 미정)"
    return None, None


CARRY_TYPES = {"KINSHIP", "HOUSEHOLD", "NEIGHBOR"}


def dynamic_figure(res, pos) -> go.Figure:
    edges, persons, ev = res["edges"], res["persons"], res["events"]
    P = persons.set_index("person_id", drop=False)
    names = P.name_ko.to_dict()
    edges = edges.copy()
    edges["fk"] = edges.record_date.map(lambda v: frame_key(v)[0])
    edges["fl"] = edges.record_date.map(lambda v: frame_key(v)[1])
    g_ev = ev[ev.person_id.isin(gp.EGO) & (ev.phase != "gap") & ~ev.event_id.isin(gp.KIN_CONTEXT_ROWS)].copy()
    g_ev["fk"] = g_ev.record_date_raw.map(lambda v: frame_key(v)[0])
    g_ev["fl"] = g_ev.record_date_raw.map(lambda v: frame_key(v)[1])
    frames_idx = (pd.concat([edges[["fk", "fl"]], g_ev[["fk", "fl"]]]).dropna()
                  .drop_duplicates().sort_values("fk"))
    undated = edges[edges.fk.isna()]

    def edge_xy(sub, curve=0.0):
        xs, ys, mx, my, mh, mc, ang, sym = [], [], [], [], [], [], [], []
        for _, e in sub.iterrows():
            (x0, y0), (x1, y1) = pos[e.source_person], pos[e.target_person]
            xs += [x0, x1, None]
            ys += [y0, y1, None]
            mx.append(x0 * 0.45 + x1 * 0.55)
            my.append(y0 * 0.45 + y1 * 0.55)
            mh.append(edge_hover(e, names))
            mc.append(GROUP_COLOR[e.relation_group])
            ang.append(math.degrees(math.atan2(x1 - x0, y1 - y0)))
            sym.append("arrow" if e.directed else "circle")
        return xs, ys, mx, my, mh, mc, ang, sym

    def build_frame(i, fk, fl):
        active = edges[edges.fk == fk]
        seen_edges = edges[(edges.fk < fk) | edges.fk.isna()]
        cur_seg = set()
        for _, e in active.iterrows():
            cur_seg |= {e.source_person, e.target_person} & gp.EGO
        evs = g_ev[g_ev.fk == fk]
        cur_seg |= set(evs.person_id)
        if not cur_seg:
            cur_seg = {"GUSUN_PRE1793"}
        carried = seen_edges[seen_edges.relation_type.isin(CARRY_TYPES) &
                             (seen_edges.source_person.isin(cur_seg) | seen_edges.target_person.isin(cur_seg))]
        carried = carried[~carried.edge_id.isin(active.edge_id)]
        traces = []
        cx, cy, cmx, cmy, cmh, _, _, _ = edge_xy(carried)
        traces.append(go.Scatter(x=cx, y=cy, mode="lines",
                                 line=dict(color="#c3c2b7", width=1.2, dash="dot"), hoverinfo="skip",
                                 name="이전 관측된 지속관계(친족·가내·이웃) — 이 시점 미관측"))
        traces.append(go.Scatter(x=cmx, y=cmy, mode="markers", marker=dict(size=6, color="#c3c2b7"),
                                 text=[h + "<br><b>이 프레임 시점에는 관측되지 않음</b>" for h in cmh],
                                 hovertemplate="%{text}<extra></extra>", showlegend=False))
        for g in gp.GROUP_ORDER:
            sub = active[active.relation_group == g]
            xs, ys, *_ = edge_xy(sub)
            traces.append(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=GROUP_COLOR[g], width=2.6),
                                     hoverinfo="skip", name=GROUP_KO[g], legendgroup=g))
        _, _, mx, my, mh, mc, ang, sym = edge_xy(active)
        traces.append(go.Scatter(x=mx, y=my, mode="markers",
                                 marker=dict(size=12, color=mc, symbol=sym, angle=ang,
                                             line=dict(color=SURFACE, width=1)),
                                 text=mh, hovertemplate="%{text}<extra></extra>", showlegend=False))
        act_nodes = set(active.source_person) | set(active.target_person) | cur_seg
        seen_nodes = (set(seen_edges.source_person) | set(seen_edges.target_person)) - act_nodes
        gx = [pos[n][0] for n in seen_nodes if n in pos]
        gy = [pos[n][1] for n in seen_nodes if n in pos]
        traces.append(go.Scatter(x=gx, y=gy, mode="markers",
                                 marker=dict(size=9, color="#e1e0d9", line=dict(color="#c3c2b7", width=1)),
                                 text=[names.get(n, n) for n in seen_nodes if n in pos],
                                 hovertemplate="%{text} (이전 프레임에서 관측)<extra></extra>",
                                 name="이전에 관측된 인물(현재 미관측)"))
        an = [n for n in act_nodes if n in pos]
        status_by_ego = {}
        for _, r in evs.iterrows():
            status_by_ego[r.person_id] = f"{r.office_name} / {r.career_state}→{r.career_state_after}"
        traces.append(go.Scatter(
            x=[pos[n][0] for n in an], y=[pos[n][1] for n in an], mode="markers+text",
            marker=dict(size=[26 if n in gp.EGO else 14 for n in an],
                        symbol=[KIND_SYMBOL.get(P.loc[n, "node_kind"], "circle") for n in an],
                        color=["#0b0b0b" if n in gp.EGO else "white" for n in an],
                        line=dict(color=INK, width=1.5)),
            text=[("구순 " + ("PRE1793" if "PRE" in n else "1793+")) if n in gp.EGO else names[n] for n in an],
            textposition="top center", textfont=dict(size=11, color=INK),
            customdata=[node_hover(P.loc[n]) + (f"<br><b>이 시점 상태: {esc(status_by_ego[n])}</b>"
                                                 if n in status_by_ego else "") for n in an],
            hovertemplate="%{customdata}<extra></extra>", name="이 시점 관측 인물"))
        ev_txt = "; ".join(f"{r.event_id}:{r.relation_type_raw}" for _, r in evs.iterrows())
        n_edges = len(active)
        stat = " | ".join(f"{'PRE1793' if 'PRE' in k else '1793+'}: {esc(v)}" for k, v in status_by_ego.items())
        title = (f"<b>{fl}</b> · 이 시점 관측 edge {n_edges}건"
                 + (f"<br><span style='font-size:11px'>구순 상태 — {stat}</span>" if stat else "")
                 + (f"<br><span style='font-size:10px;color:{MUTED}'>구순 사건: {esc(ev_txt[:150])}</span>"
                    if ev_txt else ""))
        return traces, title

    frames, first_traces, first_title = [], None, None
    steps = []
    for i, (_, fr) in enumerate(frames_idx.iterrows()):
        traces, title = build_frame(i, fr.fk, fr.fl)
        name = f"f{i:02d}"
        frames.append(go.Frame(data=traces, name=name,
                               layout=go.Layout(annotations=[dict(text=title, x=0.0, y=1.11, xref="paper",
                                                                  yref="paper", showarrow=False,
                                                                  align="left", font=dict(size=13, color=INK))])))
        steps.append(dict(method="animate", label=fr.fl.split(" ")[0],
                          args=[[name], dict(mode="immediate", frame=dict(duration=0, redraw=True),
                                             transition=dict(duration=0))]))
        if first_traces is None:
            first_traces, first_title = traces, title
    fig = go.Figure(data=first_traces, frames=frames)
    (ax, ay), (bx, by) = pos["GUSUN_PRE1793"], pos["GUSUN_1793PLUS"]
    fig.add_shape(type="line", x0=ax, y0=ay, x1=bx, y1=by, line=dict(color="#eb6834", width=1.5, dash="dash"),
                  layer="below")
    base_layout(fig, "구순(具純) Dynamic Network — CSV에 자료가 있는 시점만 프레임으로 구성", 860)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    fig.update_xaxes(range=[min(xs) - 0.15, max(xs) + 0.15])
    fig.update_yaxes(range=[min(ys) - 0.12, max(ys) + 0.15])
    fig.update_layout(
        margin=dict(l=20, r=20, t=150, b=40),
        annotations=[dict(text=first_title, x=0.0, y=1.11, xref="paper", yref="paper", showarrow=False,
                          align="left", font=dict(size=13, color=INK))],
        legend=dict(orientation="h", y=-0.02, yanchor="top"),
        updatemenus=[dict(type="buttons", direction="left", x=0.0, y=-0.08, xanchor="left",
                          buttons=[dict(label="▶ 재생", method="animate",
                                        args=[None, dict(frame=dict(duration=1300, redraw=True),
                                                         fromcurrent=True, transition=dict(duration=0))]),
                                   dict(label="❚❚ 정지", method="animate",
                                        args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))])])],
        sliders=[dict(active=0, steps=steps, x=0.12, y=-0.04, len=0.88,
                      currentvalue=dict(prefix="시점(음력): ", font=dict(size=12, color=INK)),
                      tickcolor=MUTED, font=dict(size=9, color=MUTED))],
    )
    fig._n_frames = len(frames)  # README 용
    fig._frame_labels = list(frames_idx.fl)
    fig._undated = list(undated.edge_id)
    return fig


# ───────────────────────── 빌드 ─────────────────────────
def build_all(res):
    pos = layout_positions(res["edges"])
    res["layout_positions"] = pos

    f1 = career_figure(res)
    intro1 = """
<p>X축은 음력 날짜를 1년=360일로 놓은 <b>명목 소수연도</b>(시각화용 파생값)입니다. Y축(①)은 <b>품계 순서가 아니라</b>
제도적 위치 범주(COURT / MILITARY / LOCAL / NONE)이며, CSV에는 품계 정보가 없어 rank_level을 계산하지 않았습니다.
정배·수감·조사 같은 처벌 상태는 ①에 넣지 않고 ② career_state 띠로만 표시합니다.</p>
<ul>
<li>● 채운 점 = 일자가 확정된 관측(EXACT_DAY). 점선은 관측 사이를 이은 것일 뿐 그 사이 재임을 뜻하지 않습니다.</li>
<li>굵은 반투명 막대 = 월 단위 날짜(YEAR_MONTH)의 가능 구간. 중간점을 찍지 않았습니다.</li>
<li>② 빗금 = 상태 종료 시점의 가능 구간(미상). ◁ = 시작 미상, ▷ = 이후 OPEN.</li>
<li>③ 주황 X 빗금 = 1787 제주 정배와 1793 덕평 거주 사이의 미관측 구간. 두 세그먼트는 병합하지 않았고 연결 판정은 identity_links의 L00입니다.</li>
</ul>"""
    tail1 = "<h2>career_state 구간 표</h2>" + df_table(
        res["career"], ["spell_id", "person_id", "career_state", "office_or_status", "location", "start",
                        "start_precision", "earliest_end", "latest_end", "evidence_start", "evidence_end", "notes"])
    (OUT / "gusun_temporal_career.html").write_text(
        page("구순 Temporal Career Storyline", intro1, [f1], tail1), encoding="utf-8")

    f2a = alter_timeline(res)
    f2z = alter_timeline(res, zoom=True)
    f2b = multiplex_graph(res, pos)
    f2c = composition_figure(res)
    intro2 = """
<p class="note"><b>주의:</b> 본 네트워크의 연결도와 중심성은 실제 역사적 관계뿐 아니라 기록 보존량과 행정문서의 관측 편향을 반영합니다.
1793년 사건의 인물이 많아 보이는 것은 형사 기록이 상세하기 때문이며, 그 자체로 사회관계가 더 많았다는 뜻이 아닙니다.</p>
<ul>
<li>색 = 관계군(8개), 같은 군 안의 세부 유형은 선 모양(점선·파선)으로 구분합니다. 범례를 클릭하면 layer를 켜고 끌 수 있습니다.</li>
<li>타임라인(②)의 행은 상대 인물이며 구순은 <b>PRE1793 / 1793+ 두 세그먼트로 분리</b>되어 있습니다 (동일인 병합 안 함).</li>
<li>가로 막대 = 관계 발생의 가능 구간, 점 = 일자 확정, ◁ = 시작 미상, ▷ = 종료 OPEN, ◇ = 관계의 시작·종료는 모르고 기록에서 관측된 시점만 앎.
  왼쪽 회색 열 '시점 미상'은 시간값이 아닙니다.</li>
<li>네트워크 그래프(③)의 노드 크기는 일정합니다 — 중심성으로 크기를 키우지 않았습니다. 화살표 = 방향 있는 관계.</li>
</ul>"""
    trans = res["trans"]
    tail2 = ("<h2>관계 유형 전이 (같은 인물쌍)</h2>" +
             df_table(trans, ["pair", "transition_compact", "transition_detail", "ordering_caveats"]) +
             "<h2>시기별 구성 (ego edge 수)</h2>" +
             df_table(res["comp"], ["period", "n_edges_all", "n_edges_ego", "n_alters_ego"] +
                      [f"ego_{g}" for g in gp.GROUP_ORDER]))
    (OUT / "gusun_temporal_multiplex_network.html").write_text(
        page("구순 Temporal Multiplex Ego Network", intro2, [f2a, f2z, f2b, f2c], tail2), encoding="utf-8")

    f3 = dynamic_figure(res, pos)
    res["dynamic_frames"] = f3._frame_labels
    intro3 = f"""
<p>프레임은 CSV에 관계 또는 구순 사건이 실제로 기록된 시점만으로 만들었습니다(총 {f3._n_frames}개). 빈 연도는 넣지 않았습니다.
월 단위 기록의 프레임은 월 안의 위치를 모르므로 'early'는 월초, 그 외는 월말에 배치했습니다(시각화용 순서 규칙).</p>
<ul><li>굵은 색 선 = 그 시점 기록에서 관측된 관계. 회색 점선 = 이전에 관측된 친족·가내·이웃 관계(그 시점에는 미관측; 지속 여부 미상).</li>
<li>회색 노드 = 이전 프레임에서 관측됐으나 현재 프레임에는 없음 — <b>관계 종료를 뜻하지 않습니다.</b></li>
<li>시점이 전혀 없는 관계(구세덕–구순 KINSHIP)는 1777년 이후 프레임에서 '이전 관측' 점선으로만 보입니다.</li>
<li>주황 점선 = 두 구순 세그먼트 사이 동일인 연결(L00, 병합 안 함).</li></ul>"""
    (OUT / "gusun_dynamic_network.html").write_text(
        page("구순 Dynamic Network", intro3, [f3]), encoding="utf-8")
    return res
