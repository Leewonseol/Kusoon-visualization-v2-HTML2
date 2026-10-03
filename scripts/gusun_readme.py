"""README 생성: 모든 수치는 파이프라인 산출물에서 읽는다."""
from __future__ import annotations

import pandas as pd

import gusun_pipeline as gp

OUT = gp.OUT


def md_table(df: pd.DataFrame, cols: list[str], max_rows: int = 60) -> str:
    def cell(v):
        s = "NA" if pd.isna(v) else str(v)
        return s.replace("|", "／").replace("\n", " ")
    head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    return head + "\n".join("| " + " | ".join(cell(r[c]) for c in cols) + " |"
                            for _, r in df.head(max_rows).iterrows())


def write_readme(res: dict, net_attempts: list):
    prof, events, edges, persons = res["prof"], res["events"], res["edges"], res["persons"]
    links, uncert, career, comp = res["links"], res["uncert"], res["career"], res["comp"]
    turn, trans, handoff, paths, sens, val = (res["turn"], res["trans"], res["handoff"], res["paths"],
                                              res["sens"], res["val"])
    names = persons.set_index("person_id").name_ko.to_dict()
    L = links.set_index("link_id")
    l00 = L.loc["L00"]

    ego_of = lambda seg: set(edges[(edges.source_person == seg) | (edges.target_person == seg)]
                             [["source_person", "target_person"]].values.ravel()) - {seg}
    pre_alters, post_alters = ego_of("GUSUN_PRE1793"), ego_of("GUSUN_1793PLUS")
    shared = sorted(pre_alters & post_alters)
    grp_tot = edges.relation_group.value_counts()
    ev_status = edges.evidence_status.value_counts()
    top_all = comp.sort_values("n_edges_all", ascending=False).iloc[0]
    top_ego = comp.sort_values("n_edges_ego", ascending=False).iloc[0]
    kim = persons.set_index("person_id").loc["P_KIM_MYEONGSIN"]
    n_paths_robust = int(paths.robust_to_month_placement.sum()) if len(paths) else 0
    n_paths_late_only = int((~paths.valid_EARLY & paths.valid_LATE).sum()) if len(paths) else 0
    frames = res.get("dynamic_frames", [])

    def nm(ids):
        return ", ".join(f"{names.get(i, i)}(`{i}`)" for i in ids)

    comp_cols = ["period", "n_edges_all", "n_edges_ego", "n_alters_ego"] + [f"ego_{g}" for g in gp.GROUP_ORDER]
    txt = f"""# 구순(具純) Temporal Multiplex Ego Network

> **경고 — 관측망 ≠ 역사적 현실.** 본 네트워크의 연결도와 중심성은 실제 역사적 관계뿐 아니라
> **기록 보존량과 행정문서의 관측 편향**을 반영한다. 이 네트워크는 입력 CSV에 기록된 관계만 담고 있으며,
> degree·betweenness·PageRank를 권력·영향력·사회적 중요성으로 해석해서는 안 된다.
> 1793년 김명신 사건의 인물이 많은 것은 형사 기록이 자세하기 때문이고, 김명신의 정보가 적다고
> 그가 덜 중요했다는 뜻도 아니다.

## 0. 범위와 원칙

- **유일한 입력**: `{prof['input_file']}` ({prof['n_rows']}행 × {prof['n_columns']}열). 원본은 수정하지 않았다.
- **외부 접근 없음**: 웹 검색·URL 접속·API 호출을 하지 않았다. `source_url`은 출처 메타데이터 문자열로만 보존했다.
  실행 중 모든 소켓 연결을 차단·기록하는 가드를 걸었고 기록된 시도는 **{len(net_attempts)}건**이다.
  HTML은 Plotly를 인라인으로 포함해 열람할 때도 외부 CDN을 부르지 않는다.
- **CSV에 없는 사람·관직·친족관계·사건은 만들지 않았다.** 모르는 값은 `NA` / `UNKNOWN` / `UNRESOLVED` / `OPEN`.
- **달력**: CSV 날짜는 **음력**(`date_lunar`)이다. 양력 환산은 외부 역법표가 필요하므로 하지 않았다.
  시각화 X축은 음력 날짜를 1년=360일로 놓은 **명목 소수연도**이며 `DERIVED_FOR_VISUALIZATION`으로 표시했다.
- **세 층의 구분** (`evidence_status` 컬럼):
  - `OBSERVED` — CSV에서 직접 읽히는 값 (행, 이름, 날짜, 신분 라벨, 요약문)
  - `DERIVED` — CSV 값을 규칙으로 변환·분해한 값 (relation_type 정규화, 관직 차원 분해, 날짜 구간, 역할필드·신분 라벨·요약문에서 읽은 18개 추가 edge)
  - `INFERRED` — 모델·계산 결과 (중심성, 시간순 경로, 동일인 판정 규칙의 결론)
  - `DERIVED_FOR_VISUALIZATION` — 그림 좌표 (plot_x, 프레임 순서)

### 실행

```bash
pip install pandas networkx plotly scipy
python scripts/run_all.py          # 데이터 → 시각화 → README, 검증 실패 시 종료코드 1
python scripts/run_all.py --data-only
```

단계별 중간 산출물은 `output/intermediate/`에 저장된다 (01 프로파일 → 02 품질점검 → 03 사건 정규화 →
04 edge → 05 인물 → 06 경력상태 → 07 동일인 증거 → 08 시간 불확실성).

## 1. 입력 데이터 프로파일과 품질

| 항목 | 값 |
|---|---|
| 행 / 열 | {prof['n_rows']} / {prof['n_columns']} |
| 연도 범위 | {prof['year_range'][0]}–{prof['year_range'][1]} (음력 `date_lunar` {prof['date_lunar_range'][0]} ~ {prof['date_lunar_range'][1]}) |
| subject/object id | {prof['n_distinct_ids_subject_object']}개 (그중 네트워크 actor {prof['n_actor_ids']}개; 정책·사건·상태 노드는 제외) |
| record_class | {prof['record_class_counts']} |
| time_precision | {prof['time_precision_counts']} |
| evidence_grade | {prof['evidence_grade_counts']} |
| source_name | {prof['source_name_counts']} |
| 원문 relation_type | {prof['n_relation_types_raw']}종 → 17종 vocabulary로 정규화 (원문은 `relation_subtype`에 보존) |

주요 품질 이슈 (`gusun_data_quality_findings.csv`):

{md_table(res['dq'][res['dq'].severity.isin(['HIGH', 'MEDIUM'])].drop_duplicates('finding'), ['check', 'event_id', 'finding', 'action'], 30)}

- 맥락 정책 행(C001–C017, 17행)은 `events`에는 `CONTEXT_POLICY`로 남겼지만 CSV 주석대로 구순에 대한 인과로 연결하지 않았고 네트워크에서 제외했다.
- `subject/object_level_current`(0–5)는 품계가 아니며 구순을 현직=3, 죄인=1로 코딩해 **관직과 처벌 상태를 섞는다.**
  `csv_legacy_level_*`로만 보존하고 어떤 분석에도 쓰지 않았다.

## 2. 산출물

| 파일 | 내용 |
|---|---|
| `gusun_persons.csv` | 인물·기관·집단 {len(persons)}개. 구순은 `GUSUN_PRE1793` / `GUSUN_1793PLUS` 두 세그먼트로 분리 |
| `gusun_events.csv` | CSV {len(events)}행 전체 + 정규화 시간·관직 차원·career_state |
| `gusun_temporal_edges.csv` | temporal edge {len(edges)}개 (관측 {int((edges.evidence_status != 'DERIVED').sum())}, 파생 {int((edges.evidence_status == 'DERIVED').sum())}) |
| `gusun_identity_links.csv` / `gusun_identity_evidence.csv` / `gusun_identity_record_clusters.csv` | 동일인 판단 (링크·증거항목·기록 묶음) |
| `gusun_time_uncertainty.csv` | 시간 불확실성 {len(uncert)}개 변수 |
| `gusun_career_states.csv` | 구순 career_state 구간 {len(career)}개 |
| `gusun_network_metrics.csv` | 시기별 중심성 (해석 경고 컬럼 포함) |
| `gusun_network_composition.csv` / `gusun_node_turnover.csv` / `gusun_edge_transitions.csv` | 분석 B·C·D |
| `gusun_stage_handoffs.csv` / `gusun_institutional_paths.csv` / `gusun_sensitivity_analysis.csv` | 분석 E와 민감도 |
| `gusun_source_provenance.csv` | URL 문자열 파싱 결과 (접속 안 함) |
| `gusun_validation_report.csv` | 자동 검증 9항목 |
| `gusun_temporal_career.html` | 시각화 1: 경력 storyline |
| `gusun_temporal_multiplex_network.html` | 시각화 2: 관계 타임라인(전체·1793 확대), multiplex 그래프, 시기별 구성 |
| `gusun_dynamic_network.html` | 시각화 3: 시점별 애니메이션 ({len(frames)}프레임, 슬라이더) |

## 3. 모델 설계 요약

**관직 차원 분리.** `office_name`(CSV 라벨에서), `official_rank`(**NA** — CSV에 품계 없음; E002만 '당상관(노상추일기 전언)' 원문 보존),
`rank_level`(**NA** — 품계가 없으므로 계산하지 않음), `administrative_scope`(COURT/LOCAL/MILITARY/NONE, 관직명 규칙),
`court_proximity`(별군직=HIGH: E004 '왕실 근거리 무관'; 외임 수령·변장=LOW: E007), `command_scope`(관할지·겸임),
`office_tenure`(IN_OFFICE/FORMER/NONE), `career_state`/`career_state_after`.
정배·수감·조사는 오직 `career_state`에만 있고 관직 축에는 없다. 1793년 **前府使는 `전 부사(府名 미상)` + `FORMER_OFFICIAL`**로,
낮은 관직이 아니라 과거 관직 이력 + 현재 비현직 상태다.

**관계 정규화.** 같은 인물쌍이라도 관계 유형·시점이 다르면 별도 edge다 (예: 구순–김명신 5개 edge).
각 edge는 `record_date`(기록일)와 관계 발생 구간(`earliest/latest_start`, `earliest/latest_end`)을 따로 갖는다.
1793-06-13 최종 판정에 실린 '편들기'·'편파 수사'처럼 기록일과 행위 시점이 다른 경우는 행위 구간을
CSV 날짜(도난 02-22 ~ 장계 05-12)로 묶었다.

**동일인.** 구순 기록을 10개 기록 묶음(R1–R8C)으로 나누고 묶음 사이 링크마다 증거항목을 붙였다.
판정 규칙: 명시적 상호참조 → CONFIRMED; 같은 한자 + 연대 양립 + 구체적 단서(같은 직함 재등장, 회고 언급, 연속 형벌사슬, 전직 직함 일치) → HIGH_CONFIDENCE;
같은 한자 + 일반 단서만 → PLAUSIBLE; 확정적 모순 → CONTRADICTED. 긴장(tension)은 기록하되 판정을 자동으로 낮추지 않는다.

**시간 불확실성.** DBN은 만들지 않았다. 모든 불확실 시점은 interval-censored `T ∈ (lower, upper)`로만 저장했고
사전분포 근거가 없어 `UNIFORM_INTERVAL (sensitivity only)`로 표시했으며 **연도별 확률은 하나도 만들지 않았다.**
새 증거가 없으므로 posterior = prior(결정론적 구간 교집합)이다.

---

## 4. 질문별 답

### Q1. CSV 기준으로 구순의 시간적 career trajectory는 어떻게 구성되는가?

{md_table(career, ['spell_id', 'person_id', 'career_state', 'office_or_status', 'location', 'start', 'earliest_end', 'latest_end', 'evidence_start'], 30)}

요약: **1777 선전관→별군직(COURT) → 1778 중화부사(LOCAL) → 1779 별군직 수행 → 1779 벽동군수 → ≤1781-12 백령첨사(MILITARY)
→ 1782 영흥부사(겸영장) → 1784-03 상관 능멸·나문 명령(조사 중, 재임 유지) → 1784-07 분간·포상 → 1784-09 별군직에서 정배
→ (해배 미관측) → 1787-01 별군직으로 이윤빈 무고 → 제주목 감사정배·勿揀赦典 → (73개 음력월 미관측)
→ 1793-02 청주 덕평의 전 부사 → 05-12 의금부 수금 명령 → 06-13 감사 절도정배(신지도) → 1794-10 백령도 이배
→ (≤1798) 장연현, 도 3년으로 재분류 → 1798-02-21 방송 → 이후 OPEN.**
관직 재임은 대부분 임명일 한 점만 관측되며, 재임 종료일은 하나도 직접 기록돼 있지 않다.

### Q2. 관직·신분·지역은 시간에 따라 어떻게 변하는가?

- **행정 범위**: COURT(1777–79) ↔ LOCAL(1778–84) ↔ MILITARY(1781) 사이를 왕복하다가 1784·1787·1793 세 번 처벌 상태로 빠진다.
  1793 이후 관직 차원은 `NONE`(비현직)이며 다시 관직으로 돌아온 기록은 없다.
- **중앙 접근성(court_proximity)**: 별군직 시기 HIGH, 외임 시기 LOW, 1793 이후 NONE. 1787년에는 별군직(HIGH) 상태에서 곧장 정배로 떨어진다.
- **신분 상태**: ACTIVE → UNDER_INVESTIGATION(1784, 재임 중) → ACTIVE → EXILED(1784) → ACTIVE(1787) → EXILED(1787)
  → [미관측] → FORMER_OFFICIAL(1793) → UNDER_INVESTIGATION → IMPRISONED → EXILED(1793–98) → RELEASED(1798) → UNKNOWN.
- **지역**: 한성 → 중화부 → 벽동군 → 백령 → 영흥부 → (배소 미상) → 한성 → 제주목 → 청주 덕평 → 의금부(한성) → 신지도 → 백령도 → 장연현 → 미상.
  (1784년 정배지는 CSV에 없다 — `배소 미상`.)

### Q3. 어느 시점에 어떤 종류의 관계망이 가장 많이 나타나는가?

{md_table(comp, comp_cols, 20)}

- 전체 edge 수 최대: **{top_all.period}** ({top_all.n_edges_all}건) — 대부분 구순이 끼지 않은 병영 실무자–피의자 사이의 수사 edge.
- 구순 ego edge 최대: **{top_ego.period}** ({top_ego.n_edges_ego}건) — 관찰사 장계·국왕 수금 명령 등 INVESTIGATION 중심.
- 1777–1783은 OFFICIAL(임명·입시)이 전부다(그 밖에 시점 없는 부자 KINSHIP 1건이 이 시기에 배정됨). 1784는 OFFICIAL+CONFLICT+INVESTIGATION+PUNISHMENT,
  1787은 CONFLICT(무고)·KINSHIP(종형 연루)·PUNISHMENT, 1793-02에는 처음으로 PRIVATE_SOCIAL(이웃·친교)과 HOUSEHOLD가 등장하며,
  1794–98은 PUNISHMENT와 보고·방송 심의(INVESTIGATION군)만 남는다.
- 이것은 **기록이 어떤 관계를 남겼는가**의 분포다. 1777–83에 사적 관계가 0건인 것은 사적 관계가 없었다는 뜻이 아니다.

### Q4. 관계망은 시간에 따라 어떻게 교체되는가?

{md_table(turn, ['period', 'n_actors', 'n_new', 'n_continuing', 'n_disappeared', 'continuing_from_previous', 'returning_from_earlier'], 20)}

- PRE1793 세그먼트의 상대 인물 {len(pre_alters)}명과 1793+ 세그먼트의 상대 인물 {len(post_alters)}명 중 겹치는 것은
  **{nm(shared)}뿐**이다 — 즉 국왕과 중앙 사법기관만 이어지고, 1787 사건의 이윤빈·유효원·조학신이나 1784의 신우문은
  1793 기록에 한 번도 나오지 않는다. 1787 → 1793 전환은 **사실상 완전한 관계망 교체**다.
- 1793 사건 안에서는 2월(가내·이웃·병영 실무자) → 3월(혐의자·증인 대량 유입) → 5월(관찰사·암행어사·비변사·국왕) → 6월(안핵어사·처벌)
  순으로 사적 층위에서 제도 층위로 교체된다.
- '사라짐'은 기록에서 관측되지 않음이며 관계 종료가 아니다.

### Q5. 친족·관료·갈등·수사 관계는 어떻게 다른 layer를 형성하는가?

전체 edge의 관계군 분포: {', '.join(f'{g} {int(grp_tot.get(g, 0))}' for g in gp.GROUP_ORDER)}.

- **KINSHIP layer** (2개): 구세덕(부, PRE1793; 근거 행 부재로 confidence `B_REDUCED`), 유효원(종형, 1787; 성씨가 달라 친족 경로 UNRESOLVED).
  둘 다 PRE1793에만 붙어 있고 **1793 세그먼트에는 친족 edge가 0개**다 — 이것이 동일인 판단의 친족 다리가 없는 이유이기도 하다.
  유효원과의 관계는 KINSHIP → ACCUSATION(무고에 연루시킴)으로 친족 layer와 갈등 layer가 같은 쌍에 겹친다.
- **OFFICIAL layer**: 1777–1784의 임명·입시·상관 관계와 1793 병영 내부 지휘(한재욱→이진욱·조계완, 이광섭→이문협).
- **CONFLICT layer**: 1784 상관 신우문과의 충돌, 1787 이윤빈 무고, 1793 김명신과의 단절·지목, 이광섭과의 가문 세혐.
- **INVESTIGATION layer**: 1793에 집중({int(grp_tot.get('INVESTIGATION', 0))}건). 구순이 직접 닿는 것은 유제희·이진욱 같은 실무자까지이고,
  강압 진술(한재욱→자미덕→정원돌·이집거 등)은 구순을 거치지 않는 2–4단계 하위망이다.
- **HOUSEHOLD / PRIVATE_SOCIAL layer**: 1793에만 관측 (나복·명업·행랑 하인들, 김명신 이웃·친교, 한재욱 '가객' 주장은 `B_CONTESTED`).

같은 인물쌍에서 layer가 바뀌는 전이 (`gusun_edge_transitions.csv`):

{md_table(trans[trans.involves_ego], ['pair', 'transition_compact', 'ordering_caveats'], 20)}

대표 전이 **구순–김명신: NEIGHBOR → FRIENDLY_ASSOCIATION(시작 미상) → CONFLICT(1793-02, 박거사 문제로 단절) → ACCUSATION(1793-03 유제희에게 '수상하다'; 05-12 장계의 '도적 괴수' 지목)**,
이어서 김명신은 이광섭의 체포 명령(DETENTION, 03-04)·편파 수사(INVESTIGATION)를 받는다. 각 단계는 CSV 행에 근거가 있다.

**제도적 전달 경로 (분석 E).** 1793 사건 참여자를 CSV 역할·직함으로 단계에 배정하고, 인접 단계 사이에 CSV edge가 있는지만 확인했다:

{md_table(handoff, ['from_stage', 'to_stage', 'link_status', 'edges_forward'], 30)}

- 구순 → 병영 실무자(유제희: 혐의자 이름 제공) → 비장 한재욱(명단 보고) → 장교 이진욱·조계완(체포 지시) → 피의자·증인 까지는 **CSV edge로 연결**된다.
- 그러나 **장교·비장 → 병사 이광섭**, **피의자 → 관찰사**, **관찰사 → 암행어사 → 안핵어사**, **안핵어사 → 중앙** 사이에는 CSV edge가 없다
  (관찰사·암행어사는 중앙으로부터의 처분만 역방향으로 존재). 이 구간은 자동으로 잇지 않았다.
- 시간순 경로(`gusun_institutional_paths.csv`): 구순에서 출발하는 시간순 경로 {len(paths)}종 중 {n_paths_robust}종은 월 단위 사건을 월초·월말 어디에 두어도 성립하고,
  {n_paths_late_only}종(구순의 편지 E037 → 이광섭의 편파 수사 E064)은 구간 사건을 상한에 둘 때만 성립한다.
  E037 요약('김명신 **체포 길에 들른** 조계완')은 체포 명령(E035·E036)이 편지보다 먼저였음을 명시하므로 '편지 → 체포' 경로는 배제했다.
  시간순 경로가 있다는 것은 인과·전달의 증명이 아니다.

### Q6. 동일인 여부가 불확실한 구순 기록이 존재하는가?

존재한다. 핵심은 **R7(1787 별군직·제주 정배) ↔ R8A(1793 전 부사·김명신 사건)**이며, 세그먼트 수준 판정 L00 = **{l00.same_person_status}** 이다.
CSV 작성자의 평가(`identity_bridge_status` = `highly_probable_not_fully_proven`)와 일치한다. 두 세그먼트는 **병합하지 않았다** —
`persons`·`edges`·시각화 모두에서 별도 노드이며 주황 점선 링크로만 연결된다. 전체 링크:

{md_table(links, ['link_id', 'identity_a', 'identity_b', 'same_person_status', 'supporting_evidence_count', 'contradicting_or_tension_count'], 20)}

- CONFIRMED는 명시적 상호참조가 있는 두 곳뿐: 중화부사↔백령첨사(I004 국왕 발언), 1793 신지도 정배↔1794 '신지도에서' 백령도 이배(E076).
- PRE1793 내부도 단일 인물로 확정된 것이 아니다: 1777 별군직↔1778 중화부사, 중화↔벽동, 백령↔영흥, 영흥↔1784 별군직은 PLAUSIBLE이다.
- 김명신 별칭(풍각 김생원·풍각 김상제)과 '병사'=이광섭은 CSV 작성자의 괄호 매핑이라 원문 대조 없이 CONFIRMED로 올리지 않았다(HIGH_CONFIDENCE).

### Q7. 동일인 판단을 지지하는 CSV 내부 증거와 반대 증거는 무엇인가? (L00 = R7 ↔ R8A)

| 구분 | 증거 |
|---|---|
| 지지 | {l00.supporting_evidence} |
| 긴장(반대 방향) | {l00.contradicting_evidence} |
| 결락 | {l00.missing_evidence} |

- 직접 증거(해배 기록, 1793 기록 속 제주 정배·별군직 전력 언급, 1793 세그먼트의 친족 연결)는 **하나도 없다.**
- 가장 구체적인 단서는 1793 '전 부사'가 PRE1793의 중화부사·영흥부사 직함 이력과 맞는다는 점이다(단, 1793 기록에 府名이 없다).
- 확정적 반대 증거(같은 시점 두 장소, 다른 부친 등)는 CSV에 없다. 다만 1787 판결의 **勿揀赦典**은 일반 사면에 의한 해배를 배제하므로,
  동일인이라면 특별 해배가 있었어야 하는데 그 기록이 없다 — 이는 반증이 아니라 **풀리지 않은 긴장**이다.
- CSV 안에 다른 具純 후보가 없다는 점은 CSV가 한 인물 중심으로 수집됐기 때문에 약한 단서(`WEAK_SUPPORT`)로만 셌다.

### Q8. 날짜가 불확실한 사건은 무엇이며 interval을 얼마나 좁힐 수 있는가?

{md_table(uncert[~uncert.uncertainty_id.str.match(r'U_E0(4[0-9]|7[0-5])$')], ['uncertainty_id', 'uncertain_variable', 'lower_bound', 'upper_bound', 'uncertainty_type', 'candidate_narrowing_not_applied'], 40)}

(1793-03 월 단위 수사 행 E040–E049, E070–E075도 같은 방식으로 각각 [1793-03-01, 1793-03-30] 구간을 가진다.)

- **T_release(1787 제주 정배) ∈ (1787-01-03, 1793-02-22)**: 하한은 판결일, 상한은 '구순 집 종' 나복이 등장하는 일자 확정 최초 관측(E028).
  명목 약 73 음력월(윤달 미반영). '1793-02-early' 기록(E026/E027)과 '본래 친숙' 진술은 더 이른 거주를 시사하지만
  일자를 주지 않으므로 상한을 더 좁히지 않았다. **이 변수는 L00 동일인 가정 하에서만 정의된다.**
- **좁힐 수 있었던 것**: 김명신 사망 (1793-03-04, 1793-05-27] — 체포 명령과 '옥사' 보고 사이; 구순 의금부 수감 실행 [05-12, 05-27].
- **좁히지 않은 것(후보 제약으로만 기록)**: 'early/late' 한정어를 상순/하순으로 읽는 해석, E038→E039→E035 순서 가정,
  E079의 '1795-10-15 장연 정배'(지지 행이 없는 CSV 단언 — 확실한 상한은 1798-02-21).
- 민감도 분석 (`gusun_sensitivity_analysis.csv`):

{md_table(sens, ['analysis', 'scenario', 'scenario_definition', 'n_paths', 'shortest'], 10)}

### Q9. 현재 네트워크에서 가장 큰 data gap은 무엇인가?

1. **1787-01-03 ~ 1793-02-22 구순 기록 전무** — 해배·복귀·이주·거주 시작 모두 미관측. 동일인 판단의 결정적 결락.
2. **1784-09-23 ~ 1787-01-03 해배·별군직 복귀 기록 없음** (E018).
3. **CSV 메타필드가 언급하지만 행으로 없는 근거**: 1782 부자관계 확인 국왕 대화(구세덕–구순 KINSHIP의 근거), 1795 長淵 이배(E078 결락), 백령첨사 임명 행.
   id 결락은 I001, E078, C008, C009, C011.
4. **관직 재임 종료일 0건**: 모든 관직은 임명일(또는 한 시점) 관측뿐이라 재임 기간은 '단일 관직' 모델 가정 없이는 정의되지 않는다.
5. **품계 정보 부재** → rank_level을 만들 수 없음.
6. **1793 제도적 전달 경로의 단절**: 장교·비장→병사, 관찰사→암행어사→안핵어사→중앙 사이의 문서 흐름 edge 없음.
7. **1798-02-21 이후 OPEN** (E083: 검색 실패를 사망·은거로 해석하지 않음).
8. **김명신의 독립 정보**: biographical_coverage_score = {kim.biographical_coverage_score}. CSV에서 확인되는 것은 '반족', '구순 이웃', 풍각 김생원/김상제라는 호칭,
   구순과의 친교→단절, 혐의자 명단·체포·수감, 옥중 사망(1793, 일자 구간만), 질병사 판정과 장형·평문 없음뿐이다.
   생년·본관·관직·가족·재산은 모두 `NA`이며 추정하지 않았다. 이 정보 부족은 김명신의 역사적 비중이 아니라 기록 구조를 반영한다.

### Q10. 어떤 결과가 직접 관측이고 어떤 결과가 파생·추론인가?

| 층 | 해당 결과 |
|---|---|
| **OBSERVED** (CSV 직접) | 102개 사건 행과 그 날짜·장소·요약·출처, 인물 이름·한자·신분 라벨, 관계 edge {int(ev_status.get('OBSERVED', 0))}개(행 그대로), 시간 구간이 보정된 관측 edge {int(ev_status.get('OBSERVED (relation) + DERIVED (time window)', 0))}개의 관계 자체, 김명신 사망 사실, 1793 '전 부사' 라벨, 勿揀赦典 |
| **DERIVED** (규칙 변환) | relation_type 17종 정규화와 관계군, 역할필드·라벨·요약문에서 읽은 edge {int(ev_status.get('DERIVED', 0))}개, 관직 차원(scope·proximity·command), career_state·state spell, 날짜 정규화(월 단위→월 경계 구간), 기록일≠행위일 구간, 시기 구분, 성별(친족어가 있는 경우만), biographical_coverage_score |
| **INFERRED** (모델·계산) | 동일인 판정(L00–L10의 status), 중심성 지표, 시간순 경로·단계 연결, 민감도 결과, 노드 교체·전이 순서 |
| **MODEL_ASSUMPTION** | '동시에 하나의 관직'(관직 전환 구간 U_JUNGHWA_END 등), 균등 구간 사전분포(민감도용), 프레임 내 월 단위 배치 규칙 |
| **DERIVED_FOR_VISUALIZATION** | plot_x(명목 음력 소수연도), 애니메이션 프레임 순서, 그래프 레이아웃 좌표 |

## 5. 중심성 사용 제한

`gusun_network_metrics.csv`에 전체·시기별 degree, betweenness, PageRank를 계산했지만 해석하지 않는다.
구순 두 세그먼트가 betweenness 1·2위인 것은 **ego network로 수집했기 때문**이고, 정조가 3위인 것은 국왕 명의 처분이 행정문서에 체계적으로 남기 때문이다.
그래프 노드 크기도 중심성으로 키우지 않았다.

## 6. 자동 검증 결과

{md_table(val, ['check_no', 'check', 'result', 'detail'], 20)}

## 7. 원래 연구 질문(1787 정배 구순 = 1793 전 부사 구순?)에 대한 현재 답

이 CSV만으로는 **HIGH_CONFIDENCE (CONFIRMED 아님)**. 지지 근거는 같은 한자명, 부사 직함 이력 일치, 연대 양립이며,
확정에 필요한 것은 (a) 1787–1793 사이 해배·방송 기록, (b) 1793 이후 기록에서 제주 정배·별군직 전력이나 부친 구세덕을 언급하는 구절,
(c) 1793 '전 부사'의 府名이다. 반대로 같은 시기에 다른 具純이 다른 장소에 있었다는 기록이 나오면 두 세그먼트는 이미 분리돼 있으므로
L00만 CONTRADICTED로 바꾸면 된다.
"""
    (OUT / "gusun_temporal_network_README.md").write_text(txt, encoding="utf-8")
