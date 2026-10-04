"""정조대 정책 timeline (jeongjo_policy_timeline.csv) — 독립된 context layer.

- 날짜는 서기 연도 + 조선 음력 월·일. 양력 변환하지 않는다. sort_key를 정렬 기준으로 쓴다.
- 정책은 네트워크 노드가 아니며, 정책–인물 사이 edge를 만들지 않는다.
- 구순 사건과의 '동시성'만 계산한다 (same / previous / next year, 이전 시작·종료 기록 없는 지속 제도).
  인과관계는 생성하지 않는다.
- source_url은 메타데이터로만 보존한다 (접속하지 않음).
"""
from __future__ import annotations

import pandas as pd

import gusun_pipeline as gp

DOMAINS = ["POLITICS_PERSONNEL", "SOCIAL_STATUS_PERSONNEL", "LEGAL_JUSTICE", "MILITARY_DEFENSE",
           "ECONOMY_COMMERCE", "LOCAL_ADMIN_URBAN"]
DOMAIN_KO = {"POLITICS_PERSONNEL": "정치·인사", "SOCIAL_STATUS_PERSONNEL": "신분·인사",
             "LEGAL_JUSTICE": "법제·형정", "MILITARY_DEFENSE": "군사·국방",
             "ECONOMY_COMMERCE": "경제·상업", "LOCAL_ADMIN_URBAN": "지방행정·도시"}
# event_kind → 지속성 분류 (DERIVED 규칙). 종료일은 CSV에 없으므로 모두 open-ended.
PERSISTENT_KINDS = {"INSTITUTION_FOUNDING", "PERSONNEL_INSTITUTION", "LEGAL_STANDARDIZATION",
                    "CODIFICATION_PROMULGATION", "PROGRAM_START", "MILITARY_ORGANIZATION", "MARKET_REFORM",
                    "FORENSIC_STANDARDIZATION", "REFORM_RULE"}
# 시작·종료가 둘 다 CSV milestone인 사업 구간
PROJECT_INTERVALS = [("HWASEONG", "FORTRESS_CONSTRUCTION", "PROJECT_CLOSE", "화성 축성 사업 (1794 하명 → 1796 성역 종료)")]
CAUSAL_NOTE = "contemporary institutional context — 구순 사건의 원인으로 표시하지 않음"


def find(name: str):
    c = [p for p in gp.ROOT.rglob(name) if gp.OUT not in p.parents]
    if not c:
        raise FileNotFoundError(name)
    return sorted(c, key=lambda p: p.stat().st_mtime)[-1]


def load_policy():
    path = find("jeongjo_policy_timeline.csv")
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
    df["csv_row_number"] = range(2, len(df) + 2)
    return path, df


def normalize_policy(pol: pd.DataFrame) -> pd.DataFrame:
    p = pol.copy()
    for c in ("year", "month", "day"):
        p[c + "_int"] = pd.to_numeric(p[c], errors="coerce").astype("Int64")
    p["sort_key_int"] = pd.to_numeric(p.sort_key, errors="coerce").astype("Int64")
    p = p.sort_values(["sort_key_int", "policy_event_id"]).reset_index(drop=True)
    p["date_lunar_preserved"] = p.date_lunar
    p["derived_plot_x"] = p.date_lunar.map(lambda d: gp.lx(d) if gp.is_day(d) else None)
    p["derived_plot_date"] = p.date_lunar.where(p.date_precision == "EXACT_DAY", gp.NA)
    p["derived_plot_evidence_status"] = "DERIVED_FOR_VISUALIZATION (명목 음력 소수연도; 양력 환산 아님)"
    p["persistence_class"] = p.event_kind.map(lambda k: "PERSISTENT_INSTITUTIONAL_CONTEXT"
                                              if k in PERSISTENT_KINDS else "POINT_EVENT")
    p["persistence_basis"] = p.event_kind.map(lambda k: f"event_kind={k} → 제도·규범 성립(규칙)"
                                              if k in PERSISTENT_KINDS else f"event_kind={k} → 단일 시점 행위")
    p["context_end_date"] = p.persistence_class.map(lambda c: "OPEN (CSV에 종료일 없음)"
                                                    if c.startswith("PERSISTENT") else gp.NA)
    p["project_interval"] = gp.NA
    for ep, k0, k1, label in PROJECT_INTERVALS:
        a = p[(p.policy_episode_id == ep) & (p.event_kind == k0)]
        b = p[(p.policy_episode_id == ep) & (p.event_kind == k1)]
        if len(a) and len(b):
            p.loc[a.index, "project_interval"] = f"{label}: {a.iloc[0].date_lunar} → {b.iloc[0].date_lunar} (둘 다 CSV milestone)"
    p["episode_order"] = p.groupby("policy_episode_id").cumcount() + 1
    p["episode_size"] = p.groupby("policy_episode_id").policy_event_id.transform("size")
    p["data_layer"] = "POLICY_CONTEXT"
    p["causal_link_to_gusun"] = "NONE — " + CAUSAL_NOTE
    p["evidence_status"] = "OBSERVED (policy CSV) + DERIVED (persistence_class, plot_x)"
    return p


def input_audit(master: pd.DataFrame, lk: pd.DataFrame, pol: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def add(f, metric, value):
        rows.append(dict(file=f, metric=metric, value=value))

    m = "gusun_temporal_network_master_v0_2.csv"
    add(m, "row_count", len(master))
    add(m, "column_names", ";".join(c for c in master.columns if c != "csv_row_number"))
    add(m, "date_range", f"{master.date_lunar.min()} ~ {master.date_lunar.max()} (date_lunar, 음력; year {master.year.min()}–{master.year.max()})")
    ids = set(master.subject_id) | set(master.object_id)
    add(m, "unique_person_count", f"P_ id {len([i for i in ids if i.startswith('P_')])}개 (P_GUSUN 포함; 기관 P_STATE·P_BIBEONSA·P_UIGEUMBU·P_JOSEON·P_QING 포함) / 이름 있는 개인 {len([i for i in ids if i.startswith('P_')]) - 5}명")
    st = pd.concat([master.subject_office_status, master.object_office_status]).dropna()
    add(m, "unique_office_status_values", st.nunique())
    add(m, "unique_policy_domains", f"context_domain(C행) {master.context_domain.dropna().nunique()}종: {';'.join(sorted(master.context_domain.dropna().unique()))}")
    add(m, "duplicate_rows", int(master.drop(columns="csv_row_number").duplicated().sum()))
    add(m, "duplicate_event_id", int(master.event_id.duplicated().sum()))
    crit = ["event_id", "date_lunar", "time_precision", "subject_id", "object_id", "relation_type", "source_url"]
    add(m, "missing_critical_fields", "; ".join(f"{c}={int(master[c].isna().sum())}" for c in crit)
        + " (source_url 4건은 STATE_GAP 연구공백 행)")

    lname = "office_rank_lookup.csv"
    add(lname, "row_count", len(lk))
    add(lname, "column_names", ";".join(c for c in lk.columns if c != "lookup_row_number"))
    add(lname, "date_range", "NA (시간 정보 없음)")
    add(lname, "unique_person_count", "NA (인물 없음)")
    add(lname, "unique_office_status_values", f"raw_office_status {lk.raw_office_status.nunique()} / normalized_office_title {lk.normalized_office_title.nunique()}")
    add(lname, "unique_policy_domains", f"NA (administrative_scope {lk.administrative_scope.nunique()}종)")
    add(lname, "duplicate_rows", int(lk.drop(columns="lookup_row_number").duplicated().sum()))
    add(lname, "duplicate_raw_office_status", int(lk.raw_office_status.duplicated().sum()))
    crit = ["raw_office_status", "statutory_rank", "rank_fixedness", "rank_visualizable", "verification_status"]
    add(lname, "missing_critical_fields", "; ".join(f"{c}={int(lk[c].isna().sum())}" for c in crit)
        + f"; rank_numeric 빈 값 {int(lk.rank_numeric.isna().sum())} (비고정·전직 — 정상)")

    pname = "jeongjo_policy_timeline.csv"
    add(pname, "row_count", len(pol))
    add(pname, "column_names", ";".join(c for c in pol.columns if c != "csv_row_number"))
    add(pname, "date_range", f"{pol.sort_key.min()} ~ {pol.sort_key.max()} (sort_key; 서기 연도+조선 음력 월일)")
    add(pname, "unique_person_count", "NA (인물 컬럼 없음)")
    add(pname, "unique_office_status_values", "NA")
    add(pname, "unique_policy_domains", f"{pol.broad_domain.nunique()}종: " + "; ".join(
        f"{k}={v}" for k, v in pol.broad_domain.value_counts().items()))
    add(pname, "unique_policy_episodes", f"{pol.policy_episode_id.nunique()}종")
    add(pname, "calendar_basis", "; ".join(f"{k}={v}" for k, v in pol.calendar_basis.value_counts().items())
        + " (JOSEON_REGNAL_DATE 2건도 변환하지 않고 같은 명목 음력 축에 표시)")
    add(pname, "duplicate_rows", int(pol.drop(columns="csv_row_number").duplicated().sum()))
    add(pname, "duplicate_policy_event_id", int(pol.policy_event_id.duplicated().sum()))
    crit = ["policy_event_id", "policy_episode_id", "broad_domain", "policy_title", "year", "month", "day",
            "sort_key", "date_precision", "project_relevance", "source_url"]
    add(pname, "missing_critical_fields", "; ".join(f"{c}={int(pol[c].isna().sum())}" for c in crit))
    return pd.DataFrame(rows)


def master_context_crosswalk(master: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    """master의 맥락 정책 행(C*)과 정책 CSV를 '같은 음력 날짜'로만 대응. 병합하지 않는다."""
    c = master[master.phase == "macro_context"]
    rows = []
    for _, r in c.iterrows():
        hit = p[p.date_lunar == r.date_lunar]
        rows.append(dict(master_event_id=r.event_id, master_date=r.date_lunar, master_object=r.object_name_ko,
                         policy_event_id=";".join(hit.policy_event_id) or gp.NA,
                         policy_title=";".join(hit.policy_title) or gp.NA,
                         match_basis="SAME_DATE_LUNAR" if len(hit) else "NO_SAME_DATE_POLICY_ROW",
                         action="대응만 기록; 두 행을 병합하지 않음. 대시보드 정책 layer는 정책 CSV만 사용"))
    return pd.DataFrame(rows)


def context_windows(events: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    """구순 사건 × 정책: same / previous / next year + 그 이전에 시작한 지속 제도(종료 기록 없음)."""
    g = events[events.person_id.isin(gp.EGO) & (events.phase != "gap")
               & ~events.event_id.isin(gp.KIN_CONTEXT_ROWS)]
    rows = []
    for _, e in g.iterrows():
        ey = int(e.record_date_raw[:4])
        e_lo = gp.lord(e.earliest_possible) if gp.is_day(e.earliest_possible) else None
        e_hi = gp.lord(e.latest_possible) if gp.is_day(e.latest_possible) else e_lo
        for _, q in p.iterrows():
            py = int(q.year_int)
            q_o = gp.lord(q.date_lunar)
            if py == ey:
                win = "SAME_YEAR"
            elif py == ey - 1:
                win = "PREVIOUS_YEAR"
            elif py == ey + 1:
                win = "NEXT_YEAR"
            elif py < ey - 1 and q.persistence_class.startswith("PERSISTENT"):
                win = "ONGOING_CONTEXT_STARTED_EARLIER"
            else:
                continue
            if e_lo is None:
                order = "UNRESOLVED"
            elif q_o < e_lo:
                order = "POLICY_BEFORE_EVENT"
            elif q_o > e_hi:
                order = "POLICY_AFTER_EVENT"
            else:
                order = "SAME_DAY_OR_WITHIN_EVENT_DATE_RANGE"
            rows.append(dict(
                gusun_event_id=e.event_id, gusun_person_id=e.person_id, gusun_record_date=e.record_date_raw,
                gusun_time_precision=e.time_precision, gusun_event_type=e.event_type,
                gusun_office_or_status=e.office_name, gusun_career_state=e.career_state,
                policy_event_id=q.policy_event_id, policy_episode_id=q.policy_episode_id,
                broad_domain=q.broad_domain, policy_title=q.policy_title, policy_date_lunar=q.date_lunar,
                project_relevance=q.project_relevance, persistence_class=q.persistence_class,
                window_class=win, relative_order=order,
                nominal_month_offset=(py * 12 + int(q.month_int)) - (ey * 12 + int(e.record_date_raw[5:7] or 1)
                                                                     if len(e.record_date_raw) >= 7 else 0),
                relationship="CONTEMPORANEITY_ONLY (인과 주장 없음)",
                window_rule="연도 필드 비교(same/prev/next year); ONGOING=이전에 시작한 지속 제도, 종료일 미기록",
                evidence_status="DERIVED (temporal alignment)"))
    return pd.DataFrame(rows)


def validate(res, rk, p_raw, p_norm, net_attempts) -> pd.DataFrame:
    rows = []

    def add(n, layer, name, result, detail):
        rows.append(dict(check_no=n, layer=layer, check=name, result=result, detail=detail))

    rv = rk["rank_val"].set_index("check_no")
    for n, src in [(1, 1), (2, 2), (3, 3)]:
        add(n, "OFFICE_LOOKUP", rv.loc[src, "check"], rv.loc[src, "result"], rv.loc[src, "detail"])
    add(4, "OFFICE_LOOKUP", rv.loc[5, "check"], rv.loc[5, "result"], rv.loc[5, "detail"])
    add(5, "OFFICE_LOOKUP", rv.loc[6, "check"], rv.loc[6, "result"], rv.loc[6, "detail"])

    # 6 sort_key vs y-m-d
    bad = []
    for _, r in p_raw.iterrows():
        y, m, d = int(r.year), int(r.month), int(r.day)
        if r.sort_key != f"{y:04d}{m:02d}{d:02d}" or r.date_lunar != f"{y:04d}-{m:02d}-{d:02d}":
            bad.append(r.policy_event_id)
    order_sk = list(p_raw.sort_values("sort_key").policy_event_id)
    order_ymd = list(p_raw.assign(_k=p_raw[["year", "month", "day"]].astype(int).apply(tuple, axis=1))
                     .sort_values("_k", kind="stable").policy_event_id)
    same_order = [x for x in order_sk] == order_ymd or (
        p_raw.sort_values("sort_key")[["year", "month", "day"]].astype(int).apply(tuple, axis=1).is_monotonic_increasing)
    add(6, "POLICY", "sort_key와 year-month-day(·date_lunar) 순서 일치", "PASS" if not bad and same_order else "FAIL",
        f"불일치 {bad}" if bad else f"{len(p_raw)}행 모두 sort_key=YYYYMMDD=date_lunar, 정렬 순서 동일")
    dup = p_raw.policy_event_id[p_raw.policy_event_id.duplicated()].tolist()
    add(7, "POLICY", "동일 policy_event_id 중복", "PASS" if not dup else "FAIL", f"중복 {dup}" if dup else "없음")
    bad = p_raw[(p_raw.date_precision == "EXACT_DAY") & (p_raw.month.isna() | p_raw.day.isna())].policy_event_id.tolist()
    add(8, "POLICY", "EXACT_DAY인데 month/day 없음", "PASS" if not bad else "FAIL", f"위반 {bad}" if bad else
        f"EXACT_DAY {int((p_raw.date_precision == 'EXACT_DAY').sum())}행 모두 월·일 있음")
    bad = sorted(set(p_raw.broad_domain) - set(DOMAINS))
    add(9, "POLICY", "broad_domain vocabulary", "PASS" if not bad else "FAIL", f"미정의 {bad}" if bad else
        f"6개 vocabulary 내: {', '.join(sorted(set(p_raw.broad_domain)))}")
    bad = []
    for ep, g in p_raw.assign(_n=p_raw.policy_event_id.str[2:].astype(int)).sort_values("_n").groupby("policy_episode_id"):
        sk = g.sort_key.astype(int).tolist()
        if sk != sorted(sk):
            bad.append(ep)
    add(10, "POLICY", "policy episode 내 날짜 역전 (policy_event_id 순서 기준)", "PASS" if not bad else "FAIL",
        f"역전 {bad}" if bad else f"{p_raw.policy_episode_id.nunique()}개 episode 모두 id 순서=날짜 순서")
    n_url = int(p_raw.source_url.notna().sum())
    add(11, "POLICY", "source_url 존재하되 실제 접속하지 않음", "PASS" if not net_attempts else "FAIL",
        f"source_url {n_url}/{len(p_raw)}행 존재; 런타임 소켓 연결 시도 {len(net_attempts)}건")

    v = res["val"].set_index("check_no")
    for n, src in [(12, 1), (13, 2), (14, 3), (15, 6)]:
        add(n, "TEMPORAL", v.loc[src, "check"], v.loc[src, "result"], v.loc[src, "detail"])

    persons, edges = res["persons"], res["edges"]
    pol_ids = set(p_raw.policy_event_id) | set(p_raw.policy_episode_id)
    node_hits = sorted((set(persons.person_id) | set(edges.source_person) | set(edges.target_person))
                       & (pol_ids | {i for i in persons.person_id if str(i).startswith("POL_")}))
    add(16, "NETWORK", "정책을 사람 node로 잘못 넣지 않음", "PASS" if not node_hits else "FAIL",
        f"위반 {node_hits}" if node_hits else
        f"정책 id {len(pol_ids)}개·master POL_* 노드 모두 persons/edges에 없음")
    bad = edges[edges.source_event_id.astype(str).str.contains("JP") |
                (edges.phase == "macro_context")].edge_id.tolist()
    add(17, "NETWORK", "정책–인물 인과 edge를 임의 생성하지 않음", "PASS" if not bad else "FAIL",
        f"위반 {bad}" if bad else "정책 행·master 맥락(C) 행에서 파생된 edge 0개; 정책과는 동시성 표(window)만 존재")
    return pd.DataFrame(rows)


def build(res, rk, net_attempts) -> dict:
    path, pol = load_policy()
    pn = normalize_policy(pol)
    audit = input_audit(res["df"], rk["lookup"], pol)
    cross = master_context_crosswalk(res["df"], pn)
    win = context_windows(res["events"], pn)
    val = validate(res, rk, pol, pn, net_attempts)
    pn.drop(columns=["year_int", "month_int", "day_int", "sort_key_int"]).to_csv(
        gp.OUT / "gusun_policy_timeline_normalized.csv", index=False, encoding="utf-8-sig")
    audit.to_csv(gp.OUT / "gusun_input_audit.csv", index=False, encoding="utf-8-sig")
    cross.to_csv(gp.OUT / "gusun_master_context_vs_policy_crosswalk.csv", index=False, encoding="utf-8-sig")
    win.to_csv(gp.OUT / "gusun_policy_context_windows.csv", index=False, encoding="utf-8-sig")
    val.to_csv(gp.OUT / "gusun_context_validation.csv", index=False, encoding="utf-8-sig")
    # 구순 사건 정규화본 (events + lookup 결합 + 시각화 좌표 표시)
    J = rk["joined"].set_index("event_id")
    ev = res["events"].copy()
    for c in ["normalized_office_title", "office_title_hanja", "record_type", "statutory_rank", "rank_numeric",
              "rank_fixedness", "rank_visualizable", "former_statutory_rank", "office_lookup_match_status",
              "office_lookup_verification_status", "personal_rank"]:
        ev["lookup_" + c if c in ("record_type",) else c] = ev.event_id.map(J[c])
    ev["lookup_administrative_scope"] = ev.event_id.map(J["administrative_scope"])
    ev["current_rank_numeric"] = ev["rank_numeric"]
    ev["derived_plot_x_start"] = ev.plot_x_start
    ev["derived_plot_x_end"] = ev.plot_x_end
    ev["derived_plot_evidence_status"] = "DERIVED_FOR_VISUALIZATION"
    ev["date_as_recorded"] = ev.record_date_raw  # YYYY / YYYY-MM / YYYY-MM-DD 정밀도 보존
    ev.to_csv(gp.OUT / "gusun_temporal_events_normalized.csv", index=False, encoding="utf-8-sig")
    return dict(path=path, raw=pol, norm=pn, audit=audit, cross=cross, windows=win, val=val, events_norm=ev)
