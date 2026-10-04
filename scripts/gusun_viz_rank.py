"""관직 법정 품계(lookup)를 결합한 경력 storyline: output/gusun_temporal_career_with_rank.html

① 고정 품계 관직 — Y = rank_numeric (정렬용 숫자; 위쪽이 높은 품계)
② 가변·무품 직함 — 별도 categorical lane (수치축에 넣지 않음)
③ career_state band — 전직·정배·수금 등 (관직 축과 분리)
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import gusun_office_rank as gor
import gusun_pipeline as gp
import gusun_viz as gv

VAR_LANES = ["COURT_MILITARY_VARIABLE", "SPECIAL_MISSION", "MILITARY_STAFF", "CLERICAL"]
VAR_LANE_KO = {"COURT_MILITARY_VARIABLE": "COURT_MILITARY_VARIABLE<br>(선전관·별군직)",
               "SPECIAL_MISSION": "SPECIAL_MISSION<br>(암행·안핵어사)",
               "MILITARY_STAFF": "MILITARY_STAFF<br>(비장·장교·교졸)", "CLERICAL": "CLERICAL<br>(영리)"}
OTHER_COLOR = "#898781"


def nz(v):
    return "NA" if v is None or (isinstance(v, float) and pd.isna(v)) else v


def hover(r, who: str) -> str:
    def h(v):
        return gv.esc(nz(v))
    return (f"<b>{h(r.focal_raw_office_status)}</b> — {h(who)}<br>"
            f"날짜(음력): {r.date_lunar} ({r.time_precision}) · {r.event_id}<br>"
            f"원문 직함: {h(r.focal_raw_office_status)}<br>"
            f"정규화 직함: {h(r.normalized_office_title)} {h(r.office_title_hanja)}<br>"
            f"법정 품계(관직 자체): {h(r.statutory_rank)} · rank_numeric={h(r.rank_numeric)} ({h(r.rank_fixedness)})<br>"
            f"행정 범위: {h(r.administrative_scope)} · record_type: {h(r.record_type)}<br>"
            f"career_state: {h(r.career_state)} → {h(r.career_state_after)}<br>"
            f"출처(사건): {h(r.source_name)} · grade {h(r.evidence_grade)}<br>"
            f"lookup 매칭: {h(r.office_lookup_match_status)} · verification: {h(r.office_lookup_verification_status)}<br>"
            f"개인 품계(personal_rank): {h(r.personal_rank)}<br>"
            f"<i>{gv.esc(str(r.event_summary)[:140])}</i>")


def other_party_rows(joined: pd.DataFrame) -> pd.DataFrame:
    """구순이 아닌 인물의 관직 관측 (subject/object 각각). 기본 숨김 trace 용."""
    rows = []
    for _, r in joined.iterrows():
        for s in ("subject", "object"):
            pid = r[f"{s}_id"]
            if pid == "P_GUSUN" or r[f"{s}_office_lookup_match_status"] not in ("EXACT", "NORMALIZED"):
                continue
            d = r.copy()
            d["who"] = f"{r[f'{s}_name_ko']}({pid})"
            d["focal_raw_office_status"] = r[f"{s}_office_status"]
            for c in gor.LOOKUP_COLS:
                d[c] = r[f"{s}_{c}"]
            d["office_lookup_match_status"] = r[f"{s}_office_lookup_match_status"]
            d["office_lookup_verification_status"] = r[f"{s}_verification_status"]
            former = d["rank_fixedness"] == "FORMER_OFFICE"
            d["career_state"] = "FORMER_OFFICIAL" if former else gp.UNKNOWN
            d["career_state_after"] = d["career_state"]
            if former:
                d["rank_numeric"] = None
            d["personal_rank"] = gp.NA
            d["lane"] = gor.variable_lane(d) if pd.isna(d["rank_numeric"]) else None
            rows.append(d)
    return pd.DataFrame(rows)


def figure(res, rk) -> go.Figure:
    J = rk["joined"]
    career = res["career"]
    E = res["events"].set_index("event_id")
    g = J[J.focal_person_id.isin(gp.EGO) & J.office_lookup_match_status.isin(["EXACT", "NORMALIZED"])
          & ~J.event_id.isin(gp.KIN_CONTEXT_ROWS)].copy()
    g["who"] = g.focal_person_id.map(lambda p: f"구순 {('PRE1793' if 'PRE' in p else '1793+')}")
    fixed = g[g.rank_numeric.notna()]
    var = g[g.rank_numeric.isna() & (g.rank_fixedness != "FORMER_OFFICE")].copy()
    var["lane"] = var.apply(gor.variable_lane, axis=1)
    others = other_party_rows(J)

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        row_heights=[0.42, 0.28, 0.30],
                        subplot_titles=("① 고정 품계 관직 — 관직 자체의 법정 품계 (개인 품계 아님 · Y는 정렬용)",
                                        "② 가변·무품 직함 — 수치축과 분리된 category lane",
                                        "③ career_state band — 전직·조사·수금·정배 (관직 축과 분리)"))

    # ① 고정 품계: 구순
    for prec, sub in fixed.groupby("time_precision"):
        if prec == "EXACT_DAY":
            sub = sub.sort_values("plot_x_start")
            first_ids = set(sub.drop_duplicates("normalized_office_title").event_id)
            fig.add_trace(go.Scatter(x=sub.plot_x_start, y=sub.rank_numeric, mode="lines",
                                     line=dict(color="#c3c2b7", width=1.5, dash="dot"), hoverinfo="skip",
                                     name="관측 간 연결선 (사이 재임 미관측)"), row=1, col=1)
            for state, ss in sub.groupby("career_state"):
                fig.add_trace(go.Scatter(
                    x=ss.plot_x_start, y=ss.rank_numeric, mode="markers+text",
                    marker=dict(size=12, color=gv.STATE_COLOR[state], line=dict(color=gv.SURFACE, width=2)),
                    text=[f"{t} ({sr})" if eid in first_ids else "" for t, sr, eid in
                          zip(ss.normalized_office_title, ss.statutory_rank, ss.event_id)],
                    textposition=["bottom right" if "+" in str(t) else "top center"
                                  for t in ss.normalized_office_title],
                    textfont=dict(size=10, color=gv.INK2),
                    customdata=[hover(r, r.who) for _, r in ss.iterrows()],
                    hovertemplate="%{customdata}<extra></extra>",
                    name=f"구순 · 고정 품계 관직 ({gv.STATE_KO[state]})", legendgroup=f"st_{state}"),
                    row=1, col=1)
        else:
            for _, r in sub.iterrows():
                fig.add_trace(go.Scatter(
                    x=[r.plot_x_start, r.plot_x_end], y=[r.rank_numeric] * 2, mode="lines+markers",
                    line=dict(color=gv.STATE_COLOR[r.career_state], width=7), opacity=0.55,
                    marker=dict(symbol="line-ns", size=14, line=dict(width=2, color=gv.STATE_COLOR[r.career_state])),
                    hovertemplate=hover(r, r.who) + "<extra></extra>",
                    name="구순 · 월 단위 관측(구간)"), row=1, col=1)
                fig.add_annotation(x=r.plot_x_end, y=r.rank_numeric, text=f"{r.normalized_office_title} (월 단위)",
                                   showarrow=False, xanchor="left", yshift=12, font=dict(size=10, color=gv.INK2),
                                   row=1, col=1)

    # ② 가변 lane: 구순
    for state, ss in var.groupby("career_state"):
        fig.add_trace(go.Scatter(
            x=ss.plot_x_start, y=ss.lane, mode="markers",
            marker=dict(size=12, color=gv.STATE_COLOR[state], symbol="diamond",
                        line=dict(color=gv.SURFACE, width=2)),
            customdata=[hover(r, r.who) for _, r in ss.iterrows()],
            hovertemplate="%{customdata}<extra></extra>",
            name=f"구순 · 가변 품계 직함 ({gv.STATE_KO[state]})", legendgroup=f"st_{state}"), row=2, col=1)

    # 다른 인물 (기본 숨김)
    of = others[others.rank_numeric.notna()] if len(others) else others
    ov = others[others.rank_numeric.isna() & (others.rank_fixedness != "FORMER_OFFICE")] if len(others) else others
    for sub, row, ycol in ((of, 1, "rank_numeric"), (ov, 2, "lane")):
        sub = sub[sub.plot_x_start.notna()]
        if not len(sub):
            continue
        fig.add_trace(go.Scatter(
            x=sub.plot_x_start, y=sub[ycol], mode="markers",
            marker=dict(size=8, color="white", line=dict(color=OTHER_COLOR, width=1.5),
                        symbol="circle" if row == 1 else "diamond-open"),
            customdata=[hover(r, r.who) for _, r in sub.iterrows()], hovertemplate="%{customdata}<extra></extra>",
            name="다른 인물의 관직 (참고 · 범례 클릭으로 표시)", legendgroup="others",
            showlegend=row == 1, visible="legendonly"), row=row, col=1)

    # ③ career_state band (기존 spell 재사용) + 전직 hover에 former_statutory_rank
    lk = rk["lookup"].set_index("raw_office_status")
    former_rank = lk.loc["전 부사", "former_statutory_rank"] if "전 부사" in lk.index else gp.NA
    for _, s in career.iterrows():
        start = s.start if gp.is_day(s.start) else E.loc[s.evidence_start.split(";")[0], "earliest_possible"]
        x0, x1, x2 = gv.lx(start), gv.lx(s.earliest_end), gv.lx(s.latest_end)
        color = gv.STATE_COLOR[s.career_state]
        y = gv.STATE_KO[s.career_state]
        extra = (f"<br><b>현재 상태: FORMER_OFFICIAL</b> — 현재 rank_numeric 없음"
                 f"<br>과거 관직 법정품계: {former_rank} (lookup '전 부사')") if s.career_state == "FORMER_OFFICIAL" else ""
        hv = (f"<b>{s.spell_id} {gv.STATE_KO[s.career_state]} ({s.career_state})</b><br>"
              f"{gv.esc(s.office_or_status)} · {gv.esc(s.location)}<br>시작 {s.start} ({s.start_precision}) · "
              f"종료 [{s.earliest_end}, {s.latest_end}]<br>근거 {s.evidence_start} → {s.evidence_end}<br>"
              f"{gv.esc(s.notes)}{extra}<extra></extra>")
        if x1 is not None and x1 > x0:
            fig.add_trace(go.Bar(base=[x0], x=[x1 - x0], y=[y], orientation="h", width=0.62,
                                 marker=dict(color=color, line=dict(color=gv.SURFACE, width=1)),
                                 text=[s.location] if x1 - x0 > 1.0 else None, textposition="inside",
                                 textangle=0, insidetextanchor="start", textfont=dict(color="white", size=10),
                                 showlegend=False, hovertemplate=hv), row=3, col=1)
        else:
            fig.add_trace(go.Scatter(x=[x0], y=[y], mode="markers",
                                     marker=dict(symbol="line-ns", size=16, line=dict(width=3, color=color)),
                                     showlegend=False, hovertemplate=hv), row=3, col=1)
        if x1 is not None and x2 is not None and x2 > x1:
            fig.add_trace(go.Bar(base=[x1], x=[x2 - x1], y=[y], orientation="h", width=0.62,
                                 marker=dict(color="rgba(0,0,0,0)", line=dict(color=color, width=1),
                                             pattern=dict(shape="/", fgcolor=color, size=6, solidity=0.3)),
                                 showlegend=False, hovertemplate=hv.replace("<extra>", "<br><i>빗금=종료 가능 구간</i><extra>")),
                          row=3, col=1)
        if s.career_state == "FORMER_OFFICIAL":
            fig.add_annotation(x=x0, y=y, text=f"전 부사 — 과거 관직 법정품계: {former_rank}", showarrow=True,
                               arrowhead=0, ax=-10, ay=-26, xanchor="right", font=dict(size=10, color=gv.INK2),
                               row=3, col=1)
    state_order = ["현직", "조사 중", "수감", "정배", "방송(석방)", "전직(비현직)"]
    for st in ["ACTIVE", "UNDER_INVESTIGATION", "IMPRISONED", "EXILED", "RELEASED", "FORMER_OFFICIAL"]:
        fig.add_trace(go.Bar(x=[None], y=[None], marker=dict(color=gv.STATE_COLOR[st]),
                             name=f"상태: {gv.STATE_KO[st]} ({st})", legendgroup=f"st_{st}"), row=3, col=1)

    # 1787–1793 미관측 구간 (세 패널 공통)
    for r in (1, 2, 3):
        fig.add_vrect(x0=gp.lx("1787-01-03"), x1=gp.lx("1793-02-22"), fillcolor="#fff1ea", opacity=0.6,
                      line_width=0, layer="below", row=r, col=1)
    fig.add_annotation(x=(gp.lx("1787-01-03") + gp.lx("1793-02-22")) / 2, y=2.6, row=1, col=1, showarrow=False,
                       text="1787→1793 미관측 (해배 기록 없음)<br>동일인 L00 = HIGH_CONFIDENCE",
                       font=dict(size=10, color=gv.INK2))

    ticks = [2.5, 3.0, 3.5, 4.0, 4.5]
    fig.update_yaxes(row=1, col=1, autorange=False, range=[4.85, 2.3], tickmode="array", tickvals=ticks,
                     ticktext=[f"{gor.RANK_LABEL[t]} ({t})" for t in ticks],
                     title=dict(text="법정 품계 (위=높음)", font=dict(size=11, color=gv.MUTED)))
    fig.update_yaxes(row=2, col=1, categoryorder="array", categoryarray=list(reversed(VAR_LANES)),
                     tickmode="array", tickvals=VAR_LANES, ticktext=[VAR_LANE_KO[v] for v in VAR_LANES],
                     range=[-0.5, len(VAR_LANES) - 0.5])
    fig.update_yaxes(row=3, col=1, categoryorder="array", categoryarray=list(reversed(state_order)))
    gv.base_layout(fig, "구순(具純) 경력 × 관직의 법정 품계 (office_rank_lookup 결합)", 1080)
    fig.update_layout(barmode="overlay", margin=dict(l=210))
    for r in (1, 2, 3):
        gv.year_axis(fig, 1777, 1799, row=r, col=1, title=(r == 3))
    # 2번 패널의 lane이 비어 있어도 축에 나오도록 투명 점
    fig.add_trace(go.Scatter(x=[None] * 4, y=VAR_LANES, mode="markers", showlegend=False, hoverinfo="skip"),
                  row=2, col=1)
    return fig


def build(res, rk):
    fig = figure(res, rk)
    J = rk["joined"]
    g = J[J.focal_person_id.isin(gp.EGO)]
    tbl = (g[g.office_lookup_match_status.isin(["EXACT", "NORMALIZED"])]
           .groupby(["focal_raw_office_status", "normalized_office_title", "statutory_rank", "rank_fixedness",
                     "administrative_scope", "office_lookup_verification_status"], dropna=False)
           .agg(n_rows=("event_id", "size"), first=("date_lunar", "min"), last=("date_lunar", "max"))
           .reset_index())
    tbl["former_statutory_rank"] = tbl.focal_raw_office_status.map(
        rk["lookup"].set_index("raw_office_status").former_statutory_rank)
    intro = """
<p class="note"><b>품계는 관직 자체의 법정 품계</b>입니다(office_rank_lookup.csv). 구순 개인이 그 품계를 가졌다는 뜻이 아니며,
CSV에서 개인 품계로 확인되는 것은 E002의 '당상관'(노상추일기 전언) 하나뿐입니다. rank_numeric(정3품=3.0, 종3품=3.5 …)은
<b>Y축 정렬용 숫자</b>이고 권력·영향력 점수가 아닙니다.</p>
<ul>
<li>① 고정 품계(FIXED) 관직만 수치축에 놓았습니다. 위쪽일수록 높은 품계입니다.</li>
<li>② 선전관·별군직처럼 품계가 고정되지 않은 직함(VARIABLE·NO_SINGLE_STATUTORY_RANK·UNRANKED)은 숫자를 만들지 않고 별도 lane에 둡니다.</li>
<li>③ 전 부사(FORMER_OFFICIAL)·조사·수금·정배는 관직 축이 아니라 상태 띠에 있습니다. 전 부사는 현재 rank_numeric이 비어 있고,
  hover와 주석에 과거 관직의 법정 품계만 표시합니다.</li>
<li>범례의 '다른 인물의 관직'을 누르면 사건 관련 인물(관찰사·병마절도사·영장 등)의 직함도 같은 축에 참고로 표시됩니다.</li>
<li>X축은 음력 날짜의 명목 소수연도(시각화용)입니다. 막대·빗금 = 날짜 구간, 점 = 일자 확정.</li>
</ul>"""
    tail = "<h2>구순 직함 ↔ lookup 결합 요약</h2>" + gv.df_table(
        tbl, ["focal_raw_office_status", "normalized_office_title", "statutory_rank", "rank_fixedness",
              "former_statutory_rank", "administrative_scope", "office_lookup_verification_status", "n_rows",
              "first", "last"])
    (gp.OUT / "gusun_temporal_career_with_rank.html").write_text(
        gv.page("구순 경력 × 관직 법정 품계", intro, [fig], tail), encoding="utf-8")
