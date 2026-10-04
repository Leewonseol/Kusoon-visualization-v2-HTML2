"""개인 · 관계 · 국가 정책 3층을 같은 명목 음력 시간축에 놓는 대시보드와 1793 확대 보기.

- Panel A: 구순 관직(법정 품계 수치축 / 가변 lane / career_state band)
- Panel B: 구순 사건 + 구순 중심 관계(relation group lane)
- Panel C: 정조대 정책 milestone (broad_domain lane) — context layer, 인과 표시 없음
- Panel D: 클릭한 항목의 상세 + 같은/전/다음 해 정책(동시성만)
"""
from __future__ import annotations

import json
import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import gusun_pipeline as gp
import gusun_policy as gpol
import gusun_viz as gv
import gusun_viz_rank as gvr

X0, X1 = 1776.0, 1799.0
REL_INK = {"HIGH": "#0b0b0b", "MEDIUM": "#52514e", "LOW": "#a8a7a0"}  # 정책 관련도 = 회색 단계 (구순 색과 겹치지 않게)
REL_SIZE = {"HIGH": 15, "MEDIUM": 12, "LOW": 10}
REL_OPACITY = {"HIGH": 1.0, "MEDIUM": 0.8, "LOW": 0.4}
KIND_SYMBOL = {
    "POLICY_PRINCIPLE": "star", "INSTITUTION_FOUNDING": "square", "REFORM_RULE": "triangle-up",
    "LEGAL_STANDARDIZATION": "diamond", "PERSONNEL_INSTITUTION": "square-x", "PROGRAM_START": "triangle-right",
    "PROGRAM_RULES": "triangle-right-open", "PROGRAM_REFINEMENT": "triangle-right-dot",
    "REFORM_REENFORCEMENT": "triangle-up-open", "CODIFICATION_PROCESS": "diamond-open",
    "CODIFICATION_PROMULGATION": "diamond-wide", "ABUSE_REDUCTION": "x", "MILITARY_ORGANIZATION": "pentagon",
    "MILITARY_EXPANSION": "pentagon-open", "PERSONNEL_BALANCING": "star-open", "URBAN_PROJECT_PRELUDE": "hexagon-open",
    "MARKET_REFORM": "hourglass", "FORENSIC_STANDARDIZATION": "diamond-x",
    "MILITARY_LOCAL_REORGANIZATION": "pentagon-dot", "FORTRESS_CONSTRUCTION": "hexagon",
    "FORTRESS_COMPLETION": "hexagon-dot", "PROJECT_CLOSE": "square-open", "COMPLETION_CEREMONY": "circle-open",
}
EVENT_LANE = "구순 사건"
B_LANES = [EVENT_LANE] + gp.GROUP_ORDER


def h(v) -> str:
    return gv.esc("NA" if v is None or (isinstance(v, float) and pd.isna(v)) else v)


def ego_edges(res) -> pd.DataFrame:
    e = res["edges"]
    e = e[e.source_person.isin(gp.EGO) | e.target_person.isin(gp.EGO)].copy()
    e["ego"] = e.apply(lambda r: r.source_person if r.source_person in gp.EGO else r.target_person, axis=1)
    e["alter"] = e.apply(lambda r: r.target_person if r.source_person in gp.EGO else r.source_person, axis=1)
    e["outgoing"] = e.source_person.isin(gp.EGO)
    e["x_lo"] = e.apply(lambda r: gv.lx(r.earliest_start) if gp.is_day(r.earliest_start) else gv.lx(r.latest_start), axis=1)
    e["x_hi"] = e.apply(lambda r: gv.lx(r.latest_end) if gp.is_day(r.latest_end) else
                        (gv.lx(r.latest_start) if gp.is_day(r.latest_start) else None), axis=1)

    def rec_x(v):
        v = str(v)
        if gp.is_day(v):
            return gv.lx(v)
        if gp.MONTH_RE.match(v):
            return gv.lx(f"{v}-01")
        return None
    # 관계 자체의 시점이 없는 경우(친족·가내·이웃): 기록에서 관측된 시점만 표시 (관계 시작일 아님)
    e["x_obs_only"] = e.x_lo.isna()
    e["x_lo"] = e.x_lo.where(e.x_lo.notna(), e.record_date.map(rec_x))
    return e


def edge_symbol(r) -> str:
    if getattr(r, "x_obs_only", False):
        return "diamond-open"
    if not r.directed:
        return "circle"
    return "triangle-right" if r.outgoing else "triangle-left"


def add_panel_b(fig, res, row, names, xrange=(X0, X1)):
    ev = res["events"]
    g = ev[ev.person_id.isin(gp.EGO) & (ev.phase != "gap") & ~ev.event_id.isin(gp.KIN_CONTEXT_ROWS)].copy()
    g = g[(g.plot_x_start.notna()) & (g.plot_x_start >= xrange[0]) & (g.plot_x_start <= xrange[1])]
    lane_y = {l: len(B_LANES) - 1 - i for i, l in enumerate(B_LANES)}
    # 구순 사건 lane: 같은 날 여러 사건은 위아래로 분산
    g["k"] = g.groupby(g.plot_x_start.round(3)).cumcount()
    for state, ss in g.groupby("career_state"):
        ys = lane_y[EVENT_LANE] + ss.k.map(lambda k: ((k % 5) - 2) * 0.09)
        fig.add_trace(go.Scatter(
            x=ss.plot_x_start, y=ys, mode="markers",
            marker=dict(size=9, color=gv.STATE_COLOR[state], symbol="line-ns-open" if False else "circle",
                        line=dict(color=gv.SURFACE, width=1)),
            customdata=[[f"<b>{r.event_id}</b> {h(r.record_date_raw)} ({r.time_precision})<br>{h(r.event_type)} · "
                         f"{h(r.relation_type_raw)}<br>{h(r.office_name)} · {r.career_state}→{r.career_state_after}<br>"
                         f"<i>{h(str(r.event_description)[:120])}</i>", f"G:{r.event_id}"] for _, r in ss.iterrows()],
            hovertemplate="%{customdata[0]}<extra></extra>", name=f"구순 사건 ({gv.STATE_KO[state]})",
            legendgroup=f"st_{state}", showlegend=False), row=row, col=1)
    e = ego_edges(res)
    e = e[e.x_lo.notna() & (e.x_lo >= xrange[0] - 0.01) & (e.x_lo <= xrange[1])]
    e["k"] = e.groupby([e.relation_group, e.x_lo.round(3)]).cumcount()
    for grp in gp.GROUP_ORDER:
        sub = e[e.relation_group == grp]
        if not len(sub):
            continue
        col = gv.GROUP_COLOR[grp]
        ys = lane_y[grp] + sub.k.map(lambda k: ((k % 7) - 3) * 0.08)
        hov = [[gv.edge_hover(r, names) + f"<br>상대: {h(names.get(r.alter, r.alter))} · 구순 세그먼트 {r.ego}"
                + ("<br><b>◇ 관계 시작·종료 미상 — 표시 위치는 기록에서 관측된 시점</b>" if r.x_obs_only else ""),
                f"X:{r.edge_id}"] for _, r in sub.iterrows()]
        # 구간 관계: 가는 선
        xs, yy = [], []
        for (_, r), y in zip(sub.iterrows(), ys):
            if r.x_hi is not None and not pd.isna(r.x_hi) and r.x_hi > r.x_lo + 1e-6:
                xs += [r.x_lo, r.x_hi, None]
                yy += [y, y, None]
        if xs:
            fig.add_trace(go.Scatter(x=xs, y=yy, mode="lines", line=dict(color=col, width=3), opacity=0.45,
                                     hoverinfo="skip", showlegend=False, legendgroup=f"g_{grp}"), row=row, col=1)
        fig.add_trace(go.Scatter(
            x=sub.x_lo, y=ys, mode="markers",
            marker=dict(size=10, color=col, symbol=[edge_symbol(r) for _, r in sub.iterrows()],
                        line=dict(color=gv.SURFACE, width=1)),
            customdata=hov, hovertemplate="%{customdata[0]}<extra></extra>",
            name=gv.GROUP_KO[grp], legendgroup=f"g_{grp}"), row=row, col=1)
    fig.update_yaxes(row=row, col=1, tickmode="array", tickvals=[lane_y[l] for l in B_LANES],
                     ticktext=[l if l == EVENT_LANE else gv.GROUP_KO[l] for l in B_LANES],
                     range=[-0.6, len(B_LANES) - 0.4])


def add_panel_c(fig, pn: pd.DataFrame, row, xrange=(X0, X1), label_high=True):
    lane_y = {d: len(gpol.DOMAINS) - 1 - i for i, d in enumerate(gpol.DOMAINS)}
    p = pn[(pn.derived_plot_x >= xrange[0]) & (pn.derived_plot_x <= xrange[1])].copy()
    # 같은 lane 안 가까운 날짜는 위아래로 분산
    p = p.sort_values("derived_plot_x")
    offs = []
    last = {}
    for _, r in p.iterrows():
        prev = last.get(r.broad_domain)
        k = 0 if prev is None or r.derived_plot_x - prev[0] > 0.35 else prev[1] + 1
        last[r.broad_domain] = (r.derived_plot_x, k)
        offs.append([0, 0.2, -0.2, 0.35][k % 4])
    p["y"] = p.broad_domain.map(lane_y) + offs

    # episode 연결선 (milestone은 각각 유지)
    first = True
    for ep, g in p.groupby("policy_episode_id"):
        if len(g) < 2:
            continue
        g = g.sort_values("sort_key")
        fig.add_trace(go.Scatter(x=g.derived_plot_x, y=g.y, mode="lines", line=dict(color="#c3c2b7", width=1.2),
                                 hoverinfo="skip", name="policy episode 연결 (같은 policy_episode_id)",
                                 legendgroup="episode", showlegend=first), row=row, col=1)
        first = False
    # persistent context: open-ended 가는 점선 (종료일 만들지 않음)
    first = True
    pk = {}
    for _, r in p[p.persistence_class.str.startswith("PERSISTENT")].iterrows():
        k = pk.get(r.broad_domain, 0)
        pk[r.broad_domain] = k + 1
        y = lane_y[r.broad_domain] - 0.3 - 0.07 * k
        fig.add_trace(go.Scatter(
            x=[r.derived_plot_x, xrange[1]], y=[y, y], mode="lines+markers",
            line=dict(color=REL_INK[r.project_relevance], width=1, dash="dot"),
            marker=dict(symbol=["line-ns", "triangle-right-open"], size=[8, 8], color=REL_INK[r.project_relevance]),
            opacity=0.55, name="지속 제도 (open-ended · CSV에 종료일 없음)", legendgroup="persistent",
            showlegend=first, customdata=[[f"<b>{h(r.policy_title)}</b> — PERSISTENT_INSTITUTIONAL_CONTEXT<br>"
                                           f"시작 {r.date_lunar} · 종료: OPEN (CSV에 종료일 없음; 오른쪽 끝은 축 경계일 뿐)",
                                           f"P:{r.policy_event_id}"]] * 2,
            hovertemplate="%{customdata[0]}<extra></extra>"), row=row, col=1)
        first = False
    # 사업 구간 (시작·종료 모두 CSV milestone)
    for ep, k0, k1, label in gpol.PROJECT_INTERVALS:
        a = pn[(pn.policy_episode_id == ep) & (pn.event_kind == k0)]
        b = pn[(pn.policy_episode_id == ep) & (pn.event_kind == k1)]
        if len(a) and len(b):
            ya = lane_y[a.iloc[0].broad_domain] + 0.42
            xa, xb = max(a.iloc[0].derived_plot_x, xrange[0]), min(b.iloc[0].derived_plot_x, xrange[1])
            if xb > xa:
                fig.add_trace(go.Scatter(x=[xa, xb], y=[ya, ya], mode="lines", line=dict(color="#52514e", width=4),
                                         opacity=0.35, name="사업 구간 (시작·종료 모두 CSV)", hovertemplate=
                                         f"{label}<extra></extra>"), row=row, col=1)
    # milestone marker: 관련도별 trace (LOW는 토글 가능)
    for rel in ("HIGH", "MEDIUM", "LOW"):
        sub = p[p.project_relevance == rel]
        if not len(sub):
            continue
        cd = [[f"<b>{h(r.policy_title)}</b> ({r.policy_event_id})<br>{h(r.milestone)}<br>"
               f"{r.date_lunar} 음력 · {r.date_precision} · {r.calendar_basis}<br>"
               f"{r.broad_domain} · episode {r.policy_episode_id} ({r.episode_order}/{r.episode_size})<br>"
               f"event_kind: {r.event_kind} · scale {r.policy_scale} · relevance <b>{rel}</b><br>"
               f"{r.persistence_class}<br><i>{CAUSAL}</i>", f"P:{r.policy_event_id}"] for _, r in sub.iterrows()]
        fig.add_trace(go.Scatter(
            x=sub.derived_plot_x, y=sub.y, mode="markers+text" if (rel == "HIGH" and label_high) else "markers",
            marker=dict(size=REL_SIZE[rel], color=REL_INK[rel], symbol=[KIND_SYMBOL.get(k, "circle") for k in sub.event_kind],
                        line=dict(color=gv.SURFACE, width=1)),
            opacity=REL_OPACITY[rel],
            text=[t.replace("『", "").replace("』", "") for t in sub.policy_title] if rel == "HIGH" else None,
            textposition=["top center" if i % 2 == 0 else "bottom center" for i in range(len(sub))],
            textfont=dict(size=10, color=gv.INK),
            customdata=cd, hovertemplate="%{customdata[0]}<extra></extra>",
            name=f"정책 milestone · relevance {rel}", legendgroup=f"rel_{rel}"), row=row, col=1)
    fig.update_yaxes(row=row, col=1, tickmode="array", tickvals=[lane_y[d] for d in gpol.DOMAINS],
                     ticktext=[f"{d}<br>({gpol.DOMAIN_KO[d]})" for d in gpol.DOMAINS],
                     range=[-0.75, len(gpol.DOMAINS) - 0.4])


CAUSAL = "contemporary institutional context · 구순 사건의 원인 아님"


def sv(v) -> str:
    return "NA" if v is None or (isinstance(v, float) and pd.isna(v)) or str(v) in ("nan", "None") else str(v)


def detail_data(res, rk, pc) -> dict:
    ev = res["events"]
    J = rk["joined"].set_index("event_id")
    names = res["persons"].set_index("person_id").name_ko.to_dict()
    edges = res["edges"]
    pn = pc["norm"]
    win = pc["windows"]
    G = {}
    for _, r in ev[ev.person_id.isin(gp.EGO) | ev.event_id.isin(gp.KIN_CONTEXT_ROWS)].iterrows():
        rel = edges[edges.source_event_id.str.split(";").map(lambda l: r.event_id in l)]
        G[r.event_id] = dict(
            id=r.event_id, date=r.record_date_raw, precision=r.time_precision,
            bounds=f"{r.earliest_possible} ~ {r.latest_possible}", person=r.person_id,
            office=sv(r.office_name), norm_office=sv(J.loc[r.event_id, "normalized_office_title"]),
            statutory_rank=sv(J.loc[r.event_id, "statutory_rank"]),
            former_rank=sv(J.loc[r.event_id, "former_statutory_rank"]),
            state=f"{r.career_state} → {r.career_state_after}", type=r.event_type, raw_rel=r.relation_type_raw,
            subject=names.get(r.subject_id, r.subject_id), object=names.get(r.object_id, r.object_id),
            desc=r.event_description, location=r.location, source=r.source_title, url=sv(r.source_url),
            confidence=f"grade {r.evidence_grade} · {r.claim_status}",
            relations=[dict(id=x.edge_id, t=x.relation_type, s=names.get(x.source_person, x.source_person),
                            o=names.get(x.target_person, x.target_person), c=str(x.confidence),
                            st=x.evidence_status) for _, x in rel.iterrows()],
            context=[dict(p=w.policy_event_id, w=w.window_class, o=w.relative_order)
                     for _, w in win[win.gusun_event_id == r.event_id].iterrows()])
    X = {r.edge_id: dict(id=r.edge_id, t=r.relation_type, grp=r.relation_group, sub=str(r.relation_subtype),
                         s=names.get(r.source_person, r.source_person), o=names.get(r.target_person, r.target_person),
                         start=f"{r.start_date} [{r.earliest_start}, {r.latest_start}]",
                         end=f"{r.end_date} [{r.earliest_end}, {r.latest_end}]", prec=r.time_precision,
                         conf=str(r.confidence), st=r.evidence_status, ev=str(r.period_event_id),
                         summary=str(r.evidence_summary)) for _, r in edges.iterrows()}
    S = {r.spell_id: dict(id=r.spell_id, state=r.career_state, office=r.office_or_status, loc=r.location,
                          start=f"{r.start} ({r.start_precision})", end=f"[{r.earliest_end}, {r.latest_end}]",
                          notes=r.notes, ev=r.evidence_start.split(";")[0]) for _, r in res["career"].iterrows()}
    P = {}
    for _, q in pn.iterrows():
        rel_events = win[(win.policy_event_id == q.policy_event_id) & (win.window_class != "ONGOING_CONTEXT_STARTED_EARLIER")]
        ep = pn[pn.policy_episode_id == q.policy_episode_id].sort_values("sort_key")
        P[q.policy_event_id] = dict(
            id=q.policy_event_id, title=q.policy_title, milestone=q.milestone, domain=q.broad_domain,
            date=q.date_lunar, precision=q.date_precision, calendar=q.calendar_basis, summary=q.summary,
            scale=q.policy_scale, relevance=q.project_relevance, source=q.source_title, url=q.source_url,
            verification=q.verification_status, kind=q.event_kind, persistence=q.persistence_class,
            end=str(q.context_end_date), episode=q.policy_episode_id,
            episode_list=[f"{x.date_lunar} {x.policy_title}" for _, x in ep.iterrows()],
            gusun=sorted({(w.gusun_event_id, w.window_class) for _, w in rel_events.iterrows()}))
    return dict(G=G, X=X, S=S, P=P)


PANEL_D_JS = r"""
<script>
const D = __DATA__;
function e(s){const d=document.createElement('div');d.textContent=(s===undefined||s===null)?'NA':String(s);return d.innerHTML;}
const WIN_KO={SAME_YEAR:'같은 해',PREVIOUS_YEAR:'전 해',NEXT_YEAR:'다음 해',ONGOING_CONTEXT_STARTED_EARLIER:'이전 시작 · 종료 기록 없음 (ONGOING)'};
function ctxTable(ctx){
  if(!ctx||!ctx.length) return '<p class="muted">같은/전/다음 해 정책 없음</p>';
  const order=['SAME_YEAR','PREVIOUS_YEAR','NEXT_YEAR','ONGOING_CONTEXT_STARTED_EARLIER'];
  let out='';
  for(const w of order){
    const rows=ctx.filter(c=>c.w===w); if(!rows.length) continue;
    out+=`<h4>${WIN_KO[w]} (${rows.length})</h4><ul>`;
    for(const c of rows){const p=D.P[c.p];
      out+=`<li><a href="#" data-k="P:${p.id}">${e(p.title)}</a> <span class="muted">${e(p.date)} · ${e(p.domain)} · ${e(p.relevance)} · ${e(c.o)}</span></li>`;}
    out+='</ul>';
  }
  return out;
}
function showG(id, prefix){
  const g=D.G[id]; if(!g) return '';
  let rel=g.relations.map(r=>`<li>${e(r.s)} → ${e(r.o)} : <b>${e(r.t)}</b> <span class="muted">(${e(r.c)}, ${e(r.st)})</span></li>`).join('');
  return `${prefix||''}<h3>구순 측 · ${e(g.id)}</h3>
  <table><tr><th>date</th><td>${e(g.date)} (${e(g.precision)}; 가능 구간 ${e(g.bounds)})</td></tr>
  <tr><th>office/status</th><td>${e(g.office)} · 정규화 ${e(g.norm_office)} · 법정품계 ${e(g.statutory_rank)}${g.former_rank!=='NA'?' · 과거 관직 품계 '+e(g.former_rank):''}</td></tr>
  <tr><th>career_state</th><td>${e(g.state)}</td></tr>
  <tr><th>event</th><td>${e(g.type)} · ${e(g.raw_rel)}<br>${e(g.desc)}</td></tr>
  <tr><th>person</th><td>${e(g.subject)} → ${e(g.object)} · ${e(g.location)}</td></tr>
  <tr><th>relation</th><td><ul>${rel||'<li class="muted">이 사건에서 파생된 edge 없음</li>'}</ul></td></tr>
  <tr><th>source</th><td>${e(g.source)} <span class="muted">${e(g.url)} (접속하지 않은 메타데이터)</span></td></tr>
  <tr><th>confidence</th><td>${e(g.confidence)}</td></tr></table>
  <div class="note">아래는 <b>시간적 동시성</b>만 보여줍니다. 정책이 이 사건의 원인이라는 뜻이 아닙니다 (contemporary institutional context). 창: 같은 해 / 전 해 / 다음 해 (연도 필드 기준, 양력 일수 계산 아님) + 그 이전에 시작해 CSV에 종료 기록이 없는 제도.</div>
  ${ctxTable(g.context)}`;
}
function showP(id){
  const p=D.P[id];
  const gl=p.gusun.map(([gid,w])=>`<li><a href="#" data-k="G:${gid}">${e(gid)}</a> <span class="muted">${e(D.G[gid]?D.G[gid].date:'')} · ${WIN_KO[w]} · ${e(D.G[gid]?D.G[gid].raw_rel:'')}</span></li>`).join('');
  return `<h3>정책 측 · ${e(p.id)}</h3>
  <table><tr><th>policy_title</th><td><b>${e(p.title)}</b></td></tr>
  <tr><th>milestone</th><td>${e(p.milestone)}</td></tr>
  <tr><th>date</th><td>${e(p.date)} (${e(p.precision)}, ${e(p.calendar)})</td></tr>
  <tr><th>broad_domain</th><td>${e(p.domain)} · event_kind ${e(p.kind)}</td></tr>
  <tr><th>summary</th><td>${e(p.summary)}</td></tr>
  <tr><th>policy_scale</th><td>${e(p.scale)}</td></tr>
  <tr><th>project_relevance</th><td>${e(p.relevance)}</td></tr>
  <tr><th>persistence</th><td>${e(p.persistence)} · 종료 ${e(p.end)}</td></tr>
  <tr><th>episode</th><td>${e(p.episode)}<ul>${p.episode_list.map(x=>'<li>'+e(x)+'</li>').join('')}</ul></td></tr>
  <tr><th>source_title</th><td>${e(p.source)} <span class="muted">${e(p.url)} (접속하지 않은 메타데이터)</span></td></tr>
  <tr><th>verification_status</th><td>${e(p.verification)}</td></tr></table>
  <div class="note">contemporary institutional context — 구순 사건과의 인과관계를 표시하지 않습니다.</div>
  <h4>같은/전/다음 해의 구순 기록 (${p.gusun.length})</h4><ul>${gl||'<li class="muted">없음</li>'}</ul>`;
}
function render(key){
  const box=document.getElementById('panelD'); if(!key){return;}
  const [t,id]=[key.slice(0,1),key.slice(2)];
  let html='';
  if(t==='G') html=showG(id);
  else if(t==='P') html=showP(id);
  else if(t==='X'){const x=D.X[id];
    html=`<h3>관계 edge · ${e(x.id)}</h3><table><tr><th>relation</th><td>${e(x.s)} → ${e(x.o)} : <b>${e(x.t)}</b> (${e(x.grp)})<br>${e(x.sub)}</td></tr>
    <tr><th>start</th><td>${e(x.start)}</td></tr><tr><th>end</th><td>${e(x.end)}</td></tr><tr><th>precision</th><td>${e(x.prec)}</td></tr>
    <tr><th>confidence</th><td>${e(x.conf)} · ${e(x.st)}</td></tr><tr><th>evidence</th><td>${e(x.summary)}</td></tr></table>`
    + showG(x.ev,'<hr>');}
  else if(t==='S'){const s=D.S[id];
    html=`<h3>career_state · ${e(s.id)}</h3><table><tr><th>state</th><td><b>${e(s.state)}</b> · ${e(s.office)} · ${e(s.loc)}</td></tr>
    <tr><th>start</th><td>${e(s.start)}</td></tr><tr><th>end</th><td>${e(s.end)}</td></tr><tr><th>notes</th><td>${e(s.notes)}</td></tr></table>`
    + showG(s.ev,'<hr>');}
  box.innerHTML=html; box.scrollTop=0;
}
document.addEventListener('click',ev=>{const a=ev.target.closest('a[data-k]'); if(a){ev.preventDefault(); render(a.dataset.k);}});
const sel=document.getElementById('pickEvent'); if(sel) sel.addEventListener('change',()=>render(sel.value));
window.addEventListener('load',()=>{
  document.querySelectorAll('.plotly-graph-div').forEach(gd=>{
    gd.on('plotly_click',d=>{const p=d.points&&d.points[0]; if(p&&p.customdata&&p.customdata[1]) render(p.customdata[1]);});
  });
  render('G:E066');
});
</script>
"""


def dashboard(res, rk, pc):
    names = res["persons"].set_index("person_id").name_ko.to_dict()
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.035,
                        row_heights=[0.17, 0.11, 0.14, 0.26, 0.32],
                        subplot_titles=("A① 구순 관직 — 관직 자체의 법정 품계 (Y는 정렬용; 개인 품계 아님)",
                                        "A② 가변·무품 직함 lane",
                                        "A③ career_state band (전직·조사·수감·정배 — 관직 축과 분리)",
                                        "B. 구순 사건과 구순 중심 관계 (lane = 관계군; ▶ 구순→상대, ◀ 상대→구순, ● 대칭)",
                                        "C. 정조대 정책 milestone (lane = broad_domain; 회색 농도 = project_relevance) — context layer"))
    gvr.add_career_panels(fig, res, rk, rows=(1, 2, 3), show_others=False, gap_annotation=False)
    fig.update_yaxes(row=2, col=1, ticktext=gvr.VAR_LANES, tickfont=dict(size=10))
    add_panel_b(fig, res, 4, names)
    add_panel_c(fig, pc["norm"], 5)
    for r in (4, 5):
        fig.add_vrect(x0=gp.lx("1787-01-03"), x1=gp.lx("1793-02-22"), fillcolor="#fff1ea", opacity=0.6,
                      line_width=0, layer="below", row=r, col=1)
    # 구순 핵심 사건 세로 기준선 (모든 패널 공통)
    for d, lab in [("1784-09-23", "1784 정배"), ("1787-01-03", "1787 이윤빈 무고·제주 정배"),
                   ("1793-02-22", "1793 김명신 사건"), ("1798-02-21", "1798 방송")]:
        fig.add_vline(x=gp.lx(d), line=dict(color="#898781", width=1, dash="dash"), layer="below")
    for i, (d, lab) in enumerate([("1784-09-23", "1784 정배"), ("1787-01-03", "1787 무고·제주 정배"),
                                  ("1793-02-22", "1793 김명신 사건"), ("1798-02-21", "1798 방송")]):
        fig.add_annotation(x=gp.lx(d), y=0.01 + 0.07 * (i % 2), xref="x5", yref="y5 domain", text=lab,
                           showarrow=False, xanchor="left", yanchor="bottom", bgcolor="rgba(252,252,251,0.85)",
                           font=dict(size=10, color=gv.INK2))
    gv.base_layout(fig, "", 1750)
    fig.update_layout(barmode="overlay", margin=dict(l=200, r=20, t=70, b=170),
                      updatemenus=[dict(type="buttons", direction="left", x=0.0, y=1.035, xanchor="left",
                                        yanchor="bottom", showactive=True, buttons=[
                                            dict(label="LOW 정책 흐리게 표시", method="restyle",
                                                 args=[{"visible": True}, [i for i, t in enumerate(fig.data)
                                                                          if t.legendgroup == "rel_LOW"]]),
                                            dict(label="LOW 정책 숨기기", method="restyle",
                                                 args=[{"visible": False}, [i for i, t in enumerate(fig.data)
                                                                           if t.legendgroup == "rel_LOW"]])])])
    for r in range(1, 6):
        gv.year_axis(fig, X0, X1, row=r, col=1, title=(r == 5))
    return fig


def zoom_1793(res, rk, pc):
    lo, hi = gp.lx("1793-01-01"), gp.lx("1793-12-30")
    names = res["persons"].set_index("person_id").name_ko.to_dict()
    career = res["career"]
    E = res["events"].set_index("event_id")
    pn = pc["norm"]
    e = ego_edges(res)
    e = e[(e.ego == "GUSUN_1793PLUS") & (e.phase == "kim_case_1793")]
    alters = (e.groupby("alter").x_lo.min().sort_values().index.tolist())
    new93 = pn[pn.year == "1793"]
    ongoing = pn[(pn.year.astype(int) < 1793) & pn.persistence_class.str.startswith("PERSISTENT")]
    n_alt = len(alters)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        row_heights=[0.12, 0.6, 0.28],
                        subplot_titles=("구순 career_state (1793)",
                                        "구순–주변 인물 관계 (행 = 상대 인물, 색 = 관계군; ▶ 구순→상대 ◀ 상대→구순 ● 대칭)",
                                        "정책: 1793년 신규 milestone vs 이전부터 이어진 ONGOING CONTEXT"))
    # row1 career state
    for _, s in career.iterrows():
        start = s.start if gp.is_day(s.start) else E.loc[s.evidence_start.split(";")[0], "earliest_possible"]
        x0, x1, x2 = gv.lx(start), gv.lx(s.earliest_end), gv.lx(s.latest_end)
        x2 = x2 if x2 is not None else hi
        if x2 < lo or x0 > hi:
            continue
        a, b = max(x0, lo), min(x1 if x1 else x0, hi)
        color = gv.STATE_COLOR[s.career_state]
        hv = f"<b>{s.spell_id} {gv.STATE_KO[s.career_state]}</b><br>{h(s.location)}<br>시작 {s.start} · 종료 [{s.earliest_end}, {s.latest_end}]<br>{h(s.notes)}"
        if b > a:
            fig.add_trace(go.Bar(base=[a], x=[b - a], y=["상태"], orientation="h", width=0.6,
                                 marker=dict(color=color, line=dict(color=gv.SURFACE, width=1)),
                                 text=[gv.STATE_KO[s.career_state]], textposition="inside", textangle=0,
                                 textfont=dict(color="white", size=11), showlegend=False,
                                 customdata=[[hv, f"S:{s.spell_id}"]], hovertemplate="%{customdata[0]}<extra></extra>"),
                          row=1, col=1)
        c0, c1 = max(x1 if x1 else x0, lo), min(x2, hi)
        if c1 > c0:
            fig.add_trace(go.Bar(base=[c0], x=[c1 - c0], y=["상태"], orientation="h", width=0.6,
                                 marker=dict(color="rgba(0,0,0,0)", line=dict(color=color, width=1),
                                             pattern=dict(shape="/", fgcolor=color, size=6, solidity=0.3)),
                                 showlegend=False,
                                 customdata=[[hv, f"S:{s.spell_id}"]], hovertemplate="%{customdata[0]}<extra></extra>"),
                          row=1, col=1)
    # row2 relations by alter
    ypos = {a: n_alt - i for i, a in enumerate(alters)}
    shown = set()
    goff = {g: (i - 3.5) * 0.07 for i, g in enumerate(gp.GROUP_ORDER)}
    for _, r in e.iterrows():
        y = ypos[r.alter] + goff[r.relation_group]
        col = gv.GROUP_COLOR[r.relation_group]
        hov = [[gv.edge_hover(r, names) + ("<br><b>◇ 관계 시작·종료 미상 — 표시 위치는 기록에서 관측된 시점</b>"
                                           if r.x_obs_only else ""), f"X:{r.edge_id}"]]
        leg = r.relation_group not in shown
        shown.add(r.relation_group)
        if r.x_hi is not None and not pd.isna(r.x_hi) and r.x_hi > r.x_lo + 1e-6:
            fig.add_trace(go.Scatter(x=[r.x_lo, r.x_hi], y=[y, y], mode="lines",
                                     line=dict(color=col, width=5, dash=gv.REL_DASH.get(r.relation_type, "solid")),
                                     opacity=0.5, customdata=hov * 2, hovertemplate="%{customdata[0]}<extra></extra>",
                                     name=gv.GROUP_KO[r.relation_group], legendgroup=r.relation_group,
                                     showlegend=leg), row=2, col=1)
            leg = False
        fig.add_trace(go.Scatter(x=[r.x_lo], y=[y], mode="markers",
                                 marker=dict(size=10, color=col, symbol=edge_symbol(r), line=dict(color=gv.SURFACE, width=1)),
                                 customdata=hov, hovertemplate="%{customdata[0]}<extra></extra>",
                                 name=gv.GROUP_KO[r.relation_group], legendgroup=r.relation_group, showlegend=leg),
                      row=2, col=1)
    for i, (d, lab) in enumerate([("1793-02-22", "도난 보고"), ("1793-03-04", "김명신 체포명령"),
                                  ("1793-05-12", "관찰사 장계·수금 명령"), ("1793-05-27", "암행어사 보고"),
                                  ("1793-06-13", "최종 판정·정배")]):
        fig.add_vline(x=gp.lx(d), line=dict(color="#c3c2b7", width=1, dash="dot"), layer="below")
        fig.add_annotation(x=gp.lx(d), y=0.02 + 0.055 * i, xref="x2", yref="y2 domain", text=f"{d} {lab}",
                           showarrow=False, xanchor="left", yanchor="bottom", bgcolor="rgba(252,252,251,0.85)",
                           font=dict(size=9, color=gv.INK2))
    fig.update_yaxes(row=2, col=1, tickmode="array", tickvals=[ypos[a] for a in alters],
                     ticktext=[names.get(a, a) for a in alters], range=[0.4, n_alt + 0.6])
    # row3 policy: 1793 신규 vs ongoing
    lanes = ["1793 신규 milestone"] + [f"ONGOING · {r.policy_title} (since {r.year})" for _, r in ongoing.iterrows()]
    ly = {l: len(lanes) - 1 - i for i, l in enumerate(lanes)}
    for _, q in new93.iterrows():
        fig.add_trace(go.Scatter(
            x=[q.derived_plot_x], y=[ly[lanes[0]]], mode="markers+text", text=[q.policy_title],
            textposition="middle right", textfont=dict(size=11, color=gv.INK),
            marker=dict(size=REL_SIZE[q.project_relevance], color=REL_INK[q.project_relevance],
                        symbol=KIND_SYMBOL.get(q.event_kind, "circle")),
            customdata=[[f"<b>{h(q.policy_title)}</b> {q.date_lunar}<br>{h(q.milestone)}<br>{q.broad_domain} · "
                         f"relevance {q.project_relevance}<br><b>1793년 신규 milestone</b><br><i>{CAUSAL}</i>",
                         f"P:{q.policy_event_id}"]],
            hovertemplate="%{customdata[0]}<extra></extra>", name="1793 신규 정책 milestone", showlegend=True),
            row=3, col=1)
    first = True
    for _, q in ongoing.iterrows():
        lane = f"ONGOING · {q.policy_title} (since {q.year})"
        fig.add_trace(go.Scatter(
            x=[lo, hi], y=[ly[lane]] * 2, mode="lines", line=dict(color=REL_INK[q.project_relevance], width=2, dash="dot"),
            opacity=0.6, customdata=[[f"<b>{h(q.policy_title)}</b> — ONGOING CONTEXT<br>시작 {q.date_lunar} ({q.broad_domain}, "
                                      f"relevance {q.project_relevance})<br>CSV에 종료일 없음. 1793년에 실제 시행 중이었는지는 "
                                      f"CSV가 직접 확인하지 않음 (open-ended context)<br><i>{CAUSAL}</i>",
                                      f"P:{q.policy_event_id}"]] * 2,
            hovertemplate="%{customdata[0]}<extra></extra>", name="ONGOING CONTEXT (이전 시작, 종료 기록 없음)",
            legendgroup="ongoing", showlegend=first), row=3, col=1)
        first = False
    fig.update_yaxes(row=3, col=1, tickmode="array", tickvals=list(ly.values()), ticktext=list(ly.keys()),
                     range=[-0.6, len(lanes) - 0.4])
    gv.base_layout(fig, "", 1180)
    months = [f"1793-{m:02d}-01" for m in range(1, 13)]
    for r in (1, 2, 3):
        fig.update_xaxes(row=r, col=1, range=[lo - 0.01, hi + 0.01], tickmode="array",
                         tickvals=[gp.lx(m) for m in months], ticktext=[m[:7] for m in months])
    fig.update_xaxes(row=3, col=1, title=dict(text="1793년 음력 월 (명목 축; 양력 환산 아님)",
                                              font=dict(size=11, color=gv.MUTED)))
    fig.update_layout(barmode="overlay", margin=dict(l=300, r=20, t=90, b=150))
    return fig, new93, ongoing


PANEL_CSS = """
<style>
.dash { display:grid; grid-template-columns: minmax(0,1fr) 380px; gap:14px; align-items:start; }
#panelD { position:sticky; top:12px; max-height:92vh; overflow:auto; background:var(--surface);
          border:1px solid rgba(11,11,11,.10); border-radius:10px; padding:10px 14px; font-size:.85rem; }
#panelD h3 { font-size:1rem; margin:.3rem 0; } #panelD h4 { font-size:.9rem; margin:.7rem 0 .2rem; }
#panelD table td, #panelD table th { padding:3px 6px; overflow-wrap:anywhere; } #panelD ul { padding-left:18px; margin:.2rem 0; }
.muted { color:var(--muted); } select { font:inherit; padding:4px; max-width:100%; }
@media (max-width: 1100px) { .dash { grid-template-columns: 1fr; } #panelD { position:static; max-height:none; } }
</style>"""


def build(res, rk, pc):
    data = detail_data(res, rk, pc)
    js = PANEL_D_JS.replace("__DATA__", json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/"))
    ev = res["events"]
    g = ev[ev.person_id.isin(gp.EGO) & (ev.phase != "gap") & ~ev.event_id.isin(gp.KIN_CONTEXT_ROWS)]
    options = "".join(f'<option value="G:{r.event_id}"{" selected" if r.event_id == "E066" else ""}>'
                      f'{gv.esc(r.record_date_raw)} {r.event_id} {gv.esc(r.relation_type_raw)}</option>'
                      for _, r in g.iterrows())

    fig = dashboard(res, rk, pc)
    plot_html = fig.to_html(full_html=False, include_plotlyjs=True, auto_play=False,
                            config={"responsive": True, "displaylogo": False})
    intro = f"""
<p class="note"><b>세 층은 독립된 데이터 layer입니다.</b> A·B = 구순 개인 기록(gusun_temporal_network_master),
A의 품계 = 관직 자체의 법정 품계(office_rank_lookup; 개인 품계 아님), C = 정조대 정책(jeongjo_policy_timeline).
정책과 구순 사건이 같은 시기에 보이는 것은 <b>시간적 동시성</b>일 뿐이며 인과관계를 표시하지 않습니다.
정책은 네트워크 노드가 아니고 정책–인물 edge도 없습니다.</p>
<ul>
<li>X축: 모든 날짜는 음력(정책 CSV는 서기 연도 + 조선 음력 월일). 양력으로 바꾸지 않았고, 좌표는 1년=360일 명목 소수연도(DERIVED_FOR_VISUALIZATION)입니다.</li>
<li>점 = 일자 확정, 막대·선 = 날짜 구간, 빗금 = 종료 미상 구간, 연한 주황 = 1787→1793 구순 기록 공백.</li>
<li>C 패널: 기호 = event_kind, 회색 농도·크기 = project_relevance(HIGH 진함 → LOW 흐림), 회색 선 = 같은 policy_episode 연결,
  점선 → = 종료일 없는 지속 제도(오른쪽 끝은 축 경계일 뿐 종료일이 아님), 굵은 회색 = 시작·종료가 둘 다 CSV에 있는 화성 축성 구간.
  상단 버튼으로 LOW 정책을 숨길 수 있습니다.</li>
<li><b>그래프의 점·막대를 클릭</b>하면 오른쪽 Panel D에 상세와, 구순 사건이면 같은 해·전 해·다음 해·이전부터 이어진 정책 목록이 나옵니다.</li>
</ul>"""
    body = f"""{PANEL_CSS}
<div class="dash"><div class="card">{plot_html}</div>
<aside id="panelD"><p class="muted">그래프를 클릭하세요.</p></aside></div>
<p><label>구순 사건 바로 선택: <select id="pickEvent">{options}</select></label></p>
{js}"""
    page = gv.page("구순 Temporal Context Dashboard", intro, [], "")
    page = page.replace("</main>", body + "</main>")
    (gp.OUT / "gusun_temporal_context_dashboard.html").write_text(page, encoding="utf-8")

    zfig, new93, ongoing = zoom_1793(res, rk, pc)
    zplot = zfig.to_html(full_html=False, include_plotlyjs=True, auto_play=False,
                         config={"responsive": True, "displaylogo": False})
    intro_z = f"""
<p>1793년 구순–김명신 사건을 1793년 음력 1–12월 축으로 확대했습니다. 정책은 1793년 기록만 '신규 milestone'으로 표시하고
(1793년 정책 milestone {len(new93)}건), 그 이전에 성립해 CSV에 종료 기록이 없는 제도는 <b>ONGOING CONTEXT</b>로 따로 표시했습니다
({len(ongoing)}건). ONGOING은 'CSV에 종료일이 없다'는 뜻이지, 1793년에 시행 중이었음이 확인됐다는 뜻이 아닙니다.
다른 해의 정책 milestone을 1793년으로 끌어오지 않았습니다.</p>
<p class="note">1793년 사건에서 <b>실제로 확인되는 제도적 경로</b>는 B 패널의 관계 edge(구순→유제희→한재욱→장교→피의자, 관찰사·암행어사·안핵어사·국왕의 처분)입니다.
아래 정책 줄은 <b>시대적 배경</b>일 뿐 이 경로의 일부가 아닙니다.</p>"""
    tail = ("<h2>1793년 신규 정책 milestone</h2>" +
            gv.df_table(new93, ["policy_event_id", "date_lunar", "broad_domain", "policy_title", "milestone",
                                "project_relevance", "persistence_class", "verification_status"]))
    body_z = f"""{PANEL_CSS}
<div class="dash"><div class="card">{zplot}</div>
<aside id="panelD"><p class="muted">그래프를 클릭하세요.</p></aside></div>{tail}{js}"""
    pz = gv.page("구순 1793 Context Zoom", intro_z, [], "").replace("</main>", body_z + "</main>")
    (gp.OUT / "gusun_1793_context_zoom.html").write_text(pz, encoding="utf-8")
