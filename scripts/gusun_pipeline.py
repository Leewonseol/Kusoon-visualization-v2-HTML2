"""
구순(具純) Temporal Multiplex Ego Network — 데이터 파이프라인.

입력은 gusun_temporal_network_master_v0_2.csv 하나뿐이다.
- 외부 웹/URL/API 접근을 하지 않는다 (source_url은 provenance 문자열로만 보존).
- CSV에 없는 인물·관직·친족관계·사건을 만들지 않는다.
- 모든 파생값에는 evidence_status(OBSERVED / DERIVED / INFERRED / DERIVED_FOR_VISUALIZATION)를 붙인다.

날짜는 CSV의 date_lunar(음력) 그대로 사용한다. 양력 환산은 외부 역법표가 필요하므로 하지 않는다.
정렬·시각화용으로만 '명목 음력 서수'(1년=12개월×30일)를 만든다 — DERIVED_FOR_VISUALIZATION.
"""
from __future__ import annotations

import itertools
import json
import re
from pathlib import Path

import networkx as nx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
INT = OUT / "intermediate"

UNKNOWN, OPEN, NA = "UNKNOWN", "OPEN", "NA"

RELATION_VOCAB = [
    "KINSHIP", "HOUSEHOLD", "NEIGHBOR", "FRIENDLY_ASSOCIATION", "CONFLICT", "ACCUSATION",
    "TESTIMONY", "INVESTIGATION", "DETENTION", "COMMAND", "OFFICIAL_COLLEAGUE",
    "OFFICIAL_SUPERIOR", "OFFICIAL_SUBORDINATE", "PUNISHMENT", "REPORT", "REEXAMINATION", "OTHER",
]
SYMMETRIC = {"KINSHIP", "HOUSEHOLD", "NEIGHBOR", "FRIENDLY_ASSOCIATION", "OFFICIAL_COLLEAGUE"}

# 분석용 관계군 (사용자 지정 7개 + PRIVATE_SOCIAL: NEIGHBOR·FRIENDLY_ASSOCIATION을 OTHER에 묻지 않기 위한 분리)
RELATION_GROUP = {
    "KINSHIP": "KINSHIP", "HOUSEHOLD": "HOUSEHOLD",
    "NEIGHBOR": "PRIVATE_SOCIAL", "FRIENDLY_ASSOCIATION": "PRIVATE_SOCIAL",
    "OFFICIAL_COLLEAGUE": "OFFICIAL", "OFFICIAL_SUPERIOR": "OFFICIAL",
    "OFFICIAL_SUBORDINATE": "OFFICIAL", "COMMAND": "OFFICIAL",
    "CONFLICT": "CONFLICT", "ACCUSATION": "CONFLICT",
    "INVESTIGATION": "INVESTIGATION", "TESTIMONY": "INVESTIGATION", "DETENTION": "INVESTIGATION",
    "REPORT": "INVESTIGATION", "REEXAMINATION": "INVESTIGATION",
    "PUNISHMENT": "PUNISHMENT", "OTHER": "OTHER",
}
GROUP_ORDER = ["OFFICIAL", "CONFLICT", "INVESTIGATION", "PRIVATE_SOCIAL", "HOUSEHOLD",
               "KINSHIP", "PUNISHMENT", "OTHER"]

# CSV relation_type(원문 78종 중 비맥락 행) → (정규화 relation_type, event_type)
# None = 인물 간 관계가 아님(사건/정책/상태 노드) → edge를 만들지 않는다.
RELATION_MAP = {
    "FATHER_CAREER_CONTEXT": (None, "KIN_CAREER_CONTEXT"),
    "APPOINTED_AS": ("OFFICIAL_SUPERIOR", "CAREER_APPOINTMENT"),
    "PERFORMANCE_RECOGNIZED": (None, "CAREER_ACTIVITY"),
    "SERVES_IN_ROYAL_ENTOURAGE": (None, "CAREER_ACTIVITY"),
    "EXPLICITLY_LINKS_PRIOR_OFFICE": ("OFFICIAL_SUPERIOR", "IDENTITY_BRIDGE_STATEMENT"),
    "DEPARTURE_AUDIENCE": ("OFFICIAL_SUBORDINATE", "CAREER_ACTIVITY"),
    "DISCIPLINES_SUBORDINATE": ("PUNISHMENT", "ADMINISTRATIVE_CONFLICT"),
    "CONFLICT_WITH_SUPERIOR": ("CONFLICT", "ADMINISTRATIVE_CONFLICT"),
    "PUNITIVE_RETALIATION": ("CONFLICT", "ADMINISTRATIVE_CONFLICT"),
    "ORDERED_NAB_INTERROGATION": ("INVESTIGATION", "JUDICIAL_PROCEDURE"),
    "FLAGS_LOW_COLLECTION": ("REPORT", "ADMINISTRATIVE_SCRUTINY"),
    "SPARES_DUE_TO_FAMINE_RELIEF": ("OTHER", "ADMINISTRATIVE_SCRUTINY"),
    "DEFERRED_ARREST": ("INVESTIGATION", "JUDICIAL_PROCEDURE"),
    "REWARDS_RELIEF_PERFORMANCE": ("OFFICIAL_SUPERIOR", "CAREER_REWARD"),
    "EXILES_FOR_EVADING_TEST": ("PUNISHMENT", "PUNISHMENT_SENTENCE"),
    "STATE_GAP": (None, "STATE_GAP"),
    "PRIVATE_CONFLICT": ("CONFLICT", "INTERPERSONAL_CONFLICT"),
    "FALSE_ACCUSATION": ("ACCUSATION", "ACCUSATION_ACT"),
    "IMPLICATES_AS_ASSOCIATE": ("ACCUSATION", "ACCUSATION_ACT"),
    "INSTIGATES": ("OTHER", "ACCUSATION_ACT"),
    "PUNISHES_FALSE_ACCUSATION": ("PUNISHMENT", "PUNISHMENT_SENTENCE"),
    "NOTES_PRIOR_LENIENCY": ("OTHER", "ROYAL_STATEMENT"),
    "REPORTS_ROBBERY": ("REPORT", "REPORT"),
    "REPORTS_OR_EXPANDS_ROBBERY": (None, "CASE_ORIGIN"),
    "ORDERS_ARREST": ("__ARREST__", "ARREST_DETENTION"),
    "PROVIDES_IRON_WHIPS": ("COMMAND", "INVESTIGATION_ACT"),
    "ARRESTS_SUBSTITUTE_TARGET": ("DETENTION", "ARREST_DETENTION"),
    "PROVIDES_ROBBERY_DETAILS": ("REPORT", "REPORT"),
    "PRIOR_FRIENDSHIP": ("FRIENDLY_ASSOCIATION", "INTERPERSONAL_RELATION_STATE"),
    "REBUKES_AND_BREAKS_CONTACT": ("CONFLICT", "INTERPERSONAL_CONFLICT"),
    "PRIVATE_CONTACT_WITH_OFFICER": ("OTHER", "PRIVATE_CONTACT"),
    "PROVIDES_SUSPECT_NAME": ("REPORT", "REPORT"),
    "SUBMITS_SUSPECT_LIST": ("REPORT", "REPORT"),
    "COERCES_FALSE_IDENTIFICATION": ("INVESTIGATION", "INVESTIGATION_ACT"),
    "FALSE_IDENTIFICATION_UNDER_COERCION": ("TESTIMONY", "TESTIMONY"),
    "ENTERS_SUSPECT_LIST": ("INVESTIGATION", "INVESTIGATION_ACT"),
    "SENDS_LETTER_VIA_OFFICER": ("OTHER", "PRIVATE_CONTACT"),
    "REPORTS_WRONGFUL_CASE": ("INVESTIGATION", "OFFICIAL_REPORT"),
    "CLAIMS_ROBBERY_FABRICATED": ("INVESTIGATION", "OFFICIAL_REPORT"),
    "CRITICIZES_PASSIVE_INVESTIGATION": ("ACCUSATION", "OFFICIAL_REPORT"),
    "ACCUSES_OF_BIASED_WRONGFUL_ARREST": ("ACCUSATION", "OFFICIAL_REPORT"),
    "REQUESTS_DISMISSAL_AND_ARREST": ("PUNISHMENT", "PUNISHMENT_REQUEST"),
    "ORDERS_ARREST_AND_STRICT_INVESTIGATION": ("DETENTION", "ARREST_DETENTION"),
    "ACCUSATION_AS_BANDIT_CHIEF": ("ACCUSATION", "ACCUSATION_ACT"),
    "ALLEGED_INSTRUCTION_TO_SPREAD_RUMOR": ("COMMAND", "ALLEGED_ACT"),
    "ALLEGED_COLLUSION_WITH_OFFICERS": ("OTHER", "ALLEGED_ACT"),
    "REPORTS_INVESTIGATION": ("INVESTIGATION", "OFFICIAL_REPORT"),
    "CLAIMS_HOUSEHOLD_CLIENT_LINK": ("ACCUSATION", "OFFICIAL_REPORT"),
    "DISMISSES_FOR_PROCEDURAL_FAILURE": ("PUNISHMENT", "PUNISHMENT_SENTENCE"),
    "ORDERS_REPEATED_INTERROGATION": ("INVESTIGATION", "JUDICIAL_PROCEDURE"),
    "REINVESTIGATES_AND_REVISES_FACTS": ("REEXAMINATION", "REEXAMINATION"),
    "DENIES_PRIOR_ACQUAINTANCE": ("TESTIMONY", "TESTIMONY"),
    "FINDS_DEATH_BY_DISEASE": ("REEXAMINATION", "REEXAMINATION"),
    "SIDES_WITH_AFTER_FAMILY_FEUD": ("FRIENDLY_ASSOCIATION", "INTERPERSONAL_RELATION_STATE"),
    "BIASED_INVESTIGATION": ("INVESTIGATION", "INVESTIGATION_ACT"),
    "WRONGFUL_ARRESTS_AND_CASE_FORGING": ("DETENTION", "ARREST_DETENTION"),
    "DEATH_REDUCED_REMOTE_ISLAND_EXILE": ("PUNISHMENT", "PUNISHMENT_SENTENCE"),
    "REMOTE_EXILE": ("PUNISHMENT", "PUNISHMENT_SENTENCE"),
    "HEAVY_FLOGGING_AND_ENSLAVEMENT": ("PUNISHMENT", "PUNISHMENT_SENTENCE"),
    "DISMISSES_FOR_REPORT_DISCREPANCY": ("PUNISHMENT", "PUNISHMENT_SENTENCE"),
    "TRANSFER_EXILE": ("PUNISHMENT", "EXILE_TRANSFER"),
    "REPORTS_TERM_EXPIRED": ("REPORT", "OFFICIAL_REPORT"),
    "RECOMMENDS_RELEASE": ("REEXAMINATION", "JUDICIAL_PROCEDURE"),
    "RELEASES": ("PUNISHMENT", "RELEASE"),
}

# 네트워크 actor 종류. 여기에 없는 id(POL_*, 사건·명단·상태 노드)는 네트워크에서 제외.
NODE_KIND = {
    "P_STATE": "INSTITUTION", "P_BIBEONSA": "INSTITUTION", "P_UIGEUMBU": "INSTITUTION",
    "P_JOSEON": "STATE_CONTEXT", "P_QING": "STATE_CONTEXT",
    "N_HOUSE_SERVANTS": "COLLECTIVE", "N_MILITARY_SOLDIERS": "COLLECTIVE",
    "N_INNOCENT_COMMONERS": "COLLECTIVE", "N_CENTRAL_CAMP_CLERKS": "COLLECTIVE",
    "N_YEONGHEUNG_CLERK": "COLLECTIVE_OR_UNNAMED", "N_UNNAMED_OFFICER": "UNNAMED_PERSON",
}
NON_ACTOR_PREFIXES = ("POL_", "N_UNKNOWN", "N_POST1798", "N_ROBBERY_EVENT", "N_MILITARY_EXAM",
                      "N_ROYAL_ENTOURAGE")

SEGMENT_MAP = {"GU_PRE1793": "GUSUN_PRE1793", "GU_1793PLUS": "GUSUN_1793PLUS"}

# 구순 신분 라벨(CSV 원문) → office/tenure/career_state 분리.
# office_name은 CSV 문자열에서만 가져온다. 품계(official_rank)는 CSV에 없으므로 NA.
GUSUN_STATUS = {
    "아들(후대 관계자료와 결합)": (NA, UNKNOWN, UNKNOWN),
    "선전관/별군직 계열": ("선전관/별군직 계열", "IN_OFFICE", "ACTIVE"),
    "선전관→별군직": ("별군직", "IN_OFFICE", "ACTIVE"),
    "선전관": ("선전관", "IN_OFFICE", "ACTIVE"),
    "중화부사": ("중화부사", "IN_OFFICE", "ACTIVE"),
    "별군직": ("별군직", "IN_OFFICE", "ACTIVE"),
    "벽동군수": ("벽동군수", "IN_OFFICE", "ACTIVE"),
    "백령첨사": ("백령첨사", "IN_OFFICE", "ACTIVE"),
    "영흥부사": ("영흥부사", "IN_OFFICE", "ACTIVE"),
    "영흥부사·겸영장": ("영흥부사(겸영장)", "IN_OFFICE", "ACTIVE"),
    "정배 상태": (NA, "NONE", "EXILED"),
    "죄인": (NA, "NONE", "UNDER_INVESTIGATION"),
    "제주목 감사정배": (NA, "NONE", "EXILED"),
    "전 부사·민간 거주": ("전 부사(府名 미상)", "FORMER", "FORMER_OFFICIAL"),
    "전 부사·청주 덕평 거주": ("전 부사(府名 미상)", "FORMER", "FORMER_OFFICIAL"),
    "전 부사": ("전 부사(府名 미상)", "FORMER", "FORMER_OFFICIAL"),
    "의금부 피수사자": ("전 부사(府名 미상)", "FORMER", "IMPRISONED"),
    "피수사자": ("전 부사(府名 미상)", "FORMER", "IMPRISONED"),
    "신지도 정배죄인": (NA, "NONE", "EXILED"),
    "장연현 정배": (NA, "NONE", "EXILED"),
    "장연현 도3년 정배죄인": (NA, "NONE", "EXILED"),
    "형기 만료 죄인": (NA, "NONE", "EXILED"),
    "석방 후 민간 상태 추정": (NA, UNKNOWN, UNKNOWN),  # CSV 스스로 '추정'이라 표기 → UNKNOWN
}
# 행 단위 보정: 사건이 career_state를 바꾸는 경우 (before → after)
GUSUN_STATE_OVERRIDE = {
    "E011": ("UNDER_INVESTIGATION", "UNDER_INVESTIGATION"),
    "E015": ("UNDER_INVESTIGATION", "UNDER_INVESTIGATION"),
    "E016": ("UNDER_INVESTIGATION", "ACTIVE"),
    "E017": ("ACTIVE", "EXILED"),
    "E023": ("UNDER_INVESTIGATION", "EXILED"),
    "E050": ("UNDER_INVESTIGATION", "UNDER_INVESTIGATION"),
    "E051": ("UNDER_INVESTIGATION", "UNDER_INVESTIGATION"),
    "E055": ("UNDER_INVESTIGATION", "IMPRISONED"),
    "E066": ("IMPRISONED", "EXILED"),
    "E082": ("EXILED", "RELEASED"),
}

# 관직 차원 규칙표 (DERIVED: 관직명 문자열 규칙. 품계 아님)
# office → (administrative_scope, court_proximity, command_scope, basis)
OFFICE_RULES = {
    "선전관": ("COURT", "HIGH", "NONE_RECORDED",
             "I003 '선전관·별군직 계열'로 별군직과 같은 계열로 묶임"),
    "별군직": ("COURT", "HIGH", "NONE_RECORDED", "E004 결과 '왕실 근거리 무관으로 활동 확인'"),
    "선전관/별군직 계열": ("COURT", "HIGH", "NONE_RECORDED", "I003 표현 그대로"),
    "중화부사": ("LOCAL", "LOW", "중화부", "외임 수령직(관직명 규칙); 관할=CSV location"),
    "벽동군수": ("LOCAL", "LOW", "벽동군", "외임 수령직(관직명 규칙); 관할=CSV location"),
    "백령첨사": ("MILITARY", "LOW", "백령", "첨사=변장 계열(관직명 규칙); CSV I004"),
    "영흥부사": ("LOCAL", "LOW", "영흥부", "E007 '외임으로 떠나는 수령·변장 입시 명단'"),
    "영흥부사(겸영장)": ("LOCAL", "LOW", "영흥부 + 영장 겸임",
                   "E015 support note '겸영장 수령 차겸관'"),
    "전 부사(府名 미상)": ("NONE", "NONE", "NONE", "비현직: 과거 관직 이력일 뿐 현재 관할 없음"),
}
OFFICE_LANE = {  # 경력 storyline Y축 (제도적 위치 범주; 품계 순서가 아님)
    "선전관": "COURT · 선전관", "별군직": "COURT · 별군직", "선전관/별군직 계열": "COURT · 별군직",
    "중화부사": "LOCAL · 중화부사", "벽동군수": "LOCAL · 벽동군수", "백령첨사": "MILITARY · 백령첨사",
    "영흥부사": "LOCAL · 영흥부사", "영흥부사(겸영장)": "LOCAL · 영흥부사",
    "전 부사(府名 미상)": "NONE · 전 부사(비현직)",
}

# 다른 인물들의 관직/신분 라벨 → administrative_scope (DERIVED, 관직명 키워드 규칙)
SCOPE_KEYWORDS = [
    ("국왕", "COURT"), ("별군직", "COURT"), ("선전관", "COURT"),
    ("비변사", "CENTRAL"), ("의금부", "CENTRAL"), ("중앙", "CENTRAL"), ("관청", "CENTRAL"),
    ("어사", "CENTRAL"), ("관찰사", "PROVINCIAL"), ("감사", "PROVINCIAL"),
    ("병마절도사", "MILITARY"), ("중군", "MILITARY"), ("비장", "MILITARY"), ("영리", "MILITARY"),
    ("장교", "MILITARY"), ("영장", "MILITARY"), ("교졸", "MILITARY"), ("중영", "MILITARY"),
    ("군수", "LOCAL"), ("부사", "LOCAL"), ("아전", "LOCAL"),
]

# 구순 기록 클러스터 (동일인 판단 전 '기록 묶음'). event_id 목록은 CSV 행.
GUSUN_RECORD_CLUSTERS = {
    "R1_SEONJEON_BYEOLGUN_1777_1779": ["E001", "E002", "E004"],
    "R2_JUNGHWA_BUSA_1778": ["E003"],
    "R3_BYEOKDONG_GUNSU_1779": ["E005"],
    "R4_BAENGNYEONG_CHEOMSA_1781": ["I004"],
    "R5_YEONGHEUNG_BUSA_1782_1784": ["E006", "E007", "E009", "E010", "E011", "E012", "E013",
                                     "E014", "E015", "E016"],
    "R6_BYEOLGUN_EXILE_1784": ["E017", "E018"],
    "R7_BYEOLGUN_JEJU_EXILE_1787": ["E019", "E020", "E021", "E022", "E023", "E024", "E025"],
    "R8A_FORMER_BUSA_KIM_CASE_1793": ["E026", "E027", "E029", "E030", "E034", "E037", "E038",
                                      "E050", "E051", "E055", "E056", "E059", "E060", "E061",
                                      "E063", "E066", "E084", "E085", "E086"],
    "R8B_SINJIDO_TO_BAENGNYEONG_1794": ["E076"],
    "R8C_JANGYEON_RELEASE_1795_1798": ["E079", "E080", "E081", "E082", "E083"],
}
KIN_CONTEXT_ROWS = ["I002", "I003"]  # 구세덕 경력 행 (구순은 object로만 등장)


# ───────────────────────── 시간 유틸 ─────────────────────────
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
QUAL_RE = re.compile(r"^(\d{4})-(\d{2})-(early|late)$")


def is_day(s) -> bool:
    return isinstance(s, str) and bool(DATE_RE.match(s))


def lord(s: str) -> int:
    """명목 음력 서수 (1년=360일). 정렬/시각화 전용. UNKNOWN에는 쓰지 않는다."""
    m = DATE_RE.match(s)
    if not m:
        raise ValueError(f"lord() requires a full lunar date, got {s!r}")
    y, mo, d = map(int, m.groups())
    return y * 360 + (mo - 1) * 30 + (d - 1)


def lx(s) -> float | None:
    """명목 음력 소수 연도 — DERIVED_FOR_VISUALIZATION. 불명이면 None."""
    if not is_day(s):
        return None
    return lord(s) / 360.0


def month_bounds(ym: str) -> tuple[str, str]:
    # 음력 한 달은 29 또는 30일; 실제 길이는 역법표 없이 알 수 없으므로 상한을 30일로 둔다.
    return f"{ym}-01", f"{ym}-30"


def normalize_time(row) -> dict:
    raw, raw_end, tp = row["date_lunar"], row["date_end_lunar"], row["time_precision"]
    out = dict(record_date_raw=raw, date_qualifier=NA, csv_time_precision=tp,
               precision_flag="OK")
    if tp == "day" and is_day(raw):
        out.update(event_start=raw, event_end=raw, earliest_possible=raw, latest_possible=raw,
                   time_precision="EXACT_DAY")
    elif MONTH_RE.match(raw) or QUAL_RE.match(raw):
        ym = raw[:7]
        lo, hi = month_bounds(ym)
        q = QUAL_RE.match(raw)
        out.update(event_start=ym, event_end=ym, earliest_possible=lo, latest_possible=hi,
                   time_precision="YEAR_MONTH", date_qualifier=q.group(3) if q else NA)
        if tp != "month":
            out["precision_flag"] = f"CSV_SAYS_{tp.upper()}_BUT_VALUE_IS_MONTH_LEVEL"
    elif tp == "interval":
        out.update(event_start=raw, event_end=raw_end, earliest_possible=raw,
                   latest_possible=raw_end, time_precision="RANGE")
    elif tp == "open_interval":
        out.update(event_start=raw, event_end=OPEN, earliest_possible=raw,
                   latest_possible=UNKNOWN, time_precision="OPEN_INTERVAL")
    else:
        out.update(event_start=UNKNOWN, event_end=UNKNOWN, earliest_possible=UNKNOWN,
                   latest_possible=UNKNOWN, time_precision="UNKNOWN",
                   precision_flag="UNPARSEABLE_DATE")
    return out


# ───────────────────────── 1. 입력 탐색 ─────────────────────────
def find_input() -> Path:
    exact = [p for p in ROOT.rglob("gusun_temporal_network_master_v0_2.csv")
             if OUT not in p.parents]
    if exact:
        return sorted(exact, key=lambda p: p.stat().st_mtime)[-1]
    cands = [p for p in ROOT.rglob("*.csv") if OUT not in p.parents
             and all(k in p.name.lower() for k in ("gusun", "temporal", "network"))]
    if not cands:
        raise FileNotFoundError("gusun temporal network CSV not found")
    return sorted(cands, key=lambda p: p.stat().st_mtime)[-1]


def load_raw(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False,
                     na_values=[""])
    df["csv_row_number"] = range(2, len(df) + 2)  # 헤더=1행
    return df


def write(df: pd.DataFrame, name: str, inter: bool = False):
    path = (INT if inter else OUT) / name
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def nz(v, default=NA):
    return default if v is None or (isinstance(v, float) and pd.isna(v)) or v == "" else v


# ───────────────────────── 2. 프로파일 & 품질 점검 ─────────────────────────
def profile(df: pd.DataFrame, path: Path) -> dict:
    ids = sorted(set(df.subject_id) | set(df.object_id))
    actor_ids = [i for i in ids if not i.startswith(NON_ACTOR_PREFIXES)]
    prof = {
        "input_file": str(path.relative_to(ROOT)),
        "n_rows": len(df), "n_columns": df.shape[1] - 1,
        "columns": [c for c in df.columns if c != "csv_row_number"],
        "year_range": [int(df.year.astype(int).min()), int(df.year.astype(int).max())],
        "date_lunar_range": [df.date_lunar.min(), df.date_lunar.max()],
        "calendar": "LUNAR (date_lunar)",
        "n_distinct_ids_subject_object": len(ids),
        "n_actor_ids": len(actor_ids),
        "n_person_like_P_ids": len([i for i in ids if i.startswith("P_")]),
        "time_precision_counts": df.time_precision.value_counts().to_dict(),
        "record_class_counts": df.record_class.value_counts().to_dict(),
        "phase_counts": df.phase.value_counts().to_dict(),
        "evidence_grade_counts": df.evidence_grade.value_counts().to_dict(),
        "claim_status_counts": df.claim_status.value_counts().to_dict(),
        "source_name_counts": df.source_name.fillna("NA").value_counts().to_dict(),
        "source_stage_counts": df.source_stage.value_counts().to_dict(),
        "missingness_flag_counts": df.missingness_flag.value_counts().to_dict(),
        "n_relation_types_raw": df.relation_type.nunique(),
        "uncertainty_fields": ["time_precision", "date_end_lunar", "claim_status",
                               "evidence_grade", "identity_confidence_gu", "missingness_flag",
                               "superseded_by_event_id", "identity_bridge_status"],
    }
    return prof


def quality_checks(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def add(check, event_id, finding, severity, action):
        rows.append(dict(check=check, event_id=event_id, finding=finding, severity=severity,
                         action=action))

    for _, r in df.iterrows():
        t = normalize_time(r)
        if t["precision_flag"] != "OK":
            add("time_precision_consistency", r.event_id,
                f"date_lunar={r.date_lunar!r}, time_precision={r.time_precision!r}", "MEDIUM",
                "YEAR_MONTH로 재분류; 임의의 일(day)을 부여하지 않음")
    # 번호 결락
    for prefix in ("E", "I", "C"):
        nums = sorted(int(e[1:]) for e in df.event_id if e.startswith(prefix))
        missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
        if missing:
            add("event_id_sequence_gaps", ",".join(f"{prefix}{m:03d}" for m in missing),
                f"{prefix} 계열 id 결락: {len(missing)}개", "INFO",
                "결락 행의 내용은 알 수 없음 — 생성하지 않음")
    # 메타필드가 언급하지만 행이 없는 근거
    add("referenced_but_absent_evidence", "I002;E001",
        "identity_link_basis가 '1782 royal dialogue'로 부자관계(구세덕-구순)를 근거한다고 하나 "
        "해당 1782 행이 CSV에 없음", "HIGH",
        "KINSHIP edge는 CSV 역할필드(father_of_candidate_gu)에 근거해 유지하되 confidence를 낮추고 플래그")
    add("referenced_but_absent_evidence", "E029;E079",
        "identity_link_basis가 '1795 長淵 transfer'를 언급하나 해당 이배 행이 없음 (E078 결락)",
        "HIGH", "백령도→장연현 연결을 HIGH_CONFIDENCE(미확정)로 둠; E079 시작일 1795-10-15는 "
                "CSV 단언값으로만 보존")
    add("referenced_but_absent_evidence", "I004",
        "백령첨사 임명 행 자체는 없음; 1781-12 국왕 발언(I004)만 존재", "MEDIUM",
        "백령첨사 재임 시작은 ≤1781-12로만 표현")
    add("temporal_tension", "E003;E004",
        "1778-12-24 중화부사 임명(E003) 후 1779-08-10 별군직으로 왕 행행 수행(E004); "
        "중화부사 체직 기록 없음", "MEDIUM",
        "모순으로 처리하지 않음; identity_evidence에 TENSION으로 기록")
    add("temporal_tension", "E025;E026;E027",
        "E025 gap의 종료값(1793-02-21)이 '1793-02-early' 기록(E026/E027)의 가능 구간과 겹침",
        "LOW", "해배 상한은 날짜가 확정된 최초 자유 신분 관측 E028(1793-02-22)로 둠")
    add("legacy_level_field", "ALL",
        "subject/object_level_current(0–5)는 품계가 아니라 CSV 작성자의 서열 코드이며, "
        "구순의 경우 현직=3, 죄인·전직=1로 관직과 처벌 상태를 섞음", "HIGH",
        "csv_legacy_level로만 보존, rank_level 계산에 사용하지 않음")
    add("official_rank_absent", "ALL", "CSV에 품계(정3품 등) 필드가 없음; E002만 '당상관'(일기 전언)",
        "HIGH", "official_rank·rank_level은 NA (E002 행의 '당상관(일기 전언)'만 원문 보존)")
    add("relation_type_cardinality", "ALL",
        f"원문 relation_type {df.relation_type.nunique()}종 (사건 서술형 동사)", "INFO",
        "17종 vocabulary로 정규화하고 원문은 relation_subtype으로 보존")
    add("record_vs_event_date", "E060–E069",
        "1793-06-13 최종 안핵 행들은 '기록·판정 일자'이며 서술된 행위(편들기·편파수사 등)의 발생일이 아님",
        "MEDIUM", "edge에 record_date와 관계 발생 구간(earliest/latest)을 분리")
    no_url = df[df.source_url.isna()]
    for _, r in no_url.iterrows():
        add("missing_source_url", r.event_id, f"phase={r.phase}; source_stage={r.source_stage}",
            "INFO", "연구 공백(STATE_GAP) 행 — 사료 행이 아님")
    return pd.DataFrame(rows)


def source_provenance(df: pd.DataFrame) -> pd.DataFrame:
    """URL 문자열만 파싱한다. 접속하지 않는다."""
    rows = []
    for _, r in df.iterrows():
        url = nz(r.source_url)
        dom = re.sub(r"^https?://([^/]+)/.*$", r"\1", url) if url != NA else NA
        rows.append(dict(event_id=r.event_id, source_name=nz(r.source_name),
                         source_url=url, url_domain=dom,
                         secondary_source_url=nz(r.secondary_source_url),
                         source_stage=r.source_stage, accessed="NO (metadata only)"))
    return pd.DataFrame(rows)


# ───────────────────────── 3. 인물 정규화 ─────────────────────────
def actor_pid(raw_id: str, row) -> str | None:
    if raw_id == "P_GUSUN":
        return SEGMENT_MAP[row["gu_identity_segment"]]
    if raw_id.startswith(NON_ACTOR_PREFIXES):
        return None
    return raw_id


def gusun_side(row) -> str | None:
    if row["subject_id"] == "P_GUSUN":
        return "subject"
    if row["object_id"] == "P_GUSUN":
        return "object"
    return None


# 정규식으로 친족어만 잡는다 ('처분' 같은 일반어의 '처'를 오인하지 않도록)
KIN_SEX_TERMS = [(r"의 처$", "F"), (r"남편", "M"), (r"종형", "M"), (r"^아들", "M"), (r"^father_of", "M")]


def build_persons(df: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    recs = {}
    for _, r in df.iterrows():
        for side in ("subject", "object"):
            pid = actor_pid(r[f"{side}_id"], r)
            if pid is None:
                continue
            d = recs.setdefault(pid, dict(names=set(), hanja=set(), statuses=[], dates=set(),
                                          years=set(), phases=set(), rows=[], roles=set(),
                                          raw=r[f"{side}_id"]))
            d["names"].add(r[f"{side}_name_ko"])
            if pd.notna(r[f"{side}_name_hanja"]):
                d["hanja"].add(r[f"{side}_name_hanja"])
            st = r[f"{side}_office_status"]
            if pd.notna(st):
                d["statuses"].append((r.date_lunar, st, r.event_id))
            if r.phase not in ("gap", "macro_context"):
                d["dates"].add(r.date_lunar)
                d["years"].add(r.year)
            d["phases"].add(r.phase)
            d["rows"].append(r.event_id)
            if pd.notna(r[f"{side}_role_relative_to_gu"]):
                d["roles"].add(r[f"{side}_role_relative_to_gu"])

    in_net = set(edges.source_person) | set(edges.target_person)
    alias_notes = {
        "P_KIM_MYEONGSIN": "CSV 내 별칭: '풍각 김생원'(E035), '풍각 김상제'(E038) — CSV가 괄호로 김명신과 동일시",
        "P_KIM_GAPDEUK": "CSV 내 별칭: '흥덕 김생원'(E036)",
        "P_LEE_GWANGSEOP": "CSV 서술의 '병사'(E035, E037)를 이광섭으로 대응시킨 것은 CSV 작성자의 매핑",
    }
    aliases = {"P_KIM_MYEONGSIN": "풍각 김생원; 풍각 김상제", "P_KIM_GAPDEUK": "흥덕 김생원"}
    out = []
    for pid, d in sorted(recs.items()):
        statuses = d["statuses"]
        status_str = " | ".join(f"{dt}:{st}({eid})" for dt, st, eid in statuses)
        sex, sex_basis = UNKNOWN, "CSV 친족 용어 없음"
        for term, sx in KIN_SEX_TERMS:
            hit = [s for _, s, _ in statuses if re.search(term, s)] + \
                  [ro for ro in d["roles"] if re.search(term, ro)]
            if hit:
                sex, sex_basis = sx, f"DERIVED: 친족 용어 '{term}' in '{hit[0]}'"
                break
        death_year, death_basis = NA, NA
        if pid == "P_KIM_MYEONGSIN":
            death_year, death_basis = "1793", "OBSERVED: E056 '옥사시켰다', E062 '김명신의 죽음' (일자 미상 → time_uncertainty U_DEATH_KIM)"
        n_dates, years = len(d["dates"]), sorted(d["years"])
        n_years = len(years)
        n_labels = len({s for _, s, _ in statuses})
        multi_phase = len(d["phases"] - {"gap", "macro_context"}) > 1
        # biographical_coverage_score: 사료 관측 밀도(중요도 아님)
        if n_dates >= 10 and n_years >= 5:
            score = 5
        elif n_years >= 3:
            score = 4
        elif n_labels >= 2 and (n_dates >= 2) and multi_phase:
            score = 3
        elif n_labels >= 1 and any(len(s) > 1 for _, s, _ in statuses):
            score = 2
        elif d["rows"]:
            score = 1
        else:
            score = 0
        kind = "PERSON"
        if pid.startswith("GUSUN_"):
            kind = "PERSON_IDENTITY_SEGMENT"
        elif pid in NODE_KIND:
            kind = NODE_KIND[pid]
        ident = NA
        if pid == "GUSUN_PRE1793":
            ident = "SEGMENT of P_GUSUN; links to GUSUN_1793PLUS = HIGH_CONFIDENCE (see identity_links)"
        elif pid == "GUSUN_1793PLUS":
            ident = "SEGMENT of P_GUSUN; links to GUSUN_PRE1793 = HIGH_CONFIDENCE (see identity_links)"
        elif kind == "PERSON":
            ident = "SINGLE_CSV_ID (동명이인 검토 대상 기록 없음)"
        out.append(dict(
            person_id=pid, csv_original_id=d["raw"],
            name_ko=";".join(sorted(d["names"])), name_hanja=";".join(sorted(d["hanja"])) or NA,
            aliases=aliases.get(pid, NA), node_kind=kind, sex=sex, sex_basis=sex_basis,
            birth_year=NA, death_year=death_year, death_basis=death_basis,
            known_status=status_str or NA,
            roles_relative_to_gu=";".join(sorted(d["roles"])) or NA,
            first_seen=min(d["dates"]) if d["dates"] else NA,
            last_seen=max(d["dates"]) if d["dates"] else NA,
            years_observed=";".join(years) or NA, n_csv_rows=len(d["rows"]),
            n_distinct_dates=n_dates, identity_confidence=ident,
            biographical_coverage_score=score, in_network=pid in in_net,
            evidence_status="OBSERVED (name/status) + DERIVED (score, sex, kind)",
            notes=alias_notes.get(pid, NA),
        ))
    return pd.DataFrame(out)


# ───────────────────────── 4. 사건 정규화 ─────────────────────────
def scope_for_label(label: str) -> str:
    if label in (NA, None) or (isinstance(label, float)):
        return UNKNOWN
    for kw, sc in SCOPE_KEYWORDS:
        if kw in label:
            return sc
    return UNKNOWN


def build_events(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        t = normalize_time(r)
        rel_norm, etype = (None, "CONTEXT_POLICY") if r.phase == "macro_context" \
            else RELATION_MAP[r.relation_type]
        side = gusun_side(r)
        if side:
            pid = SEGMENT_MAP[r.gu_identity_segment]
            label = r[f"{side}_office_status"]
        else:
            pid = actor_pid(r.subject_id, r) or r.subject_id
            label = r.subject_office_status
        official_rank, rank_level = NA, NA
        if r.event_id == "E002":
            official_rank = "당상관 (노상추일기 전언; 공식 임명문 아님)"
        if side and r.event_id not in KIN_CONTEXT_ROWS:
            office, tenure, state = GUSUN_STATUS[label]
            before, after = GUSUN_STATE_OVERRIDE.get(r.event_id, (state, state))
            if office in OFFICE_RULES:
                scope, prox, cmd, basis = OFFICE_RULES[office]
            else:
                scope, prox, cmd, basis = ("NONE" if tenure == "NONE" else UNKNOWN,
                                           "NONE" if tenure == "NONE" else UNKNOWN,
                                           "NONE" if tenure == "NONE" else UNKNOWN,
                                           "현직 없음(정배·수감 등은 관직 level이 아닌 career_state)")
            office_ev = "DERIVED (CSV 신분 라벨 분해)"
        elif side and r.event_id in KIN_CONTEXT_ROWS:
            office, tenure, before, after = NA, UNKNOWN, UNKNOWN, UNKNOWN
            scope, prox, cmd, basis = UNKNOWN, UNKNOWN, UNKNOWN, "구세덕 경력 행 — 구순 상태 정보 아님"
            office_ev = "NA"
        else:
            office, tenure, before, after = label if pd.notna(label) else NA, UNKNOWN, UNKNOWN, UNKNOWN
            scope, prox, cmd, basis = scope_for_label(office), UNKNOWN, UNKNOWN, \
                "관직명 키워드 규칙(비-구순 인물)"
            office_ev = "OBSERVED label / DERIVED scope"
        cluster = next((c for c, ids in GUSUN_RECORD_CLUSTERS.items() if r.event_id in ids), NA)
        rows.append(dict(
            event_id=r.event_id, csv_row_number=r.csv_row_number, event_order_csv=r.event_order,
            person_id=pid, gusun_record_cluster=cluster,
            subject_id=actor_pid(r.subject_id, r) or r.subject_id,
            object_id=actor_pid(r.object_id, r) or r.object_id,
            event_type=etype, relation_type_raw=r.relation_type,
            relation_type_norm=rel_norm if rel_norm != "__ARREST__" else arrest_kind(r),
            phase=r.phase, record_class=r.record_class,
            calendar="LUNAR", record_date_raw=t["record_date_raw"],
            event_start=t["event_start"], event_end=t["event_end"],
            earliest_possible=t["earliest_possible"], latest_possible=t["latest_possible"],
            time_precision=t["time_precision"], date_qualifier=t["date_qualifier"],
            csv_time_precision=t["csv_time_precision"], precision_flag=t["precision_flag"],
            plot_x_start=lx(t["earliest_possible"]), plot_x_end=lx(t["latest_possible"]),
            plot_x_status="DERIVED_FOR_VISUALIZATION (명목 음력 소수연도; 실제 날짜 아님)",
            office_name=office, office_tenure=tenure, official_rank=official_rank,
            rank_level=rank_level, rank_level_note="CSV에 품계 없음 → 계산하지 않음",
            administrative_scope=scope, court_proximity=prox, command_scope=cmd,
            office_dimension_basis=basis, office_evidence_status=office_ev,
            career_state=before, career_state_after=after,
            csv_legacy_level_subject=r.subject_level_current,
            csv_legacy_level_object=nz(r.object_level_current),
            location=r.location, event_description=r.event_summary,
            outcome_or_state=r.outcome_or_state, claim_status=r.claim_status,
            evidence_grade=r.evidence_grade, source_stage=r.source_stage,
            source_title=nz(r.source_name), source_url=nz(r.source_url),
            secondary_source_url=nz(r.secondary_source_url),
            source_support_note=nz(r.source_support_note),
            superseded_by_event_id=nz(r.superseded_by_event_id),
            missingness_flag=r.missingness_flag, modeling_note=nz(r.modeling_note),
            gu_identity_segment=nz(r.gu_identity_segment),
            identity_bridge_status_csv=nz(r.identity_bridge_status),
            evidence_status="OBSERVED" if r.missingness_flag == "observed" else "OBSERVED_GAP",
        ))
    return pd.DataFrame(rows)


def arrest_kind(r) -> str:
    # ORDERS_ARREST: 실무 장교에게 내린 지시면 COMMAND, 체포 대상이 피의자면 DETENTION
    return "COMMAND" if r.object_role_relative_to_gu == "operational_actor" else "DETENTION"


# ───────────────────────── 5. temporal edges ─────────────────────────
# 관계 발생 시간 보정 (CSV 기록일 ≠ 관계 발생일인 경우). 모든 값은 CSV 내 날짜에서 가져온다.
CASE_START = "1793-02-22"   # E028: 도난 보고 (사건 개시, EXACT)
CASE_PROV_END = "1793-05-12"  # E050/E054: 관찰사 장계·병사 파직 청 (병영 단계 종료)
RELATION_TIME_RULES = {
    # event_id: dict(start, end, earliest_start, latest_start, earliest_end, latest_end, precision, basis)
    "E019": dict(start=UNKNOWN, end=OPEN, earliest_start=UNKNOWN, latest_start="1787-01-03",
                 earliest_end="1787-01-03", latest_end=UNKNOWN, precision="BEFORE",
                 basis="'기존의 틈(有隙)' — 1787-01-03 판결 이전부터 존재, 종료 기록 없음"),
    "E020": dict(start=UNKNOWN, end=UNKNOWN, earliest_start=UNKNOWN, latest_start="1787-01-03",
                 earliest_end=UNKNOWN, latest_end="1787-01-03", precision="BEFORE",
                 basis="무고 행위는 1787-01-03 판결 이전 (판결일=기록일)"),
    "E021": dict(start=UNKNOWN, end=UNKNOWN, earliest_start=UNKNOWN, latest_start="1787-01-03",
                 earliest_end=UNKNOWN, latest_end="1787-01-03", precision="BEFORE",
                 basis="연루 행위는 1787-01-03 판결 이전"),
    "E022": dict(start=UNKNOWN, end=UNKNOWN, earliest_start=UNKNOWN, latest_start="1787-01-03",
                 earliest_end=UNKNOWN, latest_end="1787-01-03", precision="BEFORE",
                 basis="종용 행위는 1787-01-03 판결 이전"),
    "E026": dict(start=UNKNOWN, end="1793-02", earliest_start=UNKNOWN, latest_start="1793-02-30",
                 earliest_end="1793-02-01", latest_end="1793-02-30", precision="OPEN_INTERVAL",
                 basis="'본래 친숙' — 시작 미상, E027 단절(1793-02 '상순' 표기)로 종료"),
    "E027": dict(start="1793-02", end=OPEN, earliest_start="1793-02-01", latest_start="1793-02-30",
                 earliest_end="1793-02-01", latest_end=UNKNOWN, precision="OPEN_INTERVAL",
                 basis="단절 시점은 월 단위('early' 한정어 보존); 화해 기록 없음 → end OPEN"),
    "E063": dict(start=UNKNOWN, end=UNKNOWN, earliest_start=CASE_START, latest_start=CASE_PROV_END,
                 earliest_end=CASE_START, latest_end=CASE_PROV_END, precision="RANGE",
                 basis="1793-06-13은 국왕 판정 기록일; 편들기는 병영 수사 단계(E028~E054) 중"),
    "E064": dict(start=UNKNOWN, end=UNKNOWN, earliest_start=CASE_START, latest_start=CASE_PROV_END,
                 earliest_end=CASE_START, latest_end=CASE_PROV_END, precision="RANGE",
                 basis="06-13 판정 기록; 편파 수사는 병영 단계 중"),
    "E065": dict(start=UNKNOWN, end=UNKNOWN, earliest_start=CASE_START, latest_start=CASE_PROV_END,
                 earliest_end=CASE_START, latest_end=CASE_PROV_END, precision="RANGE",
                 basis="06-13 판정 기록; 오착·단련은 병영 단계 중"),
    "E084": dict(start=UNKNOWN, end=UNKNOWN, earliest_start=CASE_START, latest_start=CASE_PROV_END,
                 earliest_end=CASE_START, latest_end=CASE_PROV_END, precision="RANGE",
                 basis="05-12 장계 기록; '도적 괴수' 지목은 도난(02-22) 이후"),
    "E085": dict(start=UNKNOWN, end=UNKNOWN, earliest_start=CASE_START, latest_start=CASE_PROV_END,
                 earliest_end=CASE_START, latest_end=CASE_PROV_END, precision="RANGE",
                 basis="05-12 장계 기록(주장); 행위 시점은 도난 이후"),
    "E086": dict(start=UNKNOWN, end=UNKNOWN, earliest_start=CASE_START, latest_start=CASE_PROV_END,
                 earliest_end=CASE_START, latest_end=CASE_PROV_END, precision="RANGE",
                 basis="05-12 장계 기록(주장); 행위 시점은 도난 이후"),
}

# CSV 행의 역할·신분 라벨·요약문에서 '직접' 읽히는 추가 관계 (DERIVED). check_names는 검증용.
DERIVED_EDGES = [
    dict(id="D01", src="P_GU_SEDEOK", tgt="GUSUN_PRE1793", rel="KINSHIP", sub="FATHER_OF (CSV role)",
         ev="I002;I003", check=["구세덕", "구순"], conf="B_REDUCED",
         note="역할필드 father_of_candidate_gu / '아들(후대 관계자료와 결합)'. 근거로 언급된 1782 행은 CSV에 없음",
         period_event="I003", time=dict(precision="UNKNOWN")),
    dict(id="D02", src="GUSUN_PRE1793", tgt="P_RYU_HYOWON", rel="KINSHIP", sub="COUSIN '종형' (CSV label)",
         ev="E021", check=["유효원", "종형"], conf="A",
         note="object_office_status='구순의 종형'. 성씨가 달라 친족 경로(부계/외가/인척)는 UNRESOLVED",
         period_event="E021", time=dict(precision="UNKNOWN", observed="1787-01-03")),
    dict(id="D03", src="P_SHIN_U_MUN", tgt="GUSUN_PRE1793", rel="OFFICIAL_SUPERIOR",
         sub="上官 (CSV support note)", ev="E009", check=["신우문", "上官"], conf="A",
         note="role=institutional_superior; '具純之爲下官而凌侮上官者'", period_event="E009",
         time=dict(precision="EXACT_DAY", observed="1784-03-17")),
    dict(id="D04", src="GUSUN_PRE1793", tgt="P_LEE_YUNBIN", rel="OFFICIAL_COLLEAGUE",
         sub="both 별군직 at record", ev="E019", check=["이윤빈", "별군직"], conf="A",
         note="E019 subject/object_office_status 모두 '별군직'", period_event="E019",
         time=dict(precision="EXACT_DAY", observed="1787-01-03")),
    dict(id="D05", src="P_JO_HAKSIN", tgt="GUSUN_PRE1793", rel="TESTIMONY",
         sub="testified to 구순's urging", ev="E022", check=["조학신", "진술"], conf="A",
         note="'조학신이 장전 친문에서 구순의 종용을 받았다고 진술'", period_event="E022",
         time=dict(precision="BEFORE", latest="1787-01-03")),
    dict(id="D06", src="P_NABOK", tgt="GUSUN_1793PLUS", rel="HOUSEHOLD", sub="구순 집 종",
         ev="E028", check=["나복", "구순 집 종"], conf="A", note="subject_office_status='구순 집 종'",
         period_event="E028", time=dict(precision="UNKNOWN", observed="1793-02-22")),
    dict(id="D07", src="P_MYEONGEOP", tgt="GUSUN_1793PLUS", rel="HOUSEHOLD",
         sub="구순 여종의 남편 (indirect)", ev="E028", check=["명업", "구순 여종의 남편"], conf="B",
         note="object_office_status='사노·구순 여종의 남편' — 간접 가내 연결", period_event="E028",
         time=dict(precision="UNKNOWN", observed="1793-02-22")),
    dict(id="D08", src="P_KIM_MYEONGSIN", tgt="GUSUN_1793PLUS", rel="NEIGHBOR", sub="구순 이웃",
         ev="E026", check=["김명신", "이웃"], conf="A", note="subject_office_status='반족·구순 이웃'",
         period_event="E026", time=dict(precision="UNKNOWN", observed="1793-02")),
    dict(id="D09", src="N_HOUSE_SERVANTS", tgt="GUSUN_1793PLUS", rel="HOUSEHOLD", sub="구순 집 하인",
         ev="E085", check=["행랑 하인들", "구순 집 하인"], conf="B",
         note="object_office_status='구순 집 하인 집단'", period_event="E085",
         time=dict(precision="UNKNOWN", observed="1793-05-12")),
    dict(id="D10", src="P_HAN_JAEUK", tgt="P_JO_GYEWAN", rel="COMMAND", sub="ORDERS_ARREST (summary)",
         ev="E031", check=["한재욱", "조계완"], conf="A",
         note="E031 요약 '한재욱이 이진욱·조계완 등에게 … 잡으라고 지시'", period_event="E031",
         time=dict(precision="EXACT_DAY", observed="1793-02-28")),
    dict(id="D11", src="P_HAN_JAEUK", tgt="P_BYEON_JIDEUL", rel="DETENTION", sub="arrest order target",
         ev="E031", check=["변지돌"], conf="A", note="E031 요약의 체포 대상", period_event="E031",
         time=dict(precision="EXACT_DAY", observed="1793-02-28")),
    dict(id="D12", src="P_HAN_JAEUK", tgt="P_JEONG_WONDOL", rel="DETENTION", sub="arrest order target",
         ev="E031", check=["정원돌"], conf="A", note="E031 요약의 체포 대상", period_event="E031",
         time=dict(precision="EXACT_DAY", observed="1793-02-28")),
    dict(id="D13", src="GUSUN_1793PLUS", tgt="P_KIM_MYEONGSIN", rel="ACCUSATION",
         sub="names as 'very suspicious' to 유제희", ev="E038", check=["김명신", "수상"], conf="A",
         note="E038 요약 '구순이 풍각 김상제(김명신)도 매우 수상하다고 말했다'", period_event="E038",
         time=dict(precision="YEAR_MONTH", observed="1793-03")),
    dict(id="D14", src="P_YU_JEHUI", tgt="P_KIM_MYEONGSIN", rel="INVESTIGATION",
         sub="ENTERS_SUSPECT_LIST (summary)", ev="E039", check=["김명신", "유제희"], conf="A",
         note="E039 요약의 혐의자 명단에 김명신 포함 (E070–E075에는 김명신 행이 없음)",
         period_event="E039", time=dict(precision="YEAR_MONTH", observed="1793-03")),
    dict(id="D15", src="GUSUN_1793PLUS", tgt="P_LEE_GWANGSEOP", rel="OTHER",
         sub="letter to 병사 via 조계완 (content unknown)", ev="E037", check=["병사", "편지"], conf="B",
         note="'병사에게 전할 편지' — 병사=이광섭 대응은 CSV 매핑(E035). 편지 내용 미상",
         period_event="E037", time=dict(precision="EXACT_DAY", observed="1793-03-04")),
    dict(id="D16", src="P_LEE_GWANGSEOP", tgt="P_LEE_MUNHYEOP", rel="COMMAND",
         sub="영장이 병사의 명령을 따름", ev="E052", check=["이문협", "병사의 명령"], conf="A",
         note="E052 요약 '병사의 명령만 따르며 방관'", period_event="E052",
         time=dict(precision="RANGE", earliest=CASE_START, latest=CASE_PROV_END)),
    dict(id="D17", src="P_LEE_GWANGSEOP", tgt="GUSUN_1793PLUS", rel="CONFLICT",
         sub="家門 世嫌 (prior, family-level)", ev="E063", check=["세혐", "구순"], conf="B",
         note="'구순과의 세혐을 막 씻은 뒤' — 가문 단위 갈등, 개인 간 갈등인지 UNRESOLVED; 시작 미상",
         period_event="E063",
         time=dict(precision="OPEN_INTERVAL", end_latest=CASE_PROV_END)),
    dict(id="D18", src="GUSUN_1793PLUS", tgt="P_HAN_JAEUK", rel="HOUSEHOLD",
         sub="CLAIMED 가객 link (contested)", ev="E057", check=["가객", "한재욱"], conf="B_CONTESTED",
         note="이조원 보고의 주장. E061에서 한재욱은 구순을 평생 몰랐다고 진술; 최종판정은 확정하지 않음 "
              "(superseded_by=E061)", period_event="E057",
         time=dict(precision="UNKNOWN", observed="1793-05-27")),
]


def edge_time_from_event(ev: pd.Series) -> dict:
    e = ev["earliest_possible"]
    l_ = ev["latest_possible"]
    if ev["time_precision"] == "EXACT_DAY":
        return dict(start_date=e, end_date=e, earliest_start=e, latest_start=e, earliest_end=e,
                    latest_end=e, time_precision="EXACT_DAY",
                    date_basis="CSV_DATE_AS_GIVEN (관계=사건 시점에 관측)")
    if ev["time_precision"] == "YEAR_MONTH":
        return dict(start_date=ev["event_start"], end_date=ev["event_end"], earliest_start=e,
                    latest_start=l_, earliest_end=e, latest_end=l_, time_precision="YEAR_MONTH",
                    date_basis="CSV 월 단위 날짜 → 월 경계 구간")
    return dict(start_date=ev["event_start"], end_date=ev["event_end"], earliest_start=e,
                latest_start=l_, earliest_end=e, latest_end=l_, time_precision=ev["time_precision"],
                date_basis="CSV 구간값")


def build_edges(df: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    ev_by_id = events.set_index("event_id")
    raw_by_id = df.set_index("event_id")
    rows = []
    for _, ev in events.iterrows():
        rel = ev["relation_type_norm"]
        if rel is None or pd.isna(rel) or ev["phase"] == "macro_context":
            continue
        r = raw_by_id.loc[ev["event_id"]]
        s, t = actor_pid(r.subject_id, r), actor_pid(r.object_id, r)
        if s is None or t is None:
            continue
        tm = edge_time_from_event(ev)
        if ev["event_id"] in RELATION_TIME_RULES:
            rule = RELATION_TIME_RULES[ev["event_id"]]
            tm = dict(start_date=rule["start"], end_date=rule["end"],
                      earliest_start=rule["earliest_start"], latest_start=rule["latest_start"],
                      earliest_end=rule["earliest_end"], latest_end=rule["latest_end"],
                      time_precision=rule["precision"],
                      date_basis="RELATION_WINDOW_DERIVED: " + rule["basis"])
        status = "OBSERVED"
        conf = r.evidence_grade
        if pd.notna(r.superseded_by_event_id):
            conf = f"{conf}_SUPERSEDED_BY_{r.superseded_by_event_id}"
        rows.append(dict(
            edge_id=f"X_{ev['event_id']}", source_person=s, target_person=t,
            relation_type=rel, relation_group=RELATION_GROUP[rel],
            relation_subtype=r.relation_type, record_date=ev["record_date_raw"],
            **tm, directed=rel not in SYMMETRIC, confidence=conf,
            confidence_note=r.claim_status, source_event_id=ev["event_id"],
            period_event_id=ev["event_id"], phase=r.phase,
            evidence_summary=r.event_summary, source_title=nz(r.source_name),
            source_url=nz(r.source_url), source_family=source_family(nz(r.source_url)),
            evidence_status="OBSERVED" if ev["event_id"] not in RELATION_TIME_RULES
            else "OBSERVED (relation) + DERIVED (time window)",
            derivation_note=NA,
        ))
    for d in DERIVED_EDGES:
        base = ev_by_id.loc[d["ev"].split(";")[0]]
        r = raw_by_id.loc[d["ev"].split(";")[0]]
        tt = d["time"]
        p = tt["precision"]
        if p == "EXACT_DAY":
            o = tt["observed"]
            tm = dict(start_date=o, end_date=o, earliest_start=o, latest_start=o, earliest_end=o,
                      latest_end=o)
        elif p == "YEAR_MONTH":
            lo, hi = month_bounds(tt["observed"])
            tm = dict(start_date=tt["observed"], end_date=tt["observed"], earliest_start=lo,
                      latest_start=hi, earliest_end=lo, latest_end=hi)
        elif p == "RANGE":
            tm = dict(start_date=UNKNOWN, end_date=UNKNOWN, earliest_start=tt["earliest"],
                      latest_start=tt["latest"], earliest_end=tt["earliest"],
                      latest_end=tt["latest"])
        elif p == "BEFORE":
            tm = dict(start_date=UNKNOWN, end_date=UNKNOWN, earliest_start=UNKNOWN,
                      latest_start=tt["latest"], earliest_end=UNKNOWN, latest_end=tt["latest"])
        elif p == "OPEN_INTERVAL":
            tm = dict(start_date=UNKNOWN, end_date=UNKNOWN, earliest_start=UNKNOWN,
                      latest_start=tt["end_latest"], earliest_end=UNKNOWN,
                      latest_end=tt["end_latest"])
        else:  # UNKNOWN: 지속적 관계(친족·가내·이웃) — 시작·종료 모두 미상
            tm = dict(start_date=UNKNOWN, end_date=UNKNOWN, earliest_start=UNKNOWN,
                      latest_start=UNKNOWN, earliest_end=UNKNOWN, latest_end=UNKNOWN)
        rec = tt.get("observed", base["record_date_raw"])
        rows.append(dict(
            edge_id=f"X_{d['id']}", source_person=d["src"], target_person=d["tgt"],
            relation_type=d["rel"], relation_group=RELATION_GROUP[d["rel"]],
            relation_subtype=d["sub"],
            record_date=rec if d["id"] != "D01" else UNKNOWN,
            **tm, time_precision=p,
            date_basis=("관측 시점=" + rec + " (관계의 시작·종료는 CSV에 없음)") if p == "UNKNOWN"
            else "RELATION_WINDOW_DERIVED from source row",
            directed=d["rel"] not in SYMMETRIC, confidence=d["conf"], confidence_note=d["note"],
            source_event_id=d["ev"], period_event_id=d["period_event"], phase=r.phase,
            evidence_summary=r.event_summary, source_title=nz(r.source_name),
            source_url=nz(r.source_url), source_family=source_family(nz(r.source_url)),
            evidence_status="DERIVED", derivation_note=f"rule {d['id']}; check_names={d['check']}",
        ))
    e = pd.DataFrame(rows)
    return e


def source_family(url: str) -> str:
    if url == NA:
        return NA
    if "sillok.history.go.kr" in url:
        return "NIKH_SILLOK"
    if "sjw.history.go.kr" in url:
        return "NIKH_SEUNGJEONGWON"
    if "db.history.go.kr" in url:
        return "NIKH_KOREAN_HISTORY_DB"
    return "OTHER"


# ───────────────────────── 6. 구순 경력 상태 구간 ─────────────────────────
def build_career_states(events: pd.DataFrame) -> pd.DataFrame:
    """각 state spell은 CSV event_id로부터 경계를 읽는다. 경계 미상은 UNKNOWN 그대로."""
    E = events.set_index("event_id")

    def d(eid):
        return E.loc[eid, "earliest_possible"]

    spells = [
        # (spell_id, segment, state, office, location, start, start_prec, end_lo, end_hi, ev_start, ev_end, note)
        ("S01", "GUSUN_PRE1793", "ACTIVE", "선전관→별군직", "한성", d("E001"), "EXACT_DAY",
         d("E002"), d("E003"), "E001", "E002;E003",
         "별군직 차하(E001); 선전관 표기(E002, 일기); 다음 관측은 중화부사 임명(E003)"),
        ("S02", "GUSUN_PRE1793", "ACTIVE", "중화부사", "중화부", d("E003"), "EXACT_DAY",
         d("E003"), d("E004"), "E003", "E004",
         "임명일만 관측. 체직 기록 없음; 1779-08-10 별군직 수행(E004) — 겸직/체직 여부 UNRESOLVED"),
        ("S03", "GUSUN_PRE1793", "ACTIVE", "별군직", "왕 행행 수행", d("E004"), "EXACT_DAY",
         d("E004"), d("E005"), "E004", "E005", "단일 관측점"),
        ("S04", "GUSUN_PRE1793", "ACTIVE", "벽동군수", "벽동군", d("E005"), "EXACT_DAY",
         d("E005"), "1781-12-30", "E005", "I004", "임명일만 관측; 다음 관측은 백령첨사(I004, 월 단위)"),
        ("S05", "GUSUN_PRE1793", "ACTIVE", "백령첨사", "백령", UNKNOWN, "BEFORE",
         "1781-12-01", d("E006"), "I004", "E006",
         "임명 행 없음; 1781-12 국왕 발언에서 재임 확인 → 시작 ≤1781-12"),
        ("S06", "GUSUN_PRE1793", "ACTIVE", "영흥부사", "영흥부", d("E006"), "EXACT_DAY",
         d("E009"), d("E011"), "E006", "E011", "1784-03-17 상관 갈등 → 03-18 나문 명령"),
        ("S07", "GUSUN_PRE1793", "UNDER_INVESTIGATION", "영흥부사(재임 중)", "영흥부", d("E011"),
         "EXACT_DAY", d("E016"), d("E016"), "E011", "E016",
         "나문 명령(E011)→나처 연기(E015)→분간·포상(E016). 재임 유지(career_state≠관직 level)"),
        ("S08", "GUSUN_PRE1793", "ACTIVE", "영흥부사", "영흥부", d("E016"), "EXACT_DAY",
         d("E016"), d("E017"), "E016", "E017", "포상 후; 별군직 복귀 시점 미상"),
        ("S09", "GUSUN_PRE1793", "EXILED", "NA (별군직에서 정배)", "배소 미상", d("E017"),
         "EXACT_DAY", d("E017"), "1787-01-03", "E017", "E018;E019",
         "정배 명령일만 관측. 해배 미관측(E018 gap) → 1787-01-03 이전에 종료"),
        ("S10", "GUSUN_PRE1793", "ACTIVE", "별군직", "한성", UNKNOWN, "BEFORE", d("E019"),
         d("E019"), "E019", "E023", "복귀 시점 미상 (≤1787-01-03)"),
        ("S11", "GUSUN_PRE1793", "EXILED", "NA", "제주목", d("E023"), "EXACT_DAY", d("E023"),
         "1793-02-22", "E023", "E028",
         "決棍三十度·濟州牧減死定配·勿揀赦典. 해배 미관측(E025). 종료 상한은 동일인 가정(HIGH_CONFIDENCE) 하에서만 의미"),
        ("S12", "GUSUN_1793PLUS", "FORMER_OFFICIAL", "전 부사(府名 미상)", "청주 덕평", UNKNOWN,
         "BEFORE", "1793-02-01", d("E050"), "E026", "E050",
         "'본래 친숙'(E026) — 덕평 거주 시작 미상. 1793-02 최초 관측"),
        ("S13", "GUSUN_1793PLUS", "UNDER_INVESTIGATION", "전 부사(府名 미상)", "청주 덕평/충청도",
         UNKNOWN, "BEFORE", d("E050"), d("E055"), "E050", "E055",
         "관찰사 공동조사(일자 미상) → 05-12 장계"),
        ("S14", "GUSUN_1793PLUS", "IMPRISONED", "전 부사(府名 미상)", "의금부(한성)", d("E055"),
         "EXACT_DAY", d("E066"), d("E066"), "E055;E056;E059", "E066",
         "05-12 수금 명령(실제 체포일 미상, ≤05-27 의금부 피수사자)"),
        ("S15", "GUSUN_1793PLUS", "EXILED", "NA", "신지도", d("E066"), "EXACT_DAY", d("E076"),
         d("E076"), "E066", "E076", "감사 절도정배"),
        ("S16", "GUSUN_1793PLUS", "EXILED", "NA", "백령도", d("E076"), "EXACT_DAY", d("E076"),
         d("E080"), "E076", "E079;E080",
         "장연현 이배 행 없음(E078 결락). CSV E079는 1795-10-15를 장연 정배 시점으로 단언"),
        ("S17", "GUSUN_1793PLUS", "EXILED", "NA", "장연현", UNKNOWN, "BEFORE", d("E082"), d("E082"),
         "E079", "E082", "시작 ≤1795-10-15(CSV 단언) / 확실한 상한 ≤1798-02-21; '도 3년'으로 재분류 경위 미상"),
        ("S18", "GUSUN_1793PLUS", "RELEASED", "NA", "장연현→미상", d("E082"), "EXACT_DAY",
         UNKNOWN, UNKNOWN, "E082", "E083", "방송 윤허. 이후 행적 OPEN (E083)"),
    ]
    rows = []
    for sp in spells:
        (sid, seg, state, office, loc, start, sprec, end_lo, end_hi, evs, eve, note) = sp
        rows.append(dict(spell_id=sid, person_id=seg, career_state=state, office_or_status=office,
                         location=loc, start=start, start_precision=sprec,
                         earliest_end=end_lo, latest_end=end_hi,
                         end_precision="EXACT_DAY" if end_lo == end_hi and is_day(end_lo)
                         else ("UNKNOWN" if end_lo == UNKNOWN else "RANGE"),
                         evidence_start=evs, evidence_end=eve, notes=note,
                         evidence_status="DERIVED (CSV event 경계에서 구성)",
                         is_office_level=False))
    return pd.DataFrame(rows)


# ───────────────────────── 7. 동일인 evidence ─────────────────────────
IDENTITY_LINKS = [
    # link_id, a, b, evidence items [(code, kind, events, description)]
    ("L01", "R2_JUNGHWA_BUSA_1778", "R4_BAENGNYEONG_CHEOMSA_1781", [
        ("SAME_HANJA_NAME", "SUPPORT", "E003;I004", "두 기록 모두 具純"),
        ("EXPLICIT_CROSS_REFERENCE", "SUPPORT", "I004",
         "국왕이 백령 파견 취지를 '중화의 비정을 씻게 하려는 것'이라 명시 (claim_status=explicit_identity_link, A)"),
    ]),
    ("L02", "R1_SEONJEON_BYEOLGUN_1777_1779", "R2_JUNGHWA_BUSA_1778", [
        ("SAME_HANJA_NAME", "SUPPORT", "E001;E003", "具純"),
        ("CHRONOLOGICAL_COMPATIBILITY", "SUPPORT", "E001;E003", "1777-09 별군직 → 1778-12 중화부사, 날짜 중첩 없음"),
        ("TEMPORAL_TENSION", "TENSION", "E003;E004",
         "중화부사 임명(1778-12-24) 후 1779-08-10 별군직 수행 — 체직 기록 없음 (모순은 아님)"),
    ]),
    ("L03", "R2_JUNGHWA_BUSA_1778", "R3_BYEOKDONG_GUNSU_1779", [
        ("SAME_HANJA_NAME", "SUPPORT", "E003;E005", "具純"),
        ("CHRONOLOGICAL_COMPATIBILITY", "SUPPORT", "E003;E005;I004", "1778-12 → 1779-12 → 1781-12 순차"),
        ("CAREER_PATTERN_COMPATIBLE", "SUPPORT", "E003;E005", "외임 수령직 연속 (일반적 단서)"),
    ]),
    ("L04", "R4_BAENGNYEONG_CHEOMSA_1781", "R5_YEONGHEUNG_BUSA_1782_1784", [
        ("SAME_HANJA_NAME", "SUPPORT", "I004;E006", "具純"),
        ("CHRONOLOGICAL_COMPATIBILITY", "SUPPORT", "I004;E006", "1781-12 → 1782-12-29"),
        ("CAREER_PATTERN_COMPATIBLE", "SUPPORT", "I004;E007", "변장·수령 외임 계열 (일반적 단서)"),
    ]),
    ("L05", "R5_YEONGHEUNG_BUSA_1782_1784", "R6_BYEOLGUN_EXILE_1784", [
        ("SAME_HANJA_NAME", "SUPPORT", "E016;E017", "具純"),
        ("CHRONOLOGICAL_COMPATIBILITY", "SUPPORT", "E016;E017", "1784-07-16 영흥부사 → 1784-09-23 별군직"),
        ("TEMPORAL_TENSION", "TENSION", "E016;E017", "2개월 사이 영흥부사→별군직 전환 기록 없음"),
    ]),
    ("L06", "R1_SEONJEON_BYEOLGUN_1777_1779", "R6_BYEOLGUN_EXILE_1784", [
        ("SAME_HANJA_NAME", "SUPPORT", "E004;E017", "具純"),
        ("SAME_OFFICE_TITLE_RECURRENCE", "SUPPORT", "E004;E017", "같은 별군직 직함의 재등장 (구체적 단서)"),
        ("CHRONOLOGICAL_COMPATIBILITY", "SUPPORT", "E004;E017", "중첩 없음"),
    ]),
    ("L07", "R6_BYEOLGUN_EXILE_1784", "R7_BYEOLGUN_JEJU_EXILE_1787", [
        ("SAME_HANJA_NAME", "SUPPORT", "E017;E019", "具純"),
        ("SAME_OFFICE_TITLE_RECURRENCE", "SUPPORT", "E017;E019", "1784 정배 당시 별군직, 1787 별군직"),
        ("CHRONOLOGICAL_COMPATIBILITY", "SUPPORT", "E017;E019",
         "1784-09-23 정배 → 1787-01-03 현직: 중간 해배가 있었다면 양립 가능 (조건부, L08과 같은 기준)"),
        ("RETROSPECTIVE_REFERENCE", "SUPPORT", "E024",
         "정조가 '전후로 여러 차례 곡진히 살려준 은혜' 언급 — 이전 처벌·선처 전력과 정합 (특정 사건 지칭은 아님)"),
        ("MISSING_RELEASE_RECORD", "MISSING", "E018", "1784 정배 해배·복귀 기록 없음"),
    ]),
    ("L08", "R7_BYEOLGUN_JEJU_EXILE_1787", "R8A_FORMER_BUSA_KIM_CASE_1793", [
        ("SAME_HANJA_NAME", "SUPPORT", "E019;E026", "具純"),
        ("FORMER_OFFICE_TITLE_MATCH", "SUPPORT", "E003;E006;E026",
         "1793 '전 부사' ↔ 1778 중화부사·1782 영흥부사 — 부사 직함 이력 일치 (府名은 1793 기록에 없음)"),
        ("CHRONOLOGICAL_COMPATIBILITY", "SUPPORT", "E023;E028",
         "1787-01-03 정배 → 1793-02-22 덕평 자유 거주: 중간 해배가 있었다면 양립 가능 (조건부)"),
        ("NO_COMPETING_SAME_NAME_IN_CSV", "WEAK_SUPPORT", "ALL",
         "CSV 안에 다른 具純 후보 없음 — CSV가 한 인물 중심으로 수집됐으므로 약한 단서"),
        ("AMNESTY_EXCLUSION_TENSION", "TENSION", "E023;E025",
         "勿揀赦典(사면 제외) 명시 → 일반 사면 해배로 볼 수 없음; 특별 해배 기록 필요"),
        ("MISSING_RELEASE_RECORD", "MISSING", "E025", "1787 제주 정배 이후 해배·복귀 직접 기록 없음"),
        ("MISSING_RETROSPECTIVE_REFERENCE", "MISSING", "R8A",
         "1793 기록 어디에도 제주 정배·별군직 전력이나 1787 사건 언급 없음"),
        ("MISSING_KINSHIP_BRIDGE", "MISSING", "D01",
         "1793 세그먼트에 구세덕·유효원 등 PRE1793 친족이 등장하지 않음"),
    ]),
    ("L09", "R8A_FORMER_BUSA_KIM_CASE_1793", "R8B_SINJIDO_TO_BAENGNYEONG_1794", [
        ("SAME_HANJA_NAME", "SUPPORT", "E066;E076", "具純"),
        ("EXPLICIT_CROSS_REFERENCE", "SUPPORT", "E066;E076",
         "1794 이배 기록이 '신지도에서' 백령도로 옮긴다고 명시 — 1793 배소(신지도)와 직접 연결"),
        ("SEQUENTIAL_PENAL_CHAIN", "SUPPORT", "E066;E076;E077", "공범 한재욱도 같은 도류안에서 함께 이배"),
    ]),
    ("L10", "R8B_SINJIDO_TO_BAENGNYEONG_1794", "R8C_JANGYEON_RELEASE_1795_1798", [
        ("SAME_HANJA_NAME", "SUPPORT", "E076;E080", "具純"),
        ("SEQUENTIAL_PENAL_CHAIN", "SUPPORT", "E076;E079;E080", "정배 상태 연속, 1798 형기 만료 보고"),
        ("CHRONOLOGICAL_COMPATIBILITY", "SUPPORT", "E076;E080", "1794-10-15 백령도 → 1798-02-21 장연현, 중첩 없음"),
        ("MISSING_TRANSFER_RECORD", "MISSING", "E079",
         "백령도→장연현 이배 행이 CSV에 없음 (E078 결락, 메타필드만 '1795 長淵 transfer' 언급)"),
        ("SENTENCE_RECLASSIFICATION_TENSION", "TENSION", "E066;E079;E080",
         "'감사 절도정배' → '도 3년 정배' 재분류 경위 미상"),
    ]),
]
SPECIFIC_CODES = {"SAME_OFFICE_TITLE_RECURRENCE", "RETROSPECTIVE_REFERENCE", "SEQUENTIAL_PENAL_CHAIN",
                  "FORMER_OFFICE_TITLE_MATCH"}


def classify_link(items) -> str:
    codes = {c for c, k, _, _ in items if k in ("SUPPORT", "WEAK_SUPPORT")}
    kinds = {k for _, k, _, _ in items}
    if "CONTRADICT" in kinds:
        return "CONTRADICTED"
    if "EXPLICIT_CROSS_REFERENCE" in codes:
        return "CONFIRMED"
    if "SAME_HANJA_NAME" in codes and "CHRONOLOGICAL_COMPATIBILITY" in codes and codes & SPECIFIC_CODES:
        return "HIGH_CONFIDENCE"
    if "SAME_HANJA_NAME" in codes and ("CHRONOLOGICAL_COMPATIBILITY" in codes or codes & SPECIFIC_CODES):
        return "PLAUSIBLE"
    return "UNRESOLVED"


def build_identity(df: pd.DataFrame):
    ev_rows, link_rows = [], []
    csv_assess = df.set_index("event_id").identity_bridge_status
    for lid, a, b, items in IDENTITY_LINKS:
        status = classify_link(items)
        for code, kind, evs, desc in items:
            ev_rows.append(dict(link_id=lid, identity_a=a, identity_b=b, evidence_code=code,
                                evidence_kind=kind, event_ids=evs, description=desc,
                                evidence_status="OBSERVED" if kind in ("SUPPORT", "WEAK_SUPPORT",
                                                                      "TENSION", "CONTRADICT")
                                else "OBSERVED_ABSENCE_IN_CSV"))
        # contradicting(실제 반대 증거) · tension(풀리지 않은 긴장) · missing(결락)을 엄격히 분리.
        # 해배 기록의 부재는 반대 증거가 아니라 missing transition evidence다.
        sup = [f"{c}[{e}]" for c, k, e, _ in items if k in ("SUPPORT", "WEAK_SUPPORT")]
        con = [f"{c}[{e}]" for c, k, e, _ in items if k == "CONTRADICT"]
        ten = [f"{c}[{e}]" for c, k, e, _ in items if k == "TENSION"]
        mis = [f"{c}[{e}]" for c, k, e, _ in items if k == "MISSING"]
        a_ev = GUSUN_RECORD_CLUSTERS[a][0]
        b_ev = GUSUN_RECORD_CLUSTERS[b][0]
        link_rows.append(dict(
            link_id=lid, identity_a=a, identity_b=b, link_level="RECORD_CLUSTER",
            same_person_status=status,
            supporting_evidence_count=len(sup), contradicting_evidence_count=len(con),
            tension_evidence_count=len(ten), missing_evidence_count=len(mis),
            supporting_evidence="; ".join(sup), contradicting_evidence="; ".join(con) or "NONE_IN_CSV",
            tension_evidence="; ".join(ten) or "NONE",
            missing_evidence="; ".join(mis) or "NONE",
            confidence_class=status, csv_compiler_assessment=f"{a_ev}:{nz(csv_assess.get(a_ev))} / "
                                                            f"{b_ev}:{nz(csv_assess.get(b_ev))}",
            decision_rule="CONFIRMED=explicit cross-reference; HIGH=same hanja+chronology+specific cue; "
                          "PLAUSIBLE=same hanja+generic cue; CONTRADICTED=contradicting evidence 1건 이상; "
                          "tension·missing은 판정을 강등하지 않고 별도 컬럼에 기록",
            evidence_status="DERIVED (rule over CSV evidence items)"))
    links = pd.DataFrame(link_rows)
    top = links[links.link_id == "L08"].iloc[0].to_dict()
    top.update(link_id="L00", identity_a="GUSUN_PRE1793", identity_b="GUSUN_1793PLUS",
               link_level="SEGMENT (핵심 연구질문)",
               decision_rule=top["decision_rule"] + "; 세그먼트 연결 = L08(1787↔1793) 판정을 승계")
    alias_rows = [
        dict(link_id="A01", identity_a="P_KIM_MYEONGSIN", identity_b="alias:풍각 김생원 (E035)",
             link_level="ALIAS", same_person_status="HIGH_CONFIDENCE",
             supporting_evidence_count=1, contradicting_evidence_count=0, tension_evidence_count=0,
             missing_evidence_count=1, tension_evidence="NONE",
             supporting_evidence="CSV 요약이 '풍각 김생원(김명신)'으로 괄호 동일시[E035]",
             contradicting_evidence="NONE_IN_CSV", missing_evidence="원문 대조 불가(외부 접근 금지)",
             confidence_class="HIGH_CONFIDENCE", csv_compiler_assessment="CSV parenthetical",
             decision_rule="CSV 작성자 매핑 — 독립 검증 불가 → CONFIRMED로 올리지 않음",
             evidence_status="OBSERVED (CSV mapping)"),
        dict(link_id="A02", identity_a="P_KIM_MYEONGSIN", identity_b="alias:풍각 김상제 (E038)",
             link_level="ALIAS", same_person_status="HIGH_CONFIDENCE",
             supporting_evidence_count=1, contradicting_evidence_count=0, tension_evidence_count=0,
             missing_evidence_count=1, tension_evidence="NONE",
             supporting_evidence="CSV 요약 '풍각 김상제(김명신)'[E038]; 지명 '풍각' 일치",
             contradicting_evidence="NONE_IN_CSV", missing_evidence="원문 대조 불가",
             confidence_class="HIGH_CONFIDENCE", csv_compiler_assessment="CSV parenthetical",
             decision_rule="CSV 작성자 매핑", evidence_status="OBSERVED (CSV mapping)"),
        dict(link_id="A03", identity_a="P_LEE_GWANGSEOP", identity_b="role:'병사' (E035, E037)",
             link_level="ROLE_REFERENCE", same_person_status="HIGH_CONFIDENCE",
             supporting_evidence_count=1, contradicting_evidence_count=0, tension_evidence_count=0,
             missing_evidence_count=0, tension_evidence="NONE",
             supporting_evidence="E035 subject=이광섭, 요약은 '병사가 … 명한 것'; E053 이광섭=충청도 병마절도사",
             contradicting_evidence="NONE_IN_CSV", missing_evidence="NONE",
             confidence_class="HIGH_CONFIDENCE", csv_compiler_assessment="CSV mapping",
             decision_rule="동일 사건·동일 시기 직함 일치", evidence_status="OBSERVED (CSV mapping)"),
    ]
    links = pd.concat([pd.DataFrame([top]), links, pd.DataFrame(alias_rows)], ignore_index=True)
    clusters = pd.DataFrame([dict(record_cluster=c, segment="GUSUN_1793PLUS" if c.startswith("R8")
                                  else "GUSUN_PRE1793", event_ids=";".join(ids),
                                  n_events=len(ids)) for c, ids in GUSUN_RECORD_CLUSTERS.items()])
    return links, pd.DataFrame(ev_rows), clusters


# ───────────────────────── 8. 시간 불확실성 ─────────────────────────
def build_time_uncertainty(events: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    E = events.set_index("event_id")
    U = []

    def add(uid, eid, pid, var, lo, hi, prec, before, after, utype, notes,
            assumption="UNIFORM_INTERVAL (sensitivity only; 연도별 확률 산출하지 않음)",
            narrowing=NA):
        U.append(dict(uncertainty_id=uid, event_id=eid, person_id=pid, uncertain_variable=var,
                      lower_bound=lo, upper_bound=hi, precision=prec, evidence_before=before,
                      evidence_after=after, uncertainty_type=utype, model_assumption=assumption,
                      prior_type="UNIFORM_OVER_INTERVAL" if lo != UNKNOWN and hi not in (UNKNOWN, OPEN)
                      else "IMPROPER/UNBOUNDED — 확률 해석 안 함",
                      posterior_method="DETERMINISTIC_INTERVAL_INTERSECTION (CSV 제약만; 새 증거 없음 → posterior=prior)",
                      candidate_narrowing_not_applied=narrowing, notes=notes,
                      evidence_status="DERIVED"))

    add("U_RELEASE_1784", "E018", "GUSUN_PRE1793", "T_release (1784 정배 해배·복귀)",
        E.loc["E017", "earliest_possible"], E.loc["E019", "earliest_possible"], "RANGE",
        "E017 정배 명령 1784-09-23", "E019 1787-01-03 별군직으로 활동", "INTERVAL_CENSORED",
        "개구간 (1784-09-23, 1787-01-03). L07 동일인 가정(HIGH_CONFIDENCE) 하에서만 정의됨")
    add("U_RELEASE_1787", "E025", "GUSUN_PRE1793→GUSUN_1793PLUS",
        "T_release (1787 제주 정배 해배)", E.loc["E023", "earliest_possible"],
        E.loc["E028", "earliest_possible"], "RANGE",
        "E023 1787-01-03 제주목 감사정배·勿揀赦典",
        "E028 1793-02-22 '구순 집 종' 나복 — 덕평 자유 거주 최초 '일자 확정' 관측",
        "INTERVAL_CENSORED",
        "개구간 (1787-01-03, 1793-02-22). 명목 길이 ≈ 73 음력월(윤달 미반영). 동일인(L00=HIGH_CONFIDENCE)이 아니면 이 변수 자체가 정의되지 않음",
        narrowing="E026/E027 '1793-02-early'가 실제 상순(1–10일)이면 상한 1793-02-10까지; "
                  "'본래 친숙하여 날마다 상종'은 그 이전 거주를 시사하나 기간 미상 → 적용 안 함")
    add("U_JUNGHWA_END", "E003", "GUSUN_PRE1793", "T_end(중화부사 재임)", "1778-12-24", "1779-08-10",
        "RANGE", "E003 임명", "E004 별군직 수행", "OFFICE_TRANSITION",
        "단일 관직 가정(MODEL_ASSUMPTION, CSV 근거 아님)일 때만 상한 성립",
        assumption="MODEL_ASSUMPTION: 동시에 하나의 관직")
    add("U_BYEOKDONG_END", "E005", "GUSUN_PRE1793", "T_end(벽동군수) / T_start(백령첨사)",
        "1779-12-25", "1781-12-30", "RANGE", "E005 임명", "I004 1781-12 백령첨사 재임(월 단위)",
        "OFFICE_TRANSITION", "백령첨사 임명 행 없음", assumption="MODEL_ASSUMPTION: 동시에 하나의 관직")
    add("U_BAENGNYEONG_END", "I004", "GUSUN_PRE1793", "T_end(백령첨사)", "1781-12-01", "1782-12-29",
        "RANGE", "I004", "E006 영흥부사 임명", "OFFICE_TRANSITION", "",
        assumption="MODEL_ASSUMPTION: 동시에 하나의 관직")
    add("U_BYEOLGUN_RETURN_1784", "E017", "GUSUN_PRE1793", "T_start(별군직 복귀, 영흥부사 이후)",
        "1784-07-16", "1784-09-23", "RANGE", "E016 영흥부사로 포상", "E017 별군직으로 정배",
        "OFFICE_TRANSITION", "")
    add("U_BYEOLGUN_RETURN_1787", "E019", "GUSUN_PRE1793", "T_start(1787 별군직 재직)",
        "1784-09-23", "1787-01-03", "RANGE", "E017", "E019", "OFFICE_TRANSITION",
        "U_RELEASE_1784와 같은 구간 이후")
    for eid in ["I004", "E026", "E027", "E030", "E038", "E039", "E040", "E041", "E042", "E043",
                "E044", "E045", "E046", "E047", "E048", "E049", "E070", "E071", "E072", "E073",
                "E074", "E075"]:
        ev = E.loc[eid]
        narrowing = NA
        if ev.date_qualifier == "early":
            narrowing = "한정어 'early'를 상순(1–10일)으로 읽으면 [..-01, ..-10] — 해석 규칙이므로 적용 안 함"
        elif ev.date_qualifier == "late":
            narrowing = "'체포령 뒤' + 한정어 'late' → E031(1793-02-28) 이후면 [02-28, 02-30] — E031이 그 체포령인지 CSV가 명시하지 않아 적용 안 함"
        elif eid in ("E038", "E039"):
            narrowing = "E038(구순→유제희)→E039(유제희→한재욱)→E035(03-04 체포명령) 순서라면 [03-01, 03-04] — CSV가 순서를 명시하지 않아 적용 안 함"
        add(f"U_{eid}", eid, ev.person_id, f"T_event({ev.relation_type_raw})",
            ev.earliest_possible, ev.latest_possible, "YEAR_MONTH",
            "same month", "same month", "MONTH_LEVEL_DATE",
            f"CSV date_lunar={ev.record_date_raw!r}; 플래그={ev.precision_flag}", narrowing=narrowing)
    for eid in ["E063", "E064", "E065", "E084", "E085", "E086"]:
        rule = RELATION_TIME_RULES[eid]
        add(f"U_REL_{eid}", eid, E.loc[eid, "person_id"], "T_relation(기록일≠행위일)",
            rule["earliest_start"], rule["latest_start"], "RANGE", "E028 도난(02-22)",
            "E050/E054 05-12 장계·병사 파직 청", "RECORD_VS_EVENT_DATE", rule["basis"])
    add("U_FRIENDSHIP_START", "E026", "GUSUN_1793PLUS", "T_start(구순–김명신 친교)", UNKNOWN,
        "1793-02-30", "BEFORE", "없음", "E027 단절(1793-02)", "LEFT_CENSORED",
        "시작 하한 없음 — 해배 시점(U_RELEASE_1787)과의 선후도 미상",
        assumption="NO_PRIOR (하한 없음 → 분포 가정 불가)")
    add("U_DEATH_KIM", "E056;E062", "P_KIM_MYEONGSIN", "T_death(김명신, 옥중)",
        "1793-03-04", "1793-05-27", "RANGE", "E035 체포 명령 1793-03-04 (구금 후 사망)",
        "E056 1793-05-27 암행어사 보고 '옥사'", "INTERVAL_CENSORED",
        "E050(05-12) 장계에는 사망 언급 없음(CSV 요약 기준) — 그것이 '생존'을 뜻하지 않으므로 하한을 올리지 않음")
    add("U_GUSUN_ARREST_1793", "E055", "GUSUN_1793PLUS", "T_arrest(의금부 수금 실행)",
        "1793-05-12", "1793-05-27", "RANGE", "E055 수금 명령", "E056/E059 '의금부 피수사자'",
        "INTERVAL_CENSORED", "")
    add("U_TRANSFER_JANGYEON", "E079", "GUSUN_1793PLUS", "T_transfer(백령도→장연현)",
        "1794-10-15", "1798-02-21", "RANGE", "E076 백령도 이배", "E080 '장연현 도3년 정배죄인'",
        "INTERVAL_CENSORED",
        "확실한 상한은 1798-02-21. CSV E079 시작값 1795-10-15는 지지 행이 없는 단언 → 좁히지 않음",
        narrowing="CSV 단언(E079 date_lunar)을 채택하면 상한 1795-10-15")
    add("U_SENTENCE_CONVERSION", "E079", "GUSUN_1793PLUS", "T_conversion(절도정배→도3년)",
        "1793-06-13", "1798-02-21", "RANGE", "E066 감사 절도정배", "E080 도3년 정배",
        "INTERVAL_CENSORED", "법적 근거·일자 미상 (E079 modeling_note)")
    add("U_POST1798", "E083", "GUSUN_1793PLUS", "T_any_later_event / T_death(구순)",
        "1798-02-22", OPEN, "OPEN_INTERVAL", "E082 방송", "없음", "RIGHT_CENSORED",
        "검색 실패를 사망·은거로 해석하지 않음", assumption="NO_PRIOR (상한 없음)")
    return pd.DataFrame(U)


# ───────────────────────── 9. 분석 ─────────────────────────
PERIODS = [  # CSV phase 기반 (DERIVED)
    ("P1_CAREER_1777_1783", {"identity_background", "career", "career_identity_bridge"}, None),
    ("P2_YEONGHEUNG_EXILE_1784", {"administrative_conflict", "administrative_scrutiny", "discipline"}, None),
    ("P3_FALSE_ACCUSATION_1787", {"false_accusation_1787"}, None),
    ("P4a_KIM_CASE_1793-02", {"kim_case_1793"}, "1793-02"),
    ("P4b_KIM_CASE_1793-03", {"kim_case_1793"}, "1793-03"),
    ("P4c_KIM_CASE_1793-05", {"kim_case_1793"}, "1793-05"),
    ("P4d_KIM_CASE_1793-06", {"kim_case_1793"}, "1793-06"),
    ("P5_POST_SENTENCE_1794_1798", {"post_sentence"}, None),
]
EGO = {"GUSUN_PRE1793", "GUSUN_1793PLUS"}


def assign_period(edges: pd.DataFrame, events: pd.DataFrame) -> pd.Series:
    E = events.set_index("event_id")
    out = []
    for _, e in edges.iterrows():
        ev = E.loc[e.period_event_id]
        found = NA
        for name, phases, month in PERIODS:
            if ev.phase in phases and (month is None or ev.record_date_raw.startswith(month)):
                found = name
                break
        out.append(found)
    return pd.Series(out, index=edges.index)


def composition(edges: pd.DataFrame) -> pd.DataFrame:
    rows = []
    prev = None
    for name, _, _ in PERIODS:
        sub = edges[edges.period == name]
        ego = sub[sub.source_person.isin(EGO) | sub.target_person.isin(EGO)]
        row = dict(period=name, n_edges_all=len(sub), n_edges_ego=len(ego),
                   n_alters_ego=len((set(ego.source_person) | set(ego.target_person)) - EGO),
                   n_actors_all=len(set(sub.source_person) | set(sub.target_person)))
        for g in GROUP_ORDER:
            row[f"ego_{g}"] = int((ego.relation_group == g).sum())
            row[f"all_{g}"] = int((sub.relation_group == g).sum())
        for g in GROUP_ORDER:
            row[f"ego_share_{g}"] = round(row[f"ego_{g}"] / len(ego), 3) if len(ego) else None
        if prev is not None:
            for g in GROUP_ORDER:
                row[f"delta_ego_{g}"] = row[f"ego_{g}"] - prev[f"ego_{g}"]
        prev = row
        rows.append(row)
    return pd.DataFrame(rows)


def turnover(edges: pd.DataFrame) -> pd.DataFrame:
    rows, prev, seen = [], set(), set()
    for name, _, _ in PERIODS:
        sub = edges[edges.period == name]
        actors = (set(sub.source_person) | set(sub.target_person)) - EGO
        rows.append(dict(period=name, n_actors=len(actors),
                         new_actors=";".join(sorted(actors - seen)),
                         returning_from_earlier=";".join(sorted((actors & seen) - prev)),
                         continuing_from_previous=";".join(sorted(actors & prev)),
                         disappeared_since_previous=";".join(sorted(prev - actors)),
                         n_new=len(actors - seen), n_continuing=len(actors & prev),
                         n_disappeared=len(prev - actors),
                         ego_segment_present=";".join(sorted((set(sub.source_person) |
                                                               set(sub.target_person)) & EGO)),
                         caution="'사라짐'은 기록에서 관측되지 않음이며 관계 종료가 아님"))
        prev = actors
        seen |= actors
    return pd.DataFrame(rows)


def edge_sort_key(e) -> tuple:
    def k(v):
        return lord(v) if is_day(v) else None
    lo = k(e.earliest_start)
    hi = k(e.latest_start)
    if lo is None and hi is None:
        return (-1e9, -1e9)
    if lo is None:
        return (-1e9, hi)
    return (lo, hi if hi is not None else lo)


def transitions(edges: pd.DataFrame) -> pd.DataFrame:
    rows = []
    edges = edges.copy()
    edges["pair"] = edges.apply(lambda e: tuple(sorted([e.source_person, e.target_person])), axis=1)
    for pair, g in edges.groupby("pair"):
        types = g.relation_type.unique()
        if len(types) < 2:
            continue
        g = g.assign(_k=g.apply(edge_sort_key, axis=1)).sort_values("_k")
        seq, prev_k, order_notes = [], None, []
        for _, e in g.iterrows():
            seq.append(f"{e.relation_type}[{e.source_event_id}]")
            if prev_k is not None:
                if e._k[0] <= prev_k[1] and e._k != prev_k:
                    order_notes.append(f"{e.source_event_id}: 이전 관계와 시간구간 중첩 → 순서 불확실")
                elif e._k == prev_k:
                    order_notes.append(f"{e.source_event_id}: 동일 시점 → 순서 미정")
            prev_k = e._k
        compact = []
        for t in g.relation_type:
            if not compact or compact[-1] != t:
                compact.append(t)
        rows.append(dict(pair=" — ".join(pair), n_edges=len(g), n_relation_types=len(types),
                         transition_compact=" → ".join(compact),
                         transition_detail=" → ".join(seq),
                         time_window=f"{g.iloc[0].earliest_start}…{g.iloc[-1].latest_end}",
                         ordering_caveats="; ".join(order_notes) or "NONE",
                         evidence_status="DERIVED (CSV edges ordered by time bounds)",
                         involves_ego=bool(set(pair) & EGO)))
    return pd.DataFrame(rows).sort_values(["involves_ego", "n_relation_types"],
                                          ascending=[False, False])


# 1793 단계(stage) — CSV 역할필드·직함으로 배정 (DERIVED)
STAGES = [
    ("S0_HOUSEHOLD", ["P_NABOK", "P_MYEONGEOP", "N_HOUSE_SERVANTS"]),
    ("S1_COMPLAINANT", ["GUSUN_1793PLUS"]),
    ("S2_CAMP_STAFF(병영 비장·영리)", ["P_YU_JEHUI", "P_HAN_JAEUK", "N_UNNAMED_OFFICER", "N_MILITARY_SOLDIERS"]),
    ("S3_ARREST_TEAM(장교)", ["P_LEE_JINUK", "P_JO_GYEWAN"]),
    ("S4_COMMANDERS(병사·영장)", ["P_LEE_GWANGSEOP", "P_LEE_MUNHYEOP"]),
    ("S5_SUSPECTS_WITNESSES", ["P_KIM_MYEONGSIN", "P_JA_MIDEOK", "P_BYEON_JIDEUL", "P_BYEON_JAEDOL",
                               "P_JEONG_WONDOL", "P_LEE_JIPGEO", "P_KIM_GAPDEUK", "P_KIM_SEONGSON",
                               "P_KIM_HEUNGDEUK", "P_KIM_HEUNGGIL", "N_INNOCENT_COMMONERS"]),
    ("S6_GOVERNOR(관찰사)", ["P_LEE_HYEONGWON"]),
    ("S7_SECRET_INSPECTOR(암행어사)", ["P_LEE_JOWON"]),
    ("S8_SPECIAL_INVESTIGATOR(안핵어사)", ["P_HONG_DAEHYEOP"]),
    ("S9_CENTRAL(국왕·비변사·의금부)", ["P_JEONGJO", "P_BIBEONSA", "P_UIGEUMBU"]),
]


def stage_handoffs(edges: pd.DataFrame) -> pd.DataFrame:
    sub = edges[edges.phase == "kim_case_1793"]
    rows = []
    stage_of = {m: s for s, ms in STAGES for m in ms}
    pairs = [(STAGES[i][0], STAGES[i + 1][0]) for i in range(len(STAGES) - 1)]
    pairs += [("S1_COMPLAINANT", "S4_COMMANDERS(병사·영장)"),
              ("S1_COMPLAINANT", "S5_SUSPECTS_WITNESSES"),
              ("S2_CAMP_STAFF(병영 비장·영리)", "S5_SUSPECTS_WITNESSES"),
              ("S4_COMMANDERS(병사·영장)", "S5_SUSPECTS_WITNESSES"),
              ("S2_CAMP_STAFF(병영 비장·영리)", "S4_COMMANDERS(병사·영장)"),
              ("S6_GOVERNOR(관찰사)", "S9_CENTRAL(국왕·비변사·의금부)"),
              ("S7_SECRET_INSPECTOR(암행어사)", "S9_CENTRAL(국왕·비변사·의금부)"),
              ("S8_SPECIAL_INVESTIGATOR(안핵어사)", "S9_CENTRAL(국왕·비변사·의금부)"),
              ("S9_CENTRAL(국왕·비변사·의금부)", "S1_COMPLAINANT")]
    for a, b in pairs:
        hits = sub[(sub.source_person.map(stage_of) == a) & (sub.target_person.map(stage_of) == b)]
        rev = sub[(sub.source_person.map(stage_of) == b) & (sub.target_person.map(stage_of) == a)]
        rows.append(dict(
            from_stage=a, to_stage=b, n_edges_forward=len(hits), n_edges_reverse=len(rev),
            edges_forward="; ".join(f"{e.source_person}→{e.target_person}:{e.relation_type}"
                                    f"[{e.source_event_id}]" for _, e in hits.iterrows()) or NA,
            edges_reverse="; ".join(f"{e.source_person}→{e.target_person}:{e.relation_type}"
                                    f"[{e.source_event_id}]" for _, e in rev.iterrows()) or NA,
            link_status="EXPLICIT_IN_CSV" if len(hits) else (
                "ONLY_REVERSE_DIRECTION" if len(rev) else "NO_CSV_EDGE (자동 연결하지 않음)")))
    return pd.DataFrame(rows)


# 같은 날 순서를 CSV 요약문이 명시하는 경우만 (event_a가 event_b보다 먼저)
EXPLICIT_ORDER = [
    ("E035", "E037", "E037 요약: '김명신 체포 길에 들른 조계완' → 체포 명령이 편지보다 먼저"),
    ("E036", "E037", "E036은 김명신과 '함께' 잡으라는 같은 명령(E035) → 역시 편지보다 먼저"),
]


def time_respecting_paths(edges: pd.DataFrame, scenario: str, max_len: int = 4) -> list[dict]:
    """GUSUN_1793PLUS에서 출발하는 시간순 경로. scenario: EARLY/LATE (월 단위·구간 사건의 배치)."""
    # 절차 경로는 방향성 있는 행위 edge만 따른다 (친족·가내·이웃·친교 같은 대칭 상태 관계 제외)
    sub = edges[(edges.phase == "kim_case_1793") & edges.directed].copy()

    def t(e):
        lo = e.earliest_start if is_day(e.earliest_start) else None
        hi = e.latest_start if is_day(e.latest_start) else None
        v = lo if scenario == "EARLY" else hi
        v = v or lo or hi
        return lord(v) if v else None

    sub["t"] = sub.apply(t, axis=1)
    sub = sub[sub.t.notna()]
    order_after = {(b, a) for a, b, _ in EXPLICIT_ORDER}  # (later, earlier)
    adj = {}
    for _, e in sub.iterrows():
        adj.setdefault(e.source_person, []).append(e)
    results = []

    def other(e, node):
        return e.target_person if e.source_person == node else e.source_person

    def dfs(node, path, last_t, last_ev, visited):
        if path:
            results.append(list(path))
        if len(path) >= max_len:
            return
        for e in adj.get(node, []):
            nxt = other(e, node)
            if nxt in visited:
                continue
            if e.t < last_t:
                continue
            if last_ev and (last_ev, e.source_event_id) in order_after:
                continue  # 다음 edge가 이전 edge보다 먼저 일어났음이 명시됨
            dfs(nxt, path + [e], e.t, e.source_event_id, visited | {nxt})

    dfs("GUSUN_1793PLUS", [], -1, None, {"GUSUN_1793PLUS"})
    return results


def institutional_paths(edges: pd.DataFrame) -> pd.DataFrame:
    targets = {"P_KIM_MYEONGSIN", "P_JA_MIDEOK", "P_JEONG_WONDOL", "P_BYEON_JIDEUL",
               "P_KIM_GAPDEUK", "P_LEE_GWANGSEOP", "P_HAN_JAEUK", "P_YU_JEHUI"}
    keyed = {}
    for scen in ("EARLY", "LATE"):
        for p in time_respecting_paths(edges, scen):
            end = p[-1].target_person if p[-1].target_person != "GUSUN_1793PLUS" else p[-1].source_person
            if end not in targets:
                continue
            key = tuple(e.edge_id for e in p)
            k = keyed.setdefault(key, dict(path=p, scen=set()))
            k["scen"].add(scen)
    rows = []
    for key, v in keyed.items():
        p = v["path"]
        nodes = ["GUSUN_1793PLUS"]
        for e in p:
            nodes.append(e.target_person if e.source_person == nodes[-1] else e.source_person)
        same_day = any(p[i].t == p[i + 1].t for i in range(len(p) - 1))
        rows.append(dict(
            path_nodes=" → ".join(nodes),
            path_relations=" → ".join(f"{e.relation_type}[{e.source_event_id}]" for e in p),
            path_dates=" → ".join(f"{e.earliest_start}..{e.latest_start}" if e.earliest_start != e.latest_start
                                  else e.earliest_start for e in p),
            length=len(p), end_node=nodes[-1],
            valid_EARLY="EARLY" in v["scen"], valid_LATE="LATE" in v["scen"],
            robust_to_month_placement=v["scen"] == {"EARLY", "LATE"},
            contains_same_day_step=same_day,
            contains_derived_edge=any(e.evidence_status == "DERIVED" for e in p),
            interpretation="시간순 경로가 존재한다는 뜻일 뿐 인과·전달을 증명하지 않음",
        ))
    out = pd.DataFrame(rows)
    if not len(out):
        return out
    # 같은 노드열·같은 관계유형열인데 병렬 edge(E040–E044 등)만 다른 경로는 하나로 묶는다
    out["relation_types"] = out.path_relations.str.replace(r"\[[^\]]*\]", "", regex=True)
    agg = (out.groupby(["path_nodes", "relation_types"], sort=False)
              .agg(path_relations=("path_relations", lambda s: " || ".join(s)),
                   n_parallel_variants=("path_relations", "size"),
                   path_dates=("path_dates", "first"), length=("length", "first"),
                   end_node=("end_node", "first"), valid_EARLY=("valid_EARLY", "all"),
                   valid_LATE=("valid_LATE", "all"),
                   robust_to_month_placement=("robust_to_month_placement", "all"),
                   contains_same_day_step=("contains_same_day_step", "any"),
                   contains_derived_edge=("contains_derived_edge", "any"),
                   interpretation=("interpretation", "first"))
              .reset_index())
    return agg.sort_values(["robust_to_month_placement", "length"], ascending=[False, True])


def sensitivity(edges: pd.DataFrame, paths: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scen in ("EARLY", "LATE"):
        col = f"valid_{scen}"
        to_kim = paths[(paths.end_node == "P_KIM_MYEONGSIN") & paths[col]] if len(paths) else paths
        rows.append(dict(analysis="time-respecting paths GUSUN_1793PLUS→김명신", scenario=scen,
                         scenario_definition=("월 단위·구간 edge를 하한(earliest)에 배치" if scen == "EARLY"
                                              else "월 단위·구간 edge를 상한(latest)에 배치"),
                         n_paths=len(to_kim),
                         shortest=to_kim.sort_values("length").iloc[0].path_nodes if len(to_kim) else NA))
    # 단계: 1793-03 월 단위 사건이 03-04 체포명령보다 앞서는가
    rows.append(dict(analysis="1793-03 월 단위 사건(E038,E039 등) vs E035(03-04) 순서",
                     scenario="BOUNDS", scenario_definition="[1793-03-01, 1793-03-30] vs 1793-03-04",
                     n_paths=NA,
                     shortest="03-04 이전/이후 모두 가능 → 'E038→E039→체포명령' 인과 순서는 UNRESOLVED"))
    rows.append(dict(analysis="T_release_1787 interval", scenario="BOUNDS",
                     scenario_definition="(1787-01-03, 1793-02-22)", n_paths=NA,
                     shortest="연도별 확률 미산출. 어떤 해배 시점을 택해도 L00 판정(HIGH_CONFIDENCE)은 변하지 않음 — 판정은 해배 시점이 아니라 해배 '기록'의 존재에 달려 있음"))
    return pd.DataFrame(rows)


def centrality(edges: pd.DataFrame, persons: pd.DataFrame) -> pd.DataFrame:
    rows = []
    scopes = [("ALL", edges)] + [(name, edges[edges.period == name]) for name, _, _ in PERIODS]
    names = persons.set_index("person_id").name_ko.to_dict()
    for scope, sub in scopes:
        if sub.empty:
            continue
        G = nx.Graph()
        for _, e in sub.iterrows():
            G.add_edge(e.source_person, e.target_person)
        DG = nx.DiGraph()
        for _, e in sub.iterrows():
            DG.add_edge(e.source_person, e.target_person)
            if not e.directed:
                DG.add_edge(e.target_person, e.source_person)
        deg = nx.degree_centrality(G)
        btw = nx.betweenness_centrality(G)
        pr = nx.pagerank(DG) if DG.number_of_edges() else {}
        mult = sub.assign(p=sub.source_person).groupby("p").size().add(
            sub.assign(p=sub.target_person).groupby("p").size(), fill_value=0)
        layers = {}
        for _, e in sub.iterrows():
            for p in (e.source_person, e.target_person):
                layers.setdefault(p, set()).add(e.relation_group)
        for n in G.nodes:
            rows.append(dict(scope=scope, person_id=n, name_ko=names.get(n, n),
                             n_edge_records=int(mult.get(n, 0)), n_distinct_neighbors=G.degree(n),
                             n_relation_groups=len(layers.get(n, ())),
                             relation_groups=";".join(sorted(layers.get(n, ()))),
                             degree_centrality=round(deg[n], 4),
                             betweenness=round(btw[n], 4), pagerank=round(pr.get(n, 0), 4),
                             interpretation_warning="관측 편향 지표 — 권력·영향력·중요성 아님",
                             evidence_status="INFERRED (graph computation over observed+derived edges)"))
    return pd.DataFrame(rows)


# ───────────────────────── 10. 검증 ─────────────────────────
FORBIDDEN_NET = ("import requests", "import urllib", "from urllib", "import http.client",
                 "webbrowser", "urlopen(", "httpx", "aiohttp", "requests.get(")
# 'import socket'은 HTTP 클라이언트가 아니라 run_all.py의 차단 가드에 필요하므로 위 목록에서 뺐다.
# 대신 socket을 import하는 파일을 검증 detail에 별도로 나열한다.


def validate(df, events, edges, persons, uncert, career, identity, net_attempts: list) -> pd.DataFrame:
    res = []

    def chk(n, name, ok, detail):
        res.append(dict(check_no=n, check=name, result="PASS" if ok else "FAIL", detail=detail))

    def ordv(v):
        return lord(v) if is_day(v) else None

    # 1
    bad = [r.event_id for _, r in events.iterrows()
           if is_day(r.event_start) and is_day(r.event_end) and lord(r.event_start) > lord(r.event_end)]
    bad += [r.edge_id for _, r in edges.iterrows()
            if is_day(r.start_date) and is_day(r.end_date) and lord(r.start_date) > lord(r.end_date)]
    chk(1, "event_start > event_end 없음", not bad, f"위반 {bad}" if bad else
        f"events {len(events)}행·edges {len(edges)}행 검사")
    # 2
    bad = []
    for _, r in events.iterrows():
        a, b = ordv(r.earliest_possible), ordv(r.latest_possible)
        if a is not None and b is not None and a > b:
            bad.append(r.event_id)
    for _, r in edges.iterrows():
        for lo, hi in (("earliest_start", "latest_start"), ("earliest_end", "latest_end"),
                       ("earliest_start", "latest_end")):
            a, b = ordv(r[lo]), ordv(r[hi])
            if a is not None and b is not None and a > b:
                bad.append(f"{r.edge_id}:{lo}>{hi}")
    for _, r in uncert.iterrows():
        a, b = ordv(r.lower_bound), ordv(r.upper_bound)
        if a is not None and b is not None and a > b:
            bad.append(r.uncertainty_id)
    for _, r in career.iterrows():
        a, b = ordv(r.start), ordv(r.latest_end)
        if a is not None and b is not None and a > b:
            bad.append(r.spell_id)
        a, b = ordv(r.earliest_end), ordv(r.latest_end)
        if a is not None and b is not None and a > b:
            bad.append(r.spell_id + ":end")
    chk(2, "earliest_possible > latest_possible 없음 (events·edges·uncertainty·career)", not bad,
        f"위반 {bad}" if bad else "모든 하한 ≤ 상한")
    # 3
    pids = set(persons.person_id)
    bad = sorted((set(edges.source_person) | set(edges.target_person)) - pids)
    chk(3, "edge가 존재하지 않는 person_id를 참조하지 않음", not bad, f"미등록 {bad}" if bad else
        f"{len(pids)} persons")
    # 4
    dup_e = events.event_id[events.event_id.duplicated()].tolist()
    dup_x = edges.edge_id[edges.edge_id.duplicated()].tolist()
    chk(4, "event_id·edge_id 중복 없음", not dup_e and not dup_x, f"dup events {dup_e}, edges {dup_x}")
    # 5
    bad = sorted(set(edges.relation_type) - set(RELATION_VOCAB))
    chk(5, "relation_type ∈ 정의된 vocabulary", not bad, f"위반 {bad}" if bad else
        f"사용된 유형 {sorted(set(edges.relation_type))}")
    # 6
    bad = []
    for _, r in events.iterrows():
        if r.earliest_possible == UNKNOWN and pd.notna(r.plot_x_start):
            bad.append(r.event_id)
        if r.latest_possible in (UNKNOWN, OPEN) and pd.notna(r.plot_x_end):
            bad.append(r.event_id)
        if r.time_precision == "YEAR_MONTH" and is_day(r.event_start):
            bad.append(f"{r.event_id}:month→day 생성")
    for c in ("start_date", "end_date"):
        for _, r in edges.iterrows():
            if r.time_precision in ("YEAR_MONTH", "RANGE", "BEFORE", "OPEN_INTERVAL", "UNKNOWN") \
                    and is_day(r[c]) and r[c] != r.earliest_start:
                bad.append(f"{r.edge_id}:{c}")
    chk(6, "UNKNOWN 날짜를 실제 날짜처럼 계산에 사용하지 않음; 월 단위에 일 생성 없음", not bad,
        f"위반 {bad}" if bad else "UNKNOWN→plot_x=NaN; 월 단위 event_start는 YYYY-MM 유지")
    # 7
    bad = events[events.rank_level != NA].event_id.tolist()
    lane_bad = [o for o in OFFICE_LANE if any(s in o for s in ("정배", "파직", "수감", "죄인"))]
    st_bad = events[events.career_state.isin(["EXILED", "IMPRISONED", "DISMISSED"]) &
                    events.administrative_scope.isin(["COURT", "CENTRAL", "LOCAL", "MILITARY", "PROVINCIAL"]) &
                    events.person_id.isin(EGO)].event_id.tolist()
    chk(7, "EXILED/DISMISSED/IMPRISONED을 관직 level로 오인하지 않음", not bad and not lane_bad and not st_bad,
        f"rank_level 값 {bad}; 관직 lane 오염 {lane_bad}; 처벌상태+현직 scope {st_bad}" if (bad or lane_bad or st_bad)
        else "rank_level 전부 NA(품계 부재); 처벌 상태는 career_state에만 존재; 관직 lane에 상태 없음")
    # 8
    raw_ids = set(df.event_id)
    raw_actor = set(df.subject_id) | set(df.object_id)
    bad = [p for p in persons.csv_original_id if p not in raw_actor]
    for _, e in edges.iterrows():
        for evid in str(e.source_event_id).split(";"):
            if evid not in raw_ids:
                bad.append(f"{e.edge_id}:{evid}")
    raw_txt = df.set_index("event_id")
    for d in DERIVED_EDGES:
        row = raw_txt.loc[d["ev"].split(";")[0]]
        text = " ".join(str(row[c]) for c in ("subject_name_ko", "object_name_ko", "subject_office_status",
                                               "object_office_status", "event_summary",
                                               "source_support_note", "subject_role_relative_to_gu",
                                               "object_role_relative_to_gu", "identity_link_basis")
                        if pd.notna(row[c]))
        for name in d["check"]:
            if name not in text:
                bad.append(f"{d['id']}: '{name}' not in source row text")
    for ev_id in set(career.evidence_start.str.split(";").sum() + career.evidence_end.str.split(";").sum()):
        if ev_id not in raw_ids:
            bad.append(f"career:{ev_id}")
    off_bad = [o for o in events[events.person_id.isin(EGO)].office_name.unique()
               if o != NA and not any(part in " ".join(df.subject_office_status.dropna().tolist() +
                                                       df.object_office_status.dropna().tolist())
                                      for part in [o.split("(")[0]])]
    bad += [f"office:{o}" for o in off_bad]
    chk(8, "원본 CSV에 없는 정보를 생성하지 않음 (인물·사건 id·파생 edge 근거문·관직명)", not bad,
        f"위반 {bad}" if bad else
        f"persons {len(persons)} ⊂ CSV ids; edges {len(edges)} 모두 CSV event_id 참조; 파생 edge {len(DERIVED_EDGES)}개 근거문 확인")
    # 9
    # 정적 검사: scripts/*.py 전체를 줄 단위로 스캔. 제외하는 것은 FORBIDDEN_NET 패턴 정의 2줄뿐이며
    # 제외한 줄 번호를 detail에 그대로 남긴다. 실제 보증은 run_all.py의 런타임 socket guard다.
    hits, skipped, socket_importers = [], [], []
    for f in sorted(Path(__file__).parent.glob("*.py")):
        lines = f.read_text(encoding="utf-8").splitlines()
        socket_importers += [f"{f.name}:{i}" for i, ln in enumerate(lines, 1)
                             if ln.strip() == "import socket"]
        for i, line in enumerate(lines, 1):
            is_def = line.startswith("FORBIDDEN_NET = (") or (
                i > 1 and lines[i - 2].startswith("FORBIDDEN_NET = ("))
            for pat in FORBIDDEN_NET:
                if pat in line:
                    (skipped if is_def else hits).append(f"{f.name}:{i}:{pat}")
    chk(9, "source_url 실제 접속 시도 없음", not hits and not net_attempts,
        f"런타임 소켓 연결 시도 {len(net_attempts)}건 (socket guard); 정적 검사 위반 {hits or '없음'}; "
        f"패턴 정의 줄이라 제외한 매치 {len(skipped)}건; socket import 위치 {socket_importers} "
        f"(연결 차단 가드 용도)")
    return pd.DataFrame(res)


# ───────────────────────── 실행 ─────────────────────────
def run(net_attempts: list) -> dict:
    OUT.mkdir(exist_ok=True)
    INT.mkdir(exist_ok=True)
    path = find_input()
    df = load_raw(path)

    prof = profile(df, path)
    (INT / "01_input_profile.json").write_text(json.dumps(prof, ensure_ascii=False, indent=2),
                                                encoding="utf-8")
    dq = quality_checks(df)
    write(dq, "02_data_quality_findings.csv", inter=True)
    prov = source_provenance(df)
    write(prov, "gusun_source_provenance.csv")

    events = build_events(df)
    write(events, "03_events_normalized.csv", inter=True)
    edges = build_edges(df, events)
    edges["period"] = assign_period(edges, events)
    write(edges, "04_temporal_edges.csv", inter=True)
    persons = build_persons(df, edges)
    write(persons, "05_persons.csv", inter=True)
    career = build_career_states(events)
    write(career, "06_gusun_career_states.csv", inter=True)
    links, id_ev, clusters = build_identity(df)
    write(id_ev, "07_identity_evidence_items.csv", inter=True)
    uncert = build_time_uncertainty(events, edges)
    write(uncert, "08_time_uncertainty.csv", inter=True)

    comp = composition(edges)
    turn = turnover(edges)
    trans = transitions(edges)
    handoff = stage_handoffs(edges)
    paths = institutional_paths(edges)
    sens = sensitivity(edges, paths)
    cent = centrality(edges, persons)

    # 최종 산출물
    write(persons, "gusun_persons.csv")
    write(events, "gusun_events.csv")
    write(edges, "gusun_temporal_edges.csv")
    write(links, "gusun_identity_links.csv")
    write(id_ev, "gusun_identity_evidence.csv")
    write(clusters, "gusun_identity_record_clusters.csv")
    write(uncert, "gusun_time_uncertainty.csv")
    write(career, "gusun_career_states.csv")
    write(cent, "gusun_network_metrics.csv")
    write(comp, "gusun_network_composition.csv")
    write(turn, "gusun_node_turnover.csv")
    write(trans, "gusun_edge_transitions.csv")
    write(handoff, "gusun_stage_handoffs.csv")
    write(paths, "gusun_institutional_paths.csv")
    write(sens, "gusun_sensitivity_analysis.csv")
    write(dq, "gusun_data_quality_findings.csv")

    val = validate(df, events, edges, persons, uncert, career, links, net_attempts)
    write(val, "gusun_validation_report.csv")
    return dict(df=df, prof=prof, dq=dq, prov=prov, events=events, edges=edges, persons=persons,
                career=career, links=links, id_ev=id_ev, clusters=clusters, uncert=uncert,
                comp=comp, turn=turn, trans=trans, handoff=handoff, paths=paths, sens=sens,
                cent=cent, val=val)
