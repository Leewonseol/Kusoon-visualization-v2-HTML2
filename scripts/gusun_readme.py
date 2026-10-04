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

{md_table(links, ['link_id', 'identity_a', 'identity_b', 'same_person_status', 'supporting_evidence_count', 'contradicting_evidence_count', 'tension_evidence_count', 'missing_evidence_count'], 20)}

- CONFIRMED는 명시적 상호참조가 있는 두 곳뿐: 중화부사↔백령첨사(I004 국왕 발언), 1793 신지도 정배↔1794 '신지도에서' 백령도 이배(E076).
- PRE1793 내부도 단일 인물로 확정된 것이 아니다: 1777 별군직↔1778 중화부사, 중화↔벽동, 백령↔영흥, 영흥↔1784 별군직은 PLAUSIBLE이다.
- 김명신 별칭(풍각 김생원·풍각 김상제)과 '병사'=이광섭은 CSV 작성자의 괄호 매핑이라 원문 대조 없이 CONFIRMED로 올리지 않았다(HIGH_CONFIDENCE).

### Q7. 동일인 판단을 지지하는 CSV 내부 증거와 반대 증거는 무엇인가? (L00 = R7 ↔ R8A)

| 구분 | 증거 |
|---|---|
| 지지 | {l00.supporting_evidence} |
| 반대 증거(contradicting) | {l00.contradicting_evidence} |
| 긴장(tension, 반증 아님) | {l00.tension_evidence} |
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
    if "rank" in res:
        txt += rank_section(res)
    if "policy" in res:
        txt += context_section(res)
    (OUT / "gusun_temporal_network_README.md").write_text(txt, encoding="utf-8")


def rank_section(res: dict) -> str:
    rk = res["rank"]
    J, audit, val, lk = rk["joined"], rk["audit"], rk["rank_val"], rk["lookup"]
    g = J[J.focal_person_id.isin(gp.EGO)]
    gm = g[g.office_lookup_match_status.isin(["EXACT", "NORMALIZED"])]
    summ = (gm.groupby(["focal_raw_office_status", "normalized_office_title", "statutory_rank", "rank_numeric",
                        "rank_fixedness", "rank_lane", "administrative_scope", "office_lookup_verification_status"],
                       dropna=False)
              .agg(n_rows=("event_id", "size"), first=("date_lunar", "min")).reset_index()
              .sort_values("first"))
    summ["former_statutory_rank"] = summ.focal_raw_office_status.map(
        lk.set_index("raw_office_status").former_statutory_rank)
    counts = audit[audit.match_status != "LOOKUP_UNUSED"].groupby("match_status").agg(
        distinct_values=("raw_office_status", "size"), occurrences=("n_occurrences", "sum")).reset_index()
    unm = audit[audit.match_status == "UNMATCHED"]
    cand = unm[unm.unmatched_kind == "POSSIBLE_OFFICE_NOT_IN_LOOKUP"]
    n_lk_used = int((audit.match_status.isin(["EXACT", "NORMALIZED"])).sum())
    cmp_ = rk["scope_cmp"]
    return f"""

---

## 8. 관직 법정 품계 lookup 결합 (`office_rank_lookup.csv`)

> **lookup의 품계는 관직 자체의 법정·제도적 품계다. 구순 개인의 실제 품계(personal_rank)가 아니다.**
> CSV에서 개인 품계로 읽히는 것은 E002의 '당상관'(노상추일기 전언) 하나뿐이며 `personal_rank`에 따로 보존했다.
> `rank_numeric`(정3품=3.0, 종3품=3.5, 정4품=4.0, 종4품=4.5 …)은 **시각화 Y축 정렬용**이고 권력 점수·사회적 영향력·개인 품계가 아니다.

### 8.1 입력과 조인 규칙

- lookup: `{rk['lookup_path'].relative_to(gp.ROOT)}` ({len(lk)}행 × {lk.shape[1] - 1}열). 원본 두 CSV는 수정하지 않았다.
  lookup의 `source_url_1/2`(한국민족문화대백과사전·실록·승정원일기·우리역사넷)는 메타데이터로만 보존했고 접속하지 않았다.
  lookup의 품계 판정·`verification_status`는 lookup 작성자의 판단이며, 이 작업에서 독립적으로 재검증하지 않았다.
- 조인 키: master의 `subject_office_status`와 `object_office_status`를 각각 lookup의 `raw_office_status`에 **LEFT JOIN**한다.
  master에는 직함 전용 필드가 없고 이 두 필드가 직함·신분·역할을 담고 있으며, lookup 키 {len(lk)}개가 전부 이 두 필드의 값과 문자 단위로 같다.
- 매칭 순서: **EXACT**(문자열 완전 일치) → **NORMALIZED**(유니코드 NFKC + 공백 정리만, 정규화 후에도 키가 유일할 때) → **UNMATCHED**.
  부분 문자열·유사도 기반 fuzzy 매칭은 구현하지 않았다.
- 요청된 파생 컬럼(`normalized_office_title`, `office_title_hanja`, `record_type`, `administrative_scope`, `statutory_rank`,
  `rank_numeric`, `rank_fixedness`, `rank_visualizable`, `former_statutory_rank`, `office_lookup_match_status`,
  `office_lookup_verification_status`)은 각 행의 **focal 인물**(구순이 있으면 구순 쪽, 없으면 subject)을 기준으로 채웠다.
  subject·object 양쪽의 결과는 `subject_*`, `object_*` 접두사 컬럼으로 모두 남겼다.
- 앞 단계의 관직명 규칙 결과는 `rule_scope_v1`로 남겼다. lookup의 scope와 충돌하는 곳은 없고, lookup 쪽이 더 세분된다
  (예: 별군직 COURT → COURT_MILITARY, 영흥부사·겸영장 LOCAL → LOCAL_MILITARY, 백령첨사 MILITARY → MILITARY_LOCAL).

### 8.2 매칭 결과

{md_table(counts, ['match_status', 'distinct_values', 'occurrences'], 10)}

- lookup {len(lk)}행 중 {n_lk_used}행이 사용됐다 (미사용 {len(lk) - n_lk_used}행).
- NORMALIZED가 0건인 것은 정상이다: 모든 직함이 원문 그대로 일치했다.
- UNMATCHED {len(unm)}개 고유값은 대부분 관직이 아니다 (국왕·정부 같은 통치자·기관, 민간인·가내, 죄인·정배 같은 처벌 상태, 정책·사건 노드).
  **직함처럼 보이지만 lookup에 키가 없는 값** {len(cand)}개는 결합하지 않고 lookup 추가 후보로만 표시했다:
  {', '.join(f"'{v}'" for v in cand.raw_office_status)}. 예를 들어 '체포 장교'는 lookup의 '청주진 장교'와 단어가 겹치지만
  같은 직함이라고 단정할 근거가 없어 자동 결합하지 않았다.
- 전체 목록: `gusun_office_lookup_join_audit.csv`.

### 8.3 구순 직함별 결합 결과

{md_table(summ, ['first', 'focal_raw_office_status', 'normalized_office_title', 'statutory_rank', 'rank_numeric', 'rank_fixedness', 'rank_lane', 'former_statutory_rank', 'office_lookup_verification_status', 'n_rows'], 30)}

- **고정 품계(FIXED)**: 중화부사→도호부사 종3품, 벽동군수→군수 종4품, 백령첨사→첨사(첨절제사) 종3품(DERIVED_CONFIRMED),
  영흥부사·영흥부사·겸영장→대도호부사 정3품. 이 관직들만 수치축에 들어간다.
- **가변(VARIABLE)**: 선전관, 별군직, 선전관→별군직, 선전관/별군직 계열은 `rank_numeric`이 비어 있고
  `COURT_MILITARY_VARIABLE` lane에 놓인다. 구순이 별군직일 때의 개인 품계는 이 lookup으로 정할 수 없다.
- **전직(FORMER_OFFICE)**: 1793년 '전 부사', '전 부사·민간 거주', '전 부사·청주 덕평 거주'는 `career_state=FORMER_OFFICIAL`,
  현재 `rank_numeric` = 빈 값, `former_statutory_rank` = '정3품 또는 종3품(부의 종류에 따라 다름)'. 1793 기록에 府名이 없어서
  어느 쪽인지 정할 수 없다 — 이 미확정성은 동일인 판단(L08의 FORMER_OFFICE_TITLE_MATCH)에도 그대로 남는다.
  같은 규칙으로 이광섭('전 충청도 병마절도사', 종2품)과 이문협('전 청주 영장', 정3품)도 현재 품계 없이 전직 품계만 보존했다.
- **처벌·조사 상태**(죄인, 정배, 의금부 피수사자 등)는 lookup에 없고 관직이 아니므로 UNMATCHED로 남고, `career_state` band로만 그린다.
- 구순 경력선 해석상 주의: 1778 중화부사(종3품) → 1779 벽동군수(종4품) → 1781 백령첨사(종3품) → 1782 영흥부사(정3품)의
  위아래 움직임은 **관직 자체의 법정 품계 변화**이고, 구순의 개인 품계가 오르내렸다는 증거가 아니다.

### 8.4 자동 검증 (`gusun_office_rank_validation.csv`)

{md_table(val, ['check_no', 'check', 'result', 'detail'], 10)}

### 8.5 산출물

| 파일 | 내용 |
|---|---|
| `gusun_temporal_network_with_office_rank.csv` | master {len(J)}행 전체 + lookup 파생 컬럼 (행 수 불변) |
| `gusun_office_lookup_join_audit.csv` | 고유 직함 값별 매칭 상태·근거·조치 |
| `gusun_office_rank_validation.csv` | 위 7개 검사 |
| `gusun_temporal_career_with_rank.html` | ① 고정 품계 수치축 ② 가변 직함 category lane ③ career_state band. 다른 인물의 직함은 범례 클릭으로 표시 |
| `intermediate/09_office_scope_rule_vs_lookup.csv` | 앞 단계 규칙 scope와 lookup scope 비교 |

기존 산출물(`gusun_temporal_career.html` 등)은 그대로 보존했다.
"""


KEY_EVENTS = [("E001", "1777 별군직 차하"), ("E003", "1778 중화부사 임명"), ("E006", "1782 영흥부사 임명"),
              ("E011", "1784-03 나문 명령"), ("E017", "1784-09 정배"), ("E023", "1787-01 이윤빈 무고 → 제주 정배"),
              ("E029", "1793-02-22 도난 사건(사건 개시)"), ("E055", "1793-05 의금부 수금 명령"),
              ("E066", "1793-06 감사 절도정배"), ("E076", "1794-10 백령도 이배"), ("E082", "1798-02 방송")]


def context_section(res: dict) -> str:
    pc, rk = res["policy"], res["rank"]
    pn, win, val, audit, cross = pc["norm"], pc["windows"], pc["val"], pc["audit"], pc["cross"]
    links = res["links"].set_index("link_id")
    l00 = links.loc["L00"]
    P = pn.set_index("policy_event_id")

    def titles(ids, high_bold=True):
        out = []
        for i in ids:
            t = f"{P.loc[i, 'policy_title']}({P.loc[i, 'date_lunar']})"
            out.append(f"**{t}**" if high_bold and P.loc[i, "project_relevance"] == "HIGH" else t)
        return ", ".join(out) or "—"

    rows = []
    for eid, lab in KEY_EVENTS:
        w = win[win.gusun_event_id == eid]
        rows.append(dict(event=f"{eid} {lab}",
                         same_year=titles(w[w.window_class == "SAME_YEAR"].policy_event_id),
                         previous_year=titles(w[w.window_class == "PREVIOUS_YEAR"].policy_event_id),
                         next_year=titles(w[w.window_class == "NEXT_YEAR"].policy_event_id),
                         ongoing_started_earlier=titles(w[w.window_class == "ONGOING_CONTEXT_STARTED_EARLIER"]
                                                        .policy_event_id)))
    key_tbl = pd.DataFrame(rows)
    between = pn[(pn.sort_key.astype(int) > 17870103) & (pn.sort_key.astype(int) < 17930222)]
    ctx87 = set(win[(win.gusun_event_id == "E023") & (win.window_class != "NEXT_YEAR")].policy_event_id)
    ctx93 = set(win[(win.gusun_event_id == "E029") & (win.window_class != "NEXT_YEAR")].policy_event_id)
    ev = res["events"]
    gobs_8588 = ev[ev.person_id.isin(gp.EGO) & (ev.phase != "gap") &
                   ev.record_date_raw.str[:4].astype(int).between(1785, 1792)].event_id.tolist()
    persist = pn[pn.persistence_class.str.startswith("PERSISTENT")]
    vs = val.result.value_counts().to_dict()
    handoff = res["handoff"]
    explicit = handoff[handoff.link_status == "EXPLICIT_IN_CSV"]
    missing = handoff[handoff.link_status != "EXPLICIT_IN_CSV"]
    new93 = pn[pn.year == "1793"]
    ongoing93 = pn[(pn.year.astype(int) < 1793) & pn.persistence_class.str.startswith("PERSISTENT")]

    return f"""

---

## 9. 정조대 정책 context layer와 통합 대시보드 (`jeongjo_policy_timeline.csv`)

> **세 층은 독립된 데이터 layer다.** ① 개인: 구순의 관직·신분·처벌·사건(master CSV) ② 관직의 제도적 위계(office_rank_lookup — 관직 자체의 법정 품계)
> ③ 국가: 정조대 정책(policy CSV). 같은 시간축 위에 놓아 **시간적 동시성**을 보여줄 뿐, 정책이 구순 사건을 일으켰다는 인과관계는 어디에도 만들지 않았다.
> 정책은 네트워크 노드가 아니고, 정책–인물 edge는 0개다.

### 9.1 입력 점검 (`gusun_input_audit.csv`)

{md_table(audit, ['file', 'metric', 'value'], 40)}

- 원본 세 CSV는 `input/`에 복사만 했고 수정하지 않았다.
- master CSV의 맥락 행(C001–C017)과 정책 CSV는 **같은 음력 날짜**로만 대응시켰다 (`gusun_master_context_vs_policy_crosswalk.csv`):
  같은 날짜 {int((cross.match_basis == 'SAME_DATE_LUNAR').sum())}건 / 대응 없음 {int((cross.match_basis != 'SAME_DATE_LUNAR').sum())}건.
  같은 날짜라도 같은 정책이라는 뜻은 아니다 (예: C006 『병학통』과 JP013 『대전통편』은 둘 다 1785-09-11). 두 행을 병합하지 않았고, 대시보드의 정책 layer는 정책 CSV만 쓴다.

### 9.2 시간축 규칙

- 모든 층이 하나의 **명목 음력 시간축**을 공유한다. 정책 CSV는 서기 연도 + 조선 음력 월·일이고, master CSV도 음력이다. **양력으로 바꾸지 않았다.**
- 정책은 `sort_key`(YYYYMMDD)로 정렬한다. `year/month/day/date_lunar/sort_key/date_precision/calendar_basis`는 원문 그대로 보존했다.
  `calendar_basis=JOSEON_REGNAL_DATE` 2건(JP023, JP024)도 변환하지 않고 같은 축에 둔다.
- 날짜 정밀도는 `YYYY` / `YYYY-MM` / `YYYY-MM-DD` 그대로 보존(`date_as_recorded`). 연도·월만 있는 기록에 1일·15일을 만들지 않았다.
- 그림 좌표는 1년=360일 명목 소수연도 `derived_plot_x`이며 `DERIVED_FOR_VISUALIZATION`으로 표시했다. 이 좌표로 실제 일수 차이를 계산하지 않는다.
- 동시성 창은 **연도 필드** 기준(같은 해 / 전 해 / 다음 해)이다. ±365일 같은 일수 창은 양력 일수 계산처럼 오해될 수 있어 쓰지 않았다.
  여기에 '그 이전에 시작했고 CSV에 종료 기록이 없는 지속 제도'(ONGOING)를 따로 붙였다. 결과: `gusun_policy_context_windows.csv` ({len(win)}쌍, 모두 `CONTEMPORANEITY_ONLY`).

### 9.3 정책 정규화 (`gusun_policy_timeline_normalized.csv`)

- milestone {len(pn)}개를 하나씩 유지했다. 같은 `policy_episode_id`는 선으로만 잇는다
  (예: JANGYONG 1785 장용위 → 1788 장용영 확대 → 1793 화성 유수·장용외사; HWASEONG 1789 현륭원 이장 → 1794 축성 하명 → 1796 완성·성역 종료·낙성연; CHOGYE 1781 선발 → 강제절목 → 추가 절목).
- **POINT_EVENT vs PERSISTENT_INSTITUTIONAL_CONTEXT**: event_kind로 분류했다(규칙, DERIVED). 지속 제도 {len(persist)}개:
  {titles(persist.index.map(lambda i: persist.loc[i, 'policy_event_id']), high_bold=False)}.
  CSV에 종료일이 없으므로 모두 `context_end_date = OPEN`이며, 그림에서는 오른쪽 축 끝까지 이어지는 점선 + ▷로 그렸다(축 끝은 종료일이 아니다).
- 시작·종료가 둘 다 CSV milestone인 구간은 화성 축성 사업 하나(1794-01-15 하명 → 1796-09-10 성역 종료)뿐이며 별도 막대로 표시했다.
- `project_relevance`: HIGH {int((pn.project_relevance == 'HIGH').sum())}건(흠휼전칙, 대전통편 총재 임명·반포, 증수무원록), MEDIUM {int((pn.project_relevance == 'MEDIUM').sum())}, LOW {int((pn.project_relevance == 'LOW').sum())}.
  대시보드에서 HIGH는 진하고 크게(제목 라벨 포함), MEDIUM은 중간, LOW는 흐리게 그리며 상단 버튼으로 숨길 수 있다.

### 9.4 시각화

| 파일 | 내용 |
|---|---|
| `gusun_temporal_context_dashboard.html` | 하나의 X축을 공유하는 A(관직 법정 품계 / 가변 lane / career_state band) · B(구순 사건 + 관계군 lane) · C(정책 6개 broad_domain lane) + 오른쪽 **Panel D**(클릭 상세: 구순 사건이면 같은 해·전 해·다음 해·ONGOING 정책 목록; 정책이면 같은 시기 구순 기록). 정책 marker = 기호(event_kind) + 회색 농도(relevance) + lane(domain) + hover |
| `gusun_1793_context_zoom.html` | 1793년 1–12월 확대: career_state, 구순–주변 인물 관계(인물별 행), 1793 신규 정책 milestone {len(new93)}건 vs ONGOING CONTEXT {len(ongoing93)}건(별도 lane) |
| `gusun_temporal_career_with_rank.html`, `gusun_dynamic_network.html` 등 | 기존 산출물 유지 |

정책 marker 색은 일부러 회색 단계만 썼다. 구순 층(관계군·상태 색)과 색이 겹치면 정책을 구순 관계의 일부로 오독할 수 있기 때문이다.

### 9.5 질문별 답

**Q1. 구순의 관직 trajectory는 시간에 따라 어떻게 변하는가?**
1777 선전관→별군직(COURT_MILITARY, 가변 품계) → 1778 중화부사(도호부사, 종3품) → 1779 별군직 수행 → 1779 벽동군수(군수, 종4품)
→ ≤1781-12 백령첨사(첨절제사, 종3품) → 1782–84 영흥부사(대도호부사, 정3품; 1784-04 겸영장) → 1784-09 별군직(가변)에서 정배
→ 1787-01 별군직(가변)에서 제주 정배 → [1787–1793 기록 없음] → 1793 '전 부사'(현직 품계 없음) → 수금·정배 → 1798 방송.
고정 품계 축에서 보이는 종3품→종4품→종3품→정3품의 움직임은 **관직 자체의 법정 품계** 변화이며 구순 개인의 품계 변화가 아니다(§8).

**Q2. 고정 품계 관직과 별군직·선전관 같은 가변 직무는 어떻게 구분되는가?**
lookup의 `rank_fixedness`로 나눈다. FIXED(군수·도호부사·첨사·대도호부사)는 `rank_numeric`이 있어 A① 수치축에 놓이고,
VARIABLE(선전관·별군직·선전관→별군직·선전관/별군직 계열)은 숫자를 만들지 않고 A② `COURT_MILITARY_VARIABLE` lane에 놓인다.
구순 경력에서 가변 직무 관측은 1777, 1778, 1779, 1784-09, 1787-01의 5개 시점이고 고정 품계 관직은 1778–1784 사이에 몰려 있다.
즉 구순은 왕 측근 무관직(가변)과 외임 수령·변장(고정 품계) 사이를 오갔다.

**Q3. 관직 변화와 처벌·유배 상태는 어떻게 구분되는가?**
처벌·조사·전직은 관직이 아니라 `career_state`이며 A③ 띠에만 그린다. 전 부사는 `FORMER_OFFICIAL`, `current_rank_numeric = NA`,
`former_statutory_rank = 정3품 또는 종3품`이고, 정배(EXILED)·수감(IMPRISONED)·조사(UNDER_INVESTIGATION)·방송(RELEASED)도 수치축에 들어가지 않는다.
1784년 3–7월처럼 **재임 중 조사**(영흥부사 + UNDER_INVESTIGATION)는 관직 점과 상태 띠가 동시에 보인다.

**Q4. 구순의 주요 사건 시점에 정조 정부의 주요 정책·제도적 환경은 무엇이었는가?** (굵게 = HIGH)

{md_table(key_tbl, ['event', 'same_year', 'previous_year', 'next_year', 'ongoing_started_earlier'], 20)}

이 표는 **동시성만** 보여준다. 어떤 정책도 구순 사건의 원인으로 연결하지 않았다.

**Q5. 1787년 사건과 1793년 김명신 사건 당시의 정책환경은 어떻게 달랐는가?**
- 1787-01-03(E023) 기준 이미 성립했거나 같은 해·전 해에 있었던 정책: {titles(sorted(ctx87))}.
- 1793-02-22(E029) 기준: {titles(sorted(ctx93))}.
- 두 사건 사이(1787-01-03 ~ 1793-02-22)에 새로 기록된 milestone {len(between)}건: {titles(between.policy_event_id)}.
  법제 쪽에서는 **『증수무원록』 간행·반포 명령(1792-11-20)**이 1793 사건 약 3개월 전에 더해졌고, 군사 쪽에서는 장용영 확대(1788)와
  **화성 유수·장용외사 체계(1793-01-12, 사건 약 1개월 전)**, 상업 쪽에서는 신해통공(1791), 정치 쪽에서는 채제공 우의정 임명(1788)이 더해졌다.
- 1787 사건은 한성의 왕 측근 무관 조직 안에서 국왕이 직접 판정했고(E019–E024), 1793 사건은 충청 병영→관찰사→암행어사→안핵어사→국왕을 거쳤다.
  이 차이는 사건 기록 자체에서 나오는 것이며, 위 정책 변화가 그 차이를 만들었다는 근거는 CSV에 없다.

**Q6. LEGAL_JUSTICE의 흠휼전칙·대전통편·증수무원록은 어떤 contemporaneous institutional context를 제공하는가?**
- 『흠휼전칙』(1778-01-12): 정책 CSV 요약상 죄수의 구금·형구·옥중 처우를 규율하는 형정 규범. 구순이 처음 조사받은 1784년, 제주 정배된 1787년, 1793년 김명신 옥중 사망 시점 모두에서 **이미 성립한 규범**(종료 기록 없음)이다.
- 『대전통편』(1785-02-24 편찬 총재 → 1785-09-11 반포): 1787 사건과 1793 사건 모두 반포 이후다.
- 『증수무원록』(1792-11-20 간행·반포 명령): 검험 표준화. 1793 사건 직전 해의 milestone이다.
- 1793 사건 기록에는 장기 구금, 옥중 사망(E056, 질병사 판정 E062 — 장형·평문 없음), 강압 진술(E040–E049)이 나오므로 위 법제와 **주제가 겹친다.**
  그러나 master CSV의 어떤 사건 행도 이 법전·규범을 언급하거나 적용했다고 기록하지 않는다. 정책 CSV의 notes가 JP004·JP019를 '구순–김명신 사건과 관련성이 높다'고 적은 것은
  **편집자의 relevance 판단**이지 사료상의 연결이 아니다. 따라서 '이 규범이 사건 처리에 영향을 주었다'는 결론은 내리지 않는다.
  맥락 정책 행 C001(흠휼전칙)에 대한 master CSV의 주석('Context only. Do not infer direct causal effect')도 같은 원칙이다.

**Q7. 장용위→장용영 발전은 구순의 무관 경력과 같은 시대에 어떻게 전개되는가?**
장용위 명명(1785-07-02)은 구순의 1784-09 정배와 1787-01 별군직 재등장 사이의 **기록 공백**(E018) 안에 있다. 장용영 확대(1788-01-22)는 1787 제주 정배 이후 공백 안에 있고,
화성 유수·장용외사 체계(1793-01-12)는 구순의 덕평 거주가 처음 관측되는 1793-02보다 약 1개월 앞서며, 그 날짜의 구순 상태는 CSV에 없다.
1785–1792년 구순 관측 기록은 {', '.join(gobs_8588) or '없음'}뿐이다 (모두 1787-01-03 한 날짜). 구순의 무관 경력은 선전관·별군직(왕 측근 무관)과 외임 수령·변장으로 기록되며,
CSV에는 구순이 장용위·장용영에 속했다는 기록이 없다. 두 흐름은 같은 시대에 **평행하게** 전개될 뿐 교차점이 관측되지 않는다.

**Q8. 탕평·규장각·초계문신 정책은 구순 경력과 별개의 국가 수준 변화로 어떻게 나타나는가?**
규장각 설치(1776-09-25)·검서관(1779)·초계문신 선발과 절목(1781-02~03)·의리의 탕평(1776)·채제공 우의정(1788)은 모두 NATIONAL scale의 인사·학술 제도다.
정책 CSV 요약상 초계문신은 '참상·참하 **문신**' 대상이고, 구순은 무관·수령 계열이므로 제도의 직접 대상이 아니다.
대시보드 C 패널 POLITICS_PERSONNEL lane에서 이 정책들은 구순의 1777–1782 임명 기록(A 패널)과 같은 시기에 보이지만, 두 층을 잇는 edge나 사건 행은 없다.

**Q9. 1793년 사건에서 실제로 확인되는 제도적 경로와 단순한 시대적 배경은 무엇이 다른가?**
- **확인되는 경로**(CSV edge가 있는 단계 연결 {len(explicit)}개): {'; '.join(f"{r.from_stage}→{r.to_stage}" for _, r in explicit.iterrows())}.
  구체적으로 구순 → 유제희(혐의자 이름 제공, E038) → 한재욱(명단 보고, E039) → 이진욱·조계완(체포 지시, E031) → 피의자·증인,
  병사 이광섭의 체포 명령(E035–E036), 그리고 국왕의 수금·조사·정배 명령(E055, E059, E066).
- **CSV edge가 없는 단계**({len(missing)}개): {'; '.join(f"{r.from_stage}→{r.to_stage}" for _, r in missing.iterrows())}. 자동으로 잇지 않았다.
- **시대적 배경**: 1793 정책 milestone {len(new93)}건({titles(new93.policy_event_id)})과 ONGOING CONTEXT {len(ongoing93)}건. 이것들은 관계 edge도 경로의 단계도 아니며,
  1793 확대 보기에서 별도 lane에 '신규'와 'ONGOING'으로 나눠 표시했다. ONGOING은 'CSV에 종료일이 없다'는 뜻이지 1793년 시행이 확인됐다는 뜻이 아니다.

**Q10. 시각화에서 직접 관측값·lookup 파생값·정책 맥락값·미해결값을 구별할 수 있는가?**

| 층 | 화면에서의 표현 | 데이터 표시 |
|---|---|---|
| 직접 관측(구순 기록) | A·B 패널의 색 점(일자 확정)·막대(구간), hover의 출처·grade | `evidence_status=OBSERVED` |
| lookup 파생(법정 품계) | A① Y 위치, hover '법정 품계(관직 자체)', '개인 품계 아님' 문구 | `office_lookup_match_status`, `office_lookup_verification_status` |
| 규칙 파생(관계 정규화·상태 구간·시간 창) | 관계군 lane, 상태 띠, ◇(관측 시점만 아는 관계) | `DERIVED`, `RELATION_WINDOW_DERIVED` |
| 정책 맥락 | C 패널의 회색 기호, 점선 지속 제도, Panel D의 '동시성만' 경고 | `data_layer=POLICY_CONTEXT`, `causal_link_to_gusun=NONE` |
| 미해결·미관측 | 빗금(종료 미상), ◁(시작 미상), ▷(OPEN), 연한 주황(1787→1793 공백), 'NA' | `UNKNOWN`/`OPEN`/`UNRESOLVED`, time_uncertainty |
| 시각화 좌표 | X 위치 전부 | `DERIVED_FOR_VISUALIZATION` |

### 9.6 동일인 증거의 엄격한 분리

`gusun_identity_links.csv`는 이제 반대 증거(`contradicting_evidence`), 긴장(`tension_evidence`), 결락(`missing_evidence`)을 서로 다른 컬럼으로 둔다.
**해배 기록이 없다는 사실은 반대 증거가 아니라 missing transition evidence다.**
L00(1787 ↔ 1793): 반대 증거 = {l00.contradicting_evidence} · 긴장 = {l00.tension_evidence} · 결락 = {l00.missing_evidence}.
판정은 {l00.same_person_status}로 변함없다.

### 9.7 검증 (`gusun_context_validation.csv`) — PASS {vs.get('PASS', 0)} · REPORTED {vs.get('REPORTED', 0)} · FAIL {vs.get('FAIL', 0)}

{md_table(val, ['check_no', 'layer', 'check', 'result', 'detail'], 20)}

### 9.8 추가 산출물

| 파일 | 내용 |
|---|---|
| `gusun_input_audit.csv` | 세 입력 파일 점검 |
| `gusun_policy_timeline_normalized.csv` | 정책 {len(pn)}행 + persistence_class·derived_plot_x·episode 순서 |
| `gusun_temporal_events_normalized.csv` | 구순 사건 정규화본 + lookup 결합 컬럼 + `date_as_recorded` + `current_rank_numeric` |
| `gusun_policy_context_windows.csv` | 구순 사건 × 정책 동시성 쌍 (인과 주장 없음) |
| `gusun_master_context_vs_policy_crosswalk.csv` | master 맥락 행 ↔ 정책 행 같은 날짜 대응 (병합 안 함) |
| `gusun_context_validation.csv` | 17개 검사 |
| `gusun_temporal_context_dashboard.html`, `gusun_1793_context_zoom.html` | 새 시각화 |
"""
