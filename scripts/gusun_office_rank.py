"""관직의 '법정·제도적 품계' lookup 결합 (office_rank_lookup.csv).

- lookup의 품계는 **관직 자체의 법정 품계**다. 구순 개인의 실제 품계(personal_rank)가 아니다.
- 조인 키: master의 subject/object_office_status ↔ lookup.raw_office_status (LEFT JOIN, 행 수 불변).
- 매칭 단계: EXACT → NORMALIZED(NFKC·공백 정리만) → UNMATCHED. 부분 문자열·유사도 매칭(fuzzy)은 하지 않는다.
- rank_numeric은 시각화 Y축 정렬용 숫자일 뿐이다 (권력·영향력·개인 품계 아님).
- 전직(FORMER_OFFICIAL)은 현재 rank_numeric을 비우고 former_statutory_rank만 보존한다.
- lookup의 source_url은 메타데이터로만 보존하고 접속하지 않는다.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

import gusun_pipeline as gp

LOOKUP_COLS = ["normalized_office_title", "office_title_hanja", "record_type", "administrative_scope",
               "statutory_rank", "rank_numeric", "rank_fixedness", "rank_visualizable",
               "former_statutory_rank"]
RANK_LABEL = {2.0: "정2품", 2.5: "종2품", 3.0: "정3품", 3.5: "종3품", 4.0: "정4품", 4.5: "종4품",
              5.0: "정5품", 5.5: "종5품", 6.0: "정6품", 6.5: "종6품"}

# 품계가 고정되지 않은 직함의 시각화 lane (lookup의 administrative_scope / rank_fixedness에서 결정)
def variable_lane(row) -> str:
    scope, fix = row.get("administrative_scope"), row.get("rank_fixedness")
    if fix == "FORMER_OFFICE":
        return "FORMER_OFFICIAL (career-state band)"
    if scope == "COURT_MILITARY":
        return "COURT_MILITARY_VARIABLE"
    if scope == "SPECIAL_ENVOY":
        return "SPECIAL_MISSION"
    if fix == "UNRANKED_CLERICAL":
        return "CLERICAL"
    if fix == "NO_SINGLE_STATUTORY_RANK":
        return "MILITARY_STAFF"
    return "OTHER_VARIABLE"


# UNMATCHED 값의 성격 분류 (결정론적 목록; 결합에는 쓰지 않음)
UNMATCHED_KIND = [
    ("PENAL_OR_CAREER_STATE", ["죄인", "정배", "피수사자", "수감자", "석방", "형기", "노비 처분"]),
    ("POSSIBLE_OFFICE_NOT_IN_LOOKUP", ["체포 장교", "별군직 청수", "중영 하급 실무자", "병영·진영 실무자",
                                       "영흥부 아전"]),
    ("RULER_OR_INSTITUTION", ["국왕", "정부", "관서", "관청", "사법기관", "대외 상대국", "국가 성역"]),
    ("NON_OFFICE_PERSON_OR_HOUSEHOLD", ["민간인", "반족", "이웃", "처", "남편", "종형", "아들", "집 종",
                                        "하인"]),
    ("POLICY_EVENT_OR_LIST", ["규정", "법전", "지침", "정책", "교육", "기록", "사건", "체계", "시험",
                              "행정"]),
]


def unmatched_kind(v: str) -> str:
    for kind, kws in UNMATCHED_KIND:
        if any(k in v for k in kws):
            return kind
    return "UNCLASSIFIED"


def norm_key(s: str) -> str:
    """허용된 정규화: 유니코드 NFKC + 앞뒤 공백 제거 + 연속 공백 1칸. 그 외 변형 없음."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip()


def find_lookup() -> Path:
    c = [p for p in gp.ROOT.rglob("office_rank_lookup.csv") if gp.OUT not in p.parents]
    if not c:
        raise FileNotFoundError("office_rank_lookup.csv not found")
    return sorted(c, key=lambda p: p.stat().st_mtime)[-1]


def load_lookup(path: Path) -> pd.DataFrame:
    lk = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
    lk["rank_numeric"] = pd.to_numeric(lk["rank_numeric"], errors="coerce")
    lk["rank_visualizable"] = pd.to_numeric(lk["rank_visualizable"], errors="coerce").astype("Int64")
    lk["lookup_row_number"] = range(2, len(lk) + 2)
    return lk


def match_one(raw, lk_exact: dict, lk_norm: dict):
    """반환: (match_status, lookup_row or None, matched_key)."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "NO_VALUE", None, gp.NA
    if raw in lk_exact:
        return "EXACT", lk_exact[raw], raw
    nk = norm_key(raw)
    if nk in lk_norm and len(lk_norm[nk]) == 1:
        row = lk_norm[nk][0]
        return "NORMALIZED", row, row["raw_office_status"]
    return "UNMATCHED", None, gp.NA


def build(res: dict) -> dict:
    lk_path = find_lookup()
    lk = load_lookup(lk_path)
    raw = res["df"]
    ev = res["events"].set_index("event_id")
    lk_exact = {r.raw_office_status: r for _, r in lk.iterrows()}
    lk_norm: dict = {}
    for _, r in lk.iterrows():
        lk_norm.setdefault(norm_key(r.raw_office_status), []).append(r)

    out_rows, audit_long = [], []
    for _, r in raw.iterrows():
        e = ev.loc[r.event_id]
        side = gp.gusun_side(r)
        focal_side = side or "subject"
        rec = {c: r[c] for c in raw.columns if c != "csv_row_number"}
        rec["csv_row_number"] = r.csv_row_number
        for s in ("subject", "object"):
            val = r[f"{s}_office_status"]
            st, row, key = match_one(val, lk_exact, lk_norm)
            rec[f"{s}_office_lookup_match_status"] = st
            rec[f"{s}_office_lookup_key"] = key
            for c in LOOKUP_COLS + ["verification_status"]:
                v = row[c] if row is not None else None
                rec[f"{s}_{c}"] = v
            audit_long.append(dict(event_id=r.event_id, side=s, raw_office_status=val, match_status=st,
                                   matched_lookup_key=key,
                                   lookup_row_number=row["lookup_row_number"] if row is not None else None))
        # 요청 컬럼 = 사건의 focal 인물(구순이 있으면 구순 쪽, 없으면 subject) 기준
        p = f"{focal_side}_"
        rec["focal_side"] = focal_side
        rec["focal_person_id"] = e.person_id
        rec["focal_raw_office_status"] = r[f"{focal_side}_office_status"]
        for c in LOOKUP_COLS:
            rec[c] = rec[p + c]
        rec["office_lookup_match_status"] = rec[p + "office_lookup_match_status"]
        rec["office_lookup_verification_status"] = rec[p + "verification_status"]
        # 전직은 현재 rank_numeric을 비운다 (lookup이 이미 비워 두었지만 규칙으로 강제)
        lookup_former = rec["rank_fixedness"] == "FORMER_OFFICE"
        if side:
            career_state = e.career_state
            career_state_after = e.career_state_after
            cs_basis = "gusun_events.career_state (CSV 신분 라벨 분해)"
        else:
            career_state = "FORMER_OFFICIAL" if lookup_former else gp.UNKNOWN
            career_state_after = career_state
            cs_basis = "lookup rank_fixedness=FORMER_OFFICE" if lookup_former else "비-구순 인물: CSV에 상태 정보 없음"
        rec["career_state"] = career_state
        rec["career_state_after"] = career_state_after
        rec["career_state_basis"] = cs_basis
        if career_state == "FORMER_OFFICIAL" or lookup_former:
            rec["rank_numeric_blanked_reason"] = "FORMER_OFFICIAL: 현재 품계 없음" if pd.notna(rec["rank_numeric"]) \
                else gp.NA
            rec["rank_numeric"] = None
        else:
            rec["rank_numeric_blanked_reason"] = gp.NA
        rec["rank_lane"] = (RANK_LABEL.get(rec["rank_numeric"], str(rec["rank_numeric"]))
                            if pd.notna(rec["rank_numeric"]) else
                            (variable_lane(rec) if rec["office_lookup_match_status"] in ("EXACT", "NORMALIZED")
                             else gp.NA))
        rec["personal_rank"] = ("당상관 (E002 노상추일기 전언; 공식 임명문 아님)" if r.event_id == "E002"
                                else gp.NA)
        rec["personal_rank_note"] = "statutory_rank는 관직 자체의 법정 품계이며 개인 품계가 아님"
        rec["rank_numeric_meaning"] = "VISUALIZATION_SORT_ONLY (권력·영향력·개인 품계 아님)"
        # 시간 필드 (앞 단계 정규화 결과)
        for c in ("event_start", "event_end", "earliest_possible", "latest_possible", "time_precision",
                  "plot_x_start", "plot_x_end"):
            rec[c] = e[c]
        rec["rule_scope_v1"] = e.administrative_scope  # 이전 단계 관직명 규칙 결과 (비교용)
        rec["office_rank_evidence_status"] = ("DERIVED (lookup join)" if rec["office_lookup_match_status"]
                                              in ("EXACT", "NORMALIZED") else "NA (unmatched)")
        out_rows.append(rec)
    joined = pd.DataFrame(out_rows)

    # 감사 테이블: 고유 값 단위
    al = pd.DataFrame(audit_long)
    al = al[al.match_status != "NO_VALUE"]
    audit = (al.groupby(["raw_office_status", "match_status", "matched_lookup_key"], dropna=False)
               .agg(n_occurrences=("event_id", "size"),
                    sides=("side", lambda s: ";".join(sorted(set(s)))),
                    event_ids=("event_id", lambda s: ";".join(sorted(set(s)))),
                    lookup_row_number=("lookup_row_number", "first"))
               .reset_index())
    lkx = lk.set_index("raw_office_status")
    for c in ["normalized_office_title", "statutory_rank", "rank_numeric", "rank_fixedness",
              "former_statutory_rank", "verification_status"]:
        audit[c] = audit.matched_lookup_key.map(lambda k: lkx.loc[k, c] if k in lkx.index else None)
    audit["unmatched_kind"] = audit.apply(lambda a: unmatched_kind(a.raw_office_status)
                                          if a.match_status == "UNMATCHED" else gp.NA, axis=1)
    audit["action"] = audit.apply(lambda a: {
        "EXACT": "JOINED", "NORMALIZED": "JOINED (NFKC/공백 정규화만)",
        "UNMATCHED": ("LOOKUP 추가 후보 — 자동 fuzzy 매칭하지 않음"
                      if a.unmatched_kind == "POSSIBLE_OFFICE_NOT_IN_LOOKUP" else "결합 대상 아님 (관직 아님)")
    }[a.match_status], axis=1)
    audit["fuzzy_used"] = False
    unused = sorted(set(lk.raw_office_status) - set(audit.matched_lookup_key))
    if unused:
        audit = pd.concat([audit, pd.DataFrame([dict(raw_office_status=k, match_status="LOOKUP_UNUSED",
                                                     matched_lookup_key=k, n_occurrences=0,
                                                     action="lookup 행이 master에 등장하지 않음")
                                                for k in unused])], ignore_index=True)
    order = {"EXACT": 0, "NORMALIZED": 1, "UNMATCHED": 2, "LOOKUP_UNUSED": 3}
    audit = audit.sort_values(["match_status", "n_occurrences"], key=lambda s: s.map(order) if s.name ==
                              "match_status" else -s).reset_index(drop=True)

    # 이전 규칙 scope와 lookup scope 비교 (구순 행)
    g = joined[joined.focal_person_id.isin(gp.EGO) & joined.office_lookup_match_status.isin(["EXACT", "NORMALIZED"])]
    scope_cmp = (g.groupby(["focal_raw_office_status", "rule_scope_v1", "administrative_scope"])
                  .size().reset_index(name="n_rows"))

    val = validate(raw, lk, joined, al)
    return dict(lookup=lk, lookup_path=lk_path, joined=joined, audit=audit, scope_cmp=scope_cmp,
                rank_val=val, audit_long=al)


def validate(raw, lk, joined, al) -> pd.DataFrame:
    res = []

    def chk(n, name, ok, detail):
        res.append(dict(check_no=n, check=name, result="PASS" if ok else "FAIL", detail=detail))

    # 1 FIXED인데 rank_numeric 없음 (lookup 및 조인 결과; 전직 blank는 FIXED가 아니므로 해당 없음)
    b1 = lk[(lk.rank_fixedness == "FIXED") & lk.rank_numeric.isna()].raw_office_status.tolist()
    b1 += [f"{r.event_id}:{s}" for _, r in joined.iterrows() for s in ("subject", "object")
           if r[f"{s}_rank_fixedness"] == "FIXED" and pd.isna(r[f"{s}_rank_numeric"])]
    chk(1, "FIXED인데 rank_numeric이 없는 행", not b1, f"위반 {b1}" if b1 else
        f"lookup FIXED {int((lk.rank_fixedness == 'FIXED').sum())}행 모두 값 있음")
    # 2 VARIABLE 등 비고정인데 rank_numeric 있음
    nonfixed = lk.rank_fixedness != "FIXED"
    b2 = lk[nonfixed & lk.rank_numeric.notna()].raw_office_status.tolist()
    b2 += [f"{r.event_id}:{s}" for _, r in joined.iterrows() for s in ("subject", "object")
           if pd.notna(r[f"{s}_rank_fixedness"]) and r[f"{s}_rank_fixedness"] != "FIXED"
           and pd.notna(r[f"{s}_rank_numeric"])]
    b2 += [r.event_id for _, r in joined.iterrows()
           if pd.notna(r.rank_fixedness) and r.rank_fixedness != "FIXED" and pd.notna(r.rank_numeric)]
    chk(2, "VARIABLE/비고정인데 rank_numeric이 들어간 행", not b2, f"위반 {b2}" if b2 else
        f"비고정 lookup {int(nonfixed.sum())}행 ({', '.join(sorted(lk[nonfixed].rank_fixedness.unique()))}) 모두 빈 값")
    # 3 FORMER_OFFICIAL인데 현재 rank_numeric
    b3 = joined[(joined.career_state == "FORMER_OFFICIAL") & joined.rank_numeric.notna()].event_id.tolist()
    b3 += joined[(joined.rank_fixedness == "FORMER_OFFICE") & joined.rank_numeric.notna()].event_id.tolist()
    n_former = int((joined.career_state == "FORMER_OFFICIAL").sum())
    chk(3, "FORMER_OFFICIAL인데 현재 rank_numeric이 들어간 행", not b3, f"위반 {b3}" if b3 else
        f"FORMER_OFFICIAL 행 {n_former}개 모두 rank_numeric 비움 (former_statutory_rank만 보존)")
    # 4 동일 raw_office_status → 서로 다른 fixed rank
    dup = (lk[lk.rank_fixedness == "FIXED"].groupby("raw_office_status").rank_numeric.nunique())
    b4 = dup[dup > 1].index.tolist() + lk[lk.raw_office_status.duplicated(keep=False)].raw_office_status.tolist()
    normdup = pd.Series([norm_key(k) for k in lk.raw_office_status])
    b4 += normdup[normdup.duplicated(keep=False)].tolist()
    chk(4, "동일 raw_office_status가 서로 다른 fixed rank로 중복 매핑", not b4,
        f"위반 {sorted(set(b4))}" if b4 else f"lookup 키 {len(lk)}개 모두 유일 (정규화 후에도 유일)")
    # 5 unmatched
    um = al[al.match_status == "UNMATCHED"]
    kinds = um.raw_office_status.map(unmatched_kind).value_counts().to_dict()
    cand = sorted(um[um.raw_office_status.map(unmatched_kind) == "POSSIBLE_OFFICE_NOT_IN_LOOKUP"]
                  .raw_office_status.unique())
    res.append(dict(check_no=5, check="unmatched office status (보고 항목)", result="REPORTED",
                    detail=f"고유값 {um.raw_office_status.nunique()}개 / 출현 {len(um)}회; 성격 {kinds}; "
                           f"lookup 추가 후보(직함처럼 보이나 키 없음): {cand}"))
    # 6 행 수 불변
    chk(6, "join 후 temporal network 원본 행 수 불변", len(joined) == len(raw) and
        joined.event_id.tolist() == raw.event_id.tolist(),
        f"원본 {len(raw)}행 → 결합 {len(joined)}행, event_id 순서 동일={joined.event_id.tolist() == raw.event_id.tolist()}")
    # 7 fuzzy 없음: 모든 매칭이 정확 일치 또는 정규화 일치인지 재검산
    bad = []
    for _, a in al.iterrows():
        if a.match_status == "EXACT" and a.raw_office_status != a.matched_lookup_key:
            bad.append(a.event_id)
        if a.match_status == "NORMALIZED" and norm_key(a.raw_office_status) != norm_key(a.matched_lookup_key):
            bad.append(a.event_id)
    near = sorted({a.raw_office_status for _, a in al[al.match_status == "UNMATCHED"].iterrows()
                   if any(k in a.raw_office_status for k in ("장교", "별군직", "실무자"))})
    chk(7, "fuzzy merge가 발생하지 않음", not bad,
        f"재검산 위반 {bad}" if bad else
        f"EXACT {int((al.match_status == 'EXACT').sum())}회·NORMALIZED {int((al.match_status == 'NORMALIZED').sum())}회 "
        f"모두 문자열 동일성으로 재확인; 부분 문자열이 겹치지만 결합하지 않은 값: {near}")
    return pd.DataFrame(res)


def write(rk: dict):
    rk["joined"].to_csv(gp.OUT / "gusun_temporal_network_with_office_rank.csv", index=False, encoding="utf-8-sig")
    rk["audit"].to_csv(gp.OUT / "gusun_office_lookup_join_audit.csv", index=False, encoding="utf-8-sig")
    rk["rank_val"].to_csv(gp.OUT / "gusun_office_rank_validation.csv", index=False, encoding="utf-8-sig")
    rk["scope_cmp"].to_csv(gp.INT / "09_office_scope_rule_vs_lookup.csv", index=False, encoding="utf-8-sig")
