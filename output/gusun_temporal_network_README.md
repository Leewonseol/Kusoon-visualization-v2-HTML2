# 구순(具純) Temporal Multiplex Ego Network

> **경고 — 관측망 ≠ 역사적 현실.** 본 네트워크의 연결도와 중심성은 실제 역사적 관계뿐 아니라
> **기록 보존량과 행정문서의 관측 편향**을 반영한다. 이 네트워크는 입력 CSV에 기록된 관계만 담고 있으며,
> degree·betweenness·PageRank를 권력·영향력·사회적 중요성으로 해석해서는 안 된다.
> 1793년 김명신 사건의 인물이 많은 것은 형사 기록이 자세하기 때문이고, 김명신의 정보가 적다고
> 그가 덜 중요했다는 뜻도 아니다.

## 0. 범위와 원칙

- **유일한 입력**: `input/gusun_temporal_network_master_v0_2.csv` (102행 × 46열). 원본은 수정하지 않았다.
- **외부 접근 없음**: 웹 검색·URL 접속·API 호출을 하지 않았다. `source_url`은 출처 메타데이터 문자열로만 보존했다.
  실행 중 모든 소켓 연결을 차단·기록하는 가드를 걸었고 기록된 시도는 **0건**이다.
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
| 행 / 열 | 102 / 46 |
| 연도 범위 | 1763–1798 (음력 `date_lunar` 1763-01-13 ~ 1798-02-22) |
| subject/object id | 58개 (그중 네트워크 actor 40개; 정책·사건·상태 노드는 제외) |
| record_class | {'gu_network_event': 85, 'context_policy': 14, 'identity_evidence': 3} |
| time_precision | {'day': 97, 'interval': 3, 'month': 1, 'open_interval': 1} |
| evidence_grade | {'A': 90, 'B': 8, 'U': 4} |
| source_name | {'정조실록': 65, '승정원일기': 25, '비변사등록': 5, 'NA': 4, '노상추일기': 1, '비변사등록/한국사데이터베이스': 1, '정조실록 일별목록': 1} |
| 원문 relation_type | 78종 → 17종 vocabulary로 정규화 (원문은 `relation_subtype`에 보존) |

주요 품질 이슈 (`gusun_data_quality_findings.csv`):

| check | event_id | finding | action |
|---|---|---|---|
| time_precision_consistency | E026 | date_lunar='1793-02-early', time_precision='day' | YEAR_MONTH로 재분류; 임의의 일(day)을 부여하지 않음 |
| time_precision_consistency | E030 | date_lunar='1793-02-late', time_precision='day' | YEAR_MONTH로 재분류; 임의의 일(day)을 부여하지 않음 |
| time_precision_consistency | E038 | date_lunar='1793-03', time_precision='day' | YEAR_MONTH로 재분류; 임의의 일(day)을 부여하지 않음 |
| referenced_but_absent_evidence | I002;E001 | identity_link_basis가 '1782 royal dialogue'로 부자관계(구세덕-구순)를 근거한다고 하나 해당 1782 행이 CSV에 없음 | KINSHIP edge는 CSV 역할필드(father_of_candidate_gu)에 근거해 유지하되 confidence를 낮추고 플래그 |
| referenced_but_absent_evidence | E029;E079 | identity_link_basis가 '1795 長淵 transfer'를 언급하나 해당 이배 행이 없음 (E078 결락) | 백령도→장연현 연결을 HIGH_CONFIDENCE(미확정)로 둠; E079 시작일 1795-10-15는 CSV 단언값으로만 보존 |
| referenced_but_absent_evidence | I004 | 백령첨사 임명 행 자체는 없음; 1781-12 국왕 발언(I004)만 존재 | 백령첨사 재임 시작은 ≤1781-12로만 표현 |
| temporal_tension | E003;E004 | 1778-12-24 중화부사 임명(E003) 후 1779-08-10 별군직으로 왕 행행 수행(E004); 중화부사 체직 기록 없음 | 모순으로 처리하지 않음; identity_evidence에 TENSION으로 기록 |
| legacy_level_field | ALL | subject/object_level_current(0–5)는 품계가 아니라 CSV 작성자의 서열 코드이며, 구순의 경우 현직=3, 죄인·전직=1로 관직과 처벌 상태를 섞음 | csv_legacy_level로만 보존, rank_level 계산에 사용하지 않음 |
| official_rank_absent | ALL | CSV에 품계(정3품 등) 필드가 없음; E002만 '당상관'(일기 전언) | official_rank·rank_level은 NA (E002 행의 '당상관(일기 전언)'만 원문 보존) |
| record_vs_event_date | E060–E069 | 1793-06-13 최종 안핵 행들은 '기록·판정 일자'이며 서술된 행위(편들기·편파수사 등)의 발생일이 아님 | edge에 record_date와 관계 발생 구간(earliest/latest)을 분리 |

- 맥락 정책 행(C001–C017, 17행)은 `events`에는 `CONTEXT_POLICY`로 남겼지만 CSV 주석대로 구순에 대한 인과로 연결하지 않았고 네트워크에서 제외했다.
- `subject/object_level_current`(0–5)는 품계가 아니며 구순을 현직=3, 죄인=1로 코딩해 **관직과 처벌 상태를 섞는다.**
  `csv_legacy_level_*`로만 보존하고 어떤 분석에도 쓰지 않았다.

## 2. 산출물

| 파일 | 내용 |
|---|---|
| `gusun_persons.csv` | 인물·기관·집단 41개. 구순은 `GUSUN_PRE1793` / `GUSUN_1793PLUS` 두 세그먼트로 분리 |
| `gusun_events.csv` | CSV 102행 전체 + 정규화 시간·관직 차원·career_state |
| `gusun_temporal_edges.csv` | temporal edge 97개 (관측 79, 파생 18) |
| `gusun_identity_links.csv` / `gusun_identity_evidence.csv` / `gusun_identity_record_clusters.csv` | 동일인 판단 (링크·증거항목·기록 묶음) |
| `gusun_time_uncertainty.csv` | 시간 불확실성 41개 변수 |
| `gusun_career_states.csv` | 구순 career_state 구간 18개 |
| `gusun_network_metrics.csv` | 시기별 중심성 (해석 경고 컬럼 포함) |
| `gusun_network_composition.csv` / `gusun_node_turnover.csv` / `gusun_edge_transitions.csv` | 분석 B·C·D |
| `gusun_stage_handoffs.csv` / `gusun_institutional_paths.csv` / `gusun_sensitivity_analysis.csv` | 분석 E와 민감도 |
| `gusun_source_provenance.csv` | URL 문자열 파싱 결과 (접속 안 함) |
| `gusun_validation_report.csv` | 자동 검증 9항목 |
| `gusun_temporal_career.html` | 시각화 1: 경력 storyline |
| `gusun_temporal_multiplex_network.html` | 시각화 2: 관계 타임라인(전체·1793 확대), multiplex 그래프, 시기별 구성 |
| `gusun_dynamic_network.html` | 시각화 3: 시점별 애니메이션 (27프레임, 슬라이더) |

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

| spell_id | person_id | career_state | office_or_status | location | start | earliest_end | latest_end | evidence_start |
|---|---|---|---|---|---|---|---|---|
| S01 | GUSUN_PRE1793 | ACTIVE | 선전관→별군직 | 한성 | 1777-09-11 | 1778-07-04 | 1778-12-24 | E001 |
| S02 | GUSUN_PRE1793 | ACTIVE | 중화부사 | 중화부 | 1778-12-24 | 1778-12-24 | 1779-08-10 | E003 |
| S03 | GUSUN_PRE1793 | ACTIVE | 별군직 | 왕 행행 수행 | 1779-08-10 | 1779-08-10 | 1779-12-25 | E004 |
| S04 | GUSUN_PRE1793 | ACTIVE | 벽동군수 | 벽동군 | 1779-12-25 | 1779-12-25 | 1781-12-30 | E005 |
| S05 | GUSUN_PRE1793 | ACTIVE | 백령첨사 | 백령 | UNKNOWN | 1781-12-01 | 1782-12-29 | I004 |
| S06 | GUSUN_PRE1793 | ACTIVE | 영흥부사 | 영흥부 | 1782-12-29 | 1784-03-17 | 1784-03-18 | E006 |
| S07 | GUSUN_PRE1793 | UNDER_INVESTIGATION | 영흥부사(재임 중) | 영흥부 | 1784-03-18 | 1784-07-16 | 1784-07-16 | E011 |
| S08 | GUSUN_PRE1793 | ACTIVE | 영흥부사 | 영흥부 | 1784-07-16 | 1784-07-16 | 1784-09-23 | E016 |
| S09 | GUSUN_PRE1793 | EXILED | NA (별군직에서 정배) | 배소 미상 | 1784-09-23 | 1784-09-23 | 1787-01-03 | E017 |
| S10 | GUSUN_PRE1793 | ACTIVE | 별군직 | 한성 | UNKNOWN | 1787-01-03 | 1787-01-03 | E019 |
| S11 | GUSUN_PRE1793 | EXILED | NA | 제주목 | 1787-01-03 | 1787-01-03 | 1793-02-22 | E023 |
| S12 | GUSUN_1793PLUS | FORMER_OFFICIAL | 전 부사(府名 미상) | 청주 덕평 | UNKNOWN | 1793-02-01 | 1793-05-12 | E026 |
| S13 | GUSUN_1793PLUS | UNDER_INVESTIGATION | 전 부사(府名 미상) | 청주 덕평/충청도 | UNKNOWN | 1793-05-12 | 1793-05-12 | E050 |
| S14 | GUSUN_1793PLUS | IMPRISONED | 전 부사(府名 미상) | 의금부(한성) | 1793-05-12 | 1793-06-13 | 1793-06-13 | E055;E056;E059 |
| S15 | GUSUN_1793PLUS | EXILED | NA | 신지도 | 1793-06-13 | 1794-10-15 | 1794-10-15 | E066 |
| S16 | GUSUN_1793PLUS | EXILED | NA | 백령도 | 1794-10-15 | 1794-10-15 | 1798-02-21 | E076 |
| S17 | GUSUN_1793PLUS | EXILED | NA | 장연현 | UNKNOWN | 1798-02-21 | 1798-02-21 | E079 |
| S18 | GUSUN_1793PLUS | RELEASED | NA | 장연현→미상 | 1798-02-21 | UNKNOWN | UNKNOWN | E082 |

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

| period | n_edges_all | n_edges_ego | n_alters_ego | ego_OFFICIAL | ego_CONFLICT | ego_INVESTIGATION | ego_PRIVATE_SOCIAL | ego_HOUSEHOLD | ego_KINSHIP | ego_PUNISHMENT | ego_OTHER |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1_CAREER_1777_1783 | 8 | 8 | 3 | 7 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| P2_YEONGHEUNG_EXILE_1784 | 10 | 9 | 6 | 1 | 2 | 4 | 0 | 0 | 0 | 1 | 1 |
| P3_FALSE_ACCUSATION_1787 | 9 | 9 | 4 | 1 | 3 | 1 | 0 | 0 | 1 | 1 | 2 |
| P4a_KIM_CASE_1793-02 | 14 | 7 | 5 | 0 | 1 | 1 | 2 | 2 | 0 | 0 | 1 |
| P4b_KIM_CASE_1793-03 | 24 | 4 | 4 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 2 |
| P4c_KIM_CASE_1793-05 | 16 | 10 | 7 | 1 | 1 | 5 | 0 | 2 | 0 | 0 | 1 |
| P4d_KIM_CASE_1793-06 | 11 | 5 | 4 | 0 | 1 | 2 | 1 | 0 | 0 | 1 | 0 |
| P5_POST_SENTENCE_1794_1798 | 5 | 4 | 3 | 0 | 0 | 2 | 0 | 0 | 0 | 2 | 0 |

- 전체 edge 수 최대: **P4b_KIM_CASE_1793-03** (24건) — 대부분 구순이 끼지 않은 병영 실무자–피의자 사이의 수사 edge.
- 구순 ego edge 최대: **P4c_KIM_CASE_1793-05** (10건) — 관찰사 장계·국왕 수금 명령 등 INVESTIGATION 중심.
- 1777–1783은 OFFICIAL(임명·입시)이 전부다(그 밖에 시점 없는 부자 KINSHIP 1건이 이 시기에 배정됨). 1784는 OFFICIAL+CONFLICT+INVESTIGATION+PUNISHMENT,
  1787은 CONFLICT(무고)·KINSHIP(종형 연루)·PUNISHMENT, 1793-02에는 처음으로 PRIVATE_SOCIAL(이웃·친교)과 HOUSEHOLD가 등장하며,
  1794–98은 PUNISHMENT와 보고·방송 심의(INVESTIGATION군)만 남는다.
- 이것은 **기록이 어떤 관계를 남겼는가**의 분포다. 1777–83에 사적 관계가 0건인 것은 사적 관계가 없었다는 뜻이 아니다.

### Q4. 관계망은 시간에 따라 어떻게 교체되는가?

| period | n_actors | n_new | n_continuing | n_disappeared | continuing_from_previous | returning_from_earlier |
|---|---|---|---|---|---|---|
| P1_CAREER_1777_1783 | 3 | 3 | 0 | 0 |  |  |
| P2_YEONGHEUNG_EXILE_1784 | 7 | 5 | 2 | 1 | P_JEONGJO;P_STATE |  |
| P3_FALSE_ACCUSATION_1787 | 4 | 3 | 1 | 6 | P_JEONGJO |  |
| P4a_KIM_CASE_1793-02 | 10 | 10 | 0 | 4 |  |  |
| P4b_KIM_CASE_1793-03 | 14 | 8 | 6 | 4 | P_BYEON_JIDEUL;P_HAN_JAEUK;P_JA_MIDEOK;P_JEONG_WONDOL;P_JO_GYEWAN;P_KIM_MYEONGSIN |  |
| P4c_KIM_CASE_1793-05 | 10 | 5 | 3 | 11 | P_HAN_JAEUK;P_KIM_MYEONGSIN;P_LEE_GWANGSEOP | P_BIBEONSA;P_JEONGJO |
| P4d_KIM_CASE_1793-06 | 8 | 2 | 6 | 4 | P_HAN_JAEUK;P_JEONGJO;P_KIM_MYEONGSIN;P_LEE_GWANGSEOP;P_LEE_HYEONGWON;P_LEE_MUNHYEOP |  |
| P5_POST_SENTENCE_1794_1798 | 4 | 1 | 2 | 6 | P_HAN_JAEUK;P_JEONGJO | P_UIGEUMBU |

- PRE1793 세그먼트의 상대 인물 10명과 1793+ 세그먼트의 상대 인물 17명 중 겹치는 것은
  **정조(`P_JEONGJO`), 의금부(`P_UIGEUMBU`)뿐**이다 — 즉 국왕과 중앙 사법기관만 이어지고, 1787 사건의 이윤빈·유효원·조학신이나 1784의 신우문은
  1793 기록에 한 번도 나오지 않는다. 1787 → 1793 전환은 **사실상 완전한 관계망 교체**다.
- 1793 사건 안에서는 2월(가내·이웃·병영 실무자) → 3월(혐의자·증인 대량 유입) → 5월(관찰사·암행어사·비변사·국왕) → 6월(안핵어사·처벌)
  순으로 사적 층위에서 제도 층위로 교체된다.
- '사라짐'은 기록에서 관측되지 않음이며 관계 종료가 아니다.

### Q5. 친족·관료·갈등·수사 관계는 어떻게 다른 layer를 형성하는가?

전체 edge의 관계군 분포: OFFICIAL 14, CONFLICT 12, INVESTIGATION 43, PRIVATE_SOCIAL 3, HOUSEHOLD 4, KINSHIP 2, PUNISHMENT 12, OTHER 7.

- **KINSHIP layer** (2개): 구세덕(부, PRE1793; 근거 행 부재로 confidence `B_REDUCED`), 유효원(종형, 1787; 성씨가 달라 친족 경로 UNRESOLVED).
  둘 다 PRE1793에만 붙어 있고 **1793 세그먼트에는 친족 edge가 0개**다 — 이것이 동일인 판단의 친족 다리가 없는 이유이기도 하다.
  유효원과의 관계는 KINSHIP → ACCUSATION(무고에 연루시킴)으로 친족 layer와 갈등 layer가 같은 쌍에 겹친다.
- **OFFICIAL layer**: 1777–1784의 임명·입시·상관 관계와 1793 병영 내부 지휘(한재욱→이진욱·조계완, 이광섭→이문협).
- **CONFLICT layer**: 1784 상관 신우문과의 충돌, 1787 이윤빈 무고, 1793 김명신과의 단절·지목, 이광섭과의 가문 세혐.
- **INVESTIGATION layer**: 1793에 집중(43건). 구순이 직접 닿는 것은 유제희·이진욱 같은 실무자까지이고,
  강압 진술(한재욱→자미덕→정원돌·이집거 등)은 구순을 거치지 않는 2–4단계 하위망이다.
- **HOUSEHOLD / PRIVATE_SOCIAL layer**: 1793에만 관측 (나복·명업·행랑 하인들, 김명신 이웃·친교, 한재욱 '가객' 주장은 `B_CONTESTED`).

같은 인물쌍에서 layer가 바뀌는 전이 (`gusun_edge_transitions.csv`):

| pair | transition_compact | ordering_caveats |
|---|---|---|
| GUSUN_1793PLUS — P_KIM_MYEONGSIN | NEIGHBOR → FRIENDLY_ASSOCIATION → CONFLICT → ACCUSATION | E026: 이전 관계와 시간구간 중첩 → 순서 불확실; E027: 이전 관계와 시간구간 중첩 → 순서 불확실; E084: 이전 관계와 시간구간 중첩 → 순서 불확실; E038: 이전 관계와 시간구간 중첩 → 순서 불확실 |
| GUSUN_PRE1793 — P_JEONGJO | OFFICIAL_SUPERIOR → OFFICIAL_SUBORDINATE → OFFICIAL_SUPERIOR → PUNISHMENT → OTHER | E024: 동일 시점 → 순서 미정 |
| GUSUN_1793PLUS — P_JEONGJO | DETENTION → INVESTIGATION → PUNISHMENT | NONE |
| GUSUN_1793PLUS — P_LEE_GWANGSEOP | CONFLICT → FRIENDLY_ASSOCIATION → OTHER | E063: 이전 관계와 시간구간 중첩 → 순서 불확실; E037: 이전 관계와 시간구간 중첩 → 순서 불확실 |
| GUSUN_PRE1793 — P_LEE_YUNBIN | CONFLICT → ACCUSATION → OFFICIAL_COLLEAGUE | E020: 동일 시점 → 순서 미정; E019: 이전 관계와 시간구간 중첩 → 순서 불확실 |
| GUSUN_1793PLUS — N_HOUSE_SERVANTS | HOUSEHOLD → COMMAND | NONE |
| GUSUN_1793PLUS — P_HAN_JAEUK | HOUSEHOLD → TESTIMONY | NONE |
| GUSUN_PRE1793 — P_BIBEONSA | REPORT → OTHER | E013: 동일 시점 → 순서 미정; E014: 동일 시점 → 순서 미정 |
| GUSUN_PRE1793 — P_JO_HAKSIN | OTHER → TESTIMONY | E022: 동일 시점 → 순서 미정 |
| GUSUN_PRE1793 — P_RYU_HYOWON | KINSHIP → ACCUSATION | E021: 이전 관계와 시간구간 중첩 → 순서 불확실 |
| GUSUN_PRE1793 — P_SHIN_U_MUN | CONFLICT → OFFICIAL_SUPERIOR | E009: 동일 시점 → 순서 미정 |
| GUSUN_PRE1793 — P_STATE | OFFICIAL_SUPERIOR → INVESTIGATION | NONE |

대표 전이 **구순–김명신: NEIGHBOR → FRIENDLY_ASSOCIATION(시작 미상) → CONFLICT(1793-02, 박거사 문제로 단절) → ACCUSATION(1793-03 유제희에게 '수상하다'; 05-12 장계의 '도적 괴수' 지목)**,
이어서 김명신은 이광섭의 체포 명령(DETENTION, 03-04)·편파 수사(INVESTIGATION)를 받는다. 각 단계는 CSV 행에 근거가 있다.

**제도적 전달 경로 (분석 E).** 1793 사건 참여자를 CSV 역할·직함으로 단계에 배정하고, 인접 단계 사이에 CSV edge가 있는지만 확인했다:

| from_stage | to_stage | link_status | edges_forward |
|---|---|---|---|
| S0_HOUSEHOLD | S1_COMPLAINANT | EXPLICIT_IN_CSV | P_NABOK→GUSUN_1793PLUS:HOUSEHOLD[E028]; P_MYEONGEOP→GUSUN_1793PLUS:HOUSEHOLD[E028]; N_HOUSE_SERVANTS→GUSUN_1793PLUS:HOUSEHOLD[E085] |
| S1_COMPLAINANT | S2_CAMP_STAFF(병영 비장·영리) | EXPLICIT_IN_CSV | GUSUN_1793PLUS→N_UNNAMED_OFFICER:OTHER[E030]; GUSUN_1793PLUS→P_YU_JEHUI:REPORT[E038]; GUSUN_1793PLUS→N_MILITARY_SOLDIERS:OTHER[E086]; GUSUN_1793PLUS→P_HAN_JAEUK:HOUSEHOLD[E057] |
| S2_CAMP_STAFF(병영 비장·영리) | S3_ARREST_TEAM(장교) | EXPLICIT_IN_CSV | P_HAN_JAEUK→P_LEE_JINUK:COMMAND[E031]; P_HAN_JAEUK→P_LEE_JINUK:COMMAND[E032]; P_HAN_JAEUK→P_JO_GYEWAN:COMMAND[E031] |
| S3_ARREST_TEAM(장교) | S4_COMMANDERS(병사·영장) | NO_CSV_EDGE (자동 연결하지 않음) | NA |
| S4_COMMANDERS(병사·영장) | S5_SUSPECTS_WITNESSES | EXPLICIT_IN_CSV | P_LEE_GWANGSEOP→P_KIM_MYEONGSIN:DETENTION[E035]; P_LEE_GWANGSEOP→P_KIM_GAPDEUK:DETENTION[E036]; P_LEE_GWANGSEOP→P_KIM_MYEONGSIN:INVESTIGATION[E064]; P_LEE_MUNHYEOP→N_INNOCENT_COMMONERS:DETENTION[E065] |
| S5_SUSPECTS_WITNESSES | S6_GOVERNOR(관찰사) | NO_CSV_EDGE (자동 연결하지 않음) | NA |
| S6_GOVERNOR(관찰사) | S7_SECRET_INSPECTOR(암행어사) | NO_CSV_EDGE (자동 연결하지 않음) | NA |
| S7_SECRET_INSPECTOR(암행어사) | S8_SPECIAL_INVESTIGATOR(안핵어사) | NO_CSV_EDGE (자동 연결하지 않음) | NA |
| S8_SPECIAL_INVESTIGATOR(안핵어사) | S9_CENTRAL(국왕·비변사·의금부) | NO_CSV_EDGE (자동 연결하지 않음) | NA |
| S1_COMPLAINANT | S4_COMMANDERS(병사·영장) | EXPLICIT_IN_CSV | GUSUN_1793PLUS→P_LEE_GWANGSEOP:OTHER[E037] |
| S1_COMPLAINANT | S5_SUSPECTS_WITNESSES | EXPLICIT_IN_CSV | GUSUN_1793PLUS→P_KIM_MYEONGSIN:ACCUSATION[E084]; GUSUN_1793PLUS→P_KIM_MYEONGSIN:ACCUSATION[E038] |
| S2_CAMP_STAFF(병영 비장·영리) | S5_SUSPECTS_WITNESSES | EXPLICIT_IN_CSV | P_HAN_JAEUK→P_JA_MIDEOK:INVESTIGATION[E040]; P_HAN_JAEUK→P_JA_MIDEOK:INVESTIGATION[E041]; P_HAN_JAEUK→P_JA_MIDEOK:INVESTIGATION[E042]; P_HAN_JAEUK→P_JA_MIDEOK:INVESTIGATION[E043]; P_HAN_JAEUK→P_JA_MIDEOK:INVESTIGATION[E044]; P_YU_JEHUI→P_BYEON_JIDEUL:INVESTIGATION[E070]; P_YU_JEHUI→P_BYEON_JAEDOL:INVESTIGATION[E071]; P_YU_JEHUI→P_JEONG_WONDOL:INVESTIGATION[E072]; P_YU_JEHUI→P_KIM_SEONGSON:INVESTIGATION[E073]; P_YU_JEHUI→P_KIM_HEUNGDEUK:INVESTIGATION[E074]; P_YU_JEHUI→P_KIM_HEUNGGIL:INVESTIGATION[E075]; P_HAN_JAEUK→P_BYEON_JIDEUL:DETENTION[E031]; P_HAN_JAEUK→P_JEONG_WONDOL:DETENTION[E031]; P_YU_JEHUI→P_KIM_MYEONGSIN:INVESTIGATION[E039] |
| S4_COMMANDERS(병사·영장) | S5_SUSPECTS_WITNESSES | EXPLICIT_IN_CSV | P_LEE_GWANGSEOP→P_KIM_MYEONGSIN:DETENTION[E035]; P_LEE_GWANGSEOP→P_KIM_GAPDEUK:DETENTION[E036]; P_LEE_GWANGSEOP→P_KIM_MYEONGSIN:INVESTIGATION[E064]; P_LEE_MUNHYEOP→N_INNOCENT_COMMONERS:DETENTION[E065] |
| S2_CAMP_STAFF(병영 비장·영리) | S4_COMMANDERS(병사·영장) | NO_CSV_EDGE (자동 연결하지 않음) | NA |
| S6_GOVERNOR(관찰사) | S9_CENTRAL(국왕·비변사·의금부) | ONLY_REVERSE_DIRECTION | NA |
| S7_SECRET_INSPECTOR(암행어사) | S9_CENTRAL(국왕·비변사·의금부) | ONLY_REVERSE_DIRECTION | NA |
| S8_SPECIAL_INVESTIGATOR(안핵어사) | S9_CENTRAL(국왕·비변사·의금부) | NO_CSV_EDGE (자동 연결하지 않음) | NA |
| S9_CENTRAL(국왕·비변사·의금부) | S1_COMPLAINANT | EXPLICIT_IN_CSV | P_JEONGJO→GUSUN_1793PLUS:DETENTION[E055]; P_JEONGJO→GUSUN_1793PLUS:INVESTIGATION[E059]; P_JEONGJO→GUSUN_1793PLUS:PUNISHMENT[E066] |

- 구순 → 병영 실무자(유제희: 혐의자 이름 제공) → 비장 한재욱(명단 보고) → 장교 이진욱·조계완(체포 지시) → 피의자·증인 까지는 **CSV edge로 연결**된다.
- 그러나 **장교·비장 → 병사 이광섭**, **피의자 → 관찰사**, **관찰사 → 암행어사 → 안핵어사**, **안핵어사 → 중앙** 사이에는 CSV edge가 없다
  (관찰사·암행어사는 중앙으로부터의 처분만 역방향으로 존재). 이 구간은 자동으로 잇지 않았다.
- 시간순 경로(`gusun_institutional_paths.csv`): 구순에서 출발하는 시간순 경로 14종 중 13종은 월 단위 사건을 월초·월말 어디에 두어도 성립하고,
  1종(구순의 편지 E037 → 이광섭의 편파 수사 E064)은 구간 사건을 상한에 둘 때만 성립한다.
  E037 요약('김명신 **체포 길에 들른** 조계완')은 체포 명령(E035·E036)이 편지보다 먼저였음을 명시하므로 '편지 → 체포' 경로는 배제했다.
  시간순 경로가 있다는 것은 인과·전달의 증명이 아니다.

### Q6. 동일인 여부가 불확실한 구순 기록이 존재하는가?

존재한다. 핵심은 **R7(1787 별군직·제주 정배) ↔ R8A(1793 전 부사·김명신 사건)**이며, 세그먼트 수준 판정 L00 = **HIGH_CONFIDENCE** 이다.
CSV 작성자의 평가(`identity_bridge_status` = `highly_probable_not_fully_proven`)와 일치한다. 두 세그먼트는 **병합하지 않았다** —
`persons`·`edges`·시각화 모두에서 별도 노드이며 주황 점선 링크로만 연결된다. 전체 링크:

| link_id | identity_a | identity_b | same_person_status | supporting_evidence_count | contradicting_or_tension_count |
|---|---|---|---|---|---|
| L00 | GUSUN_PRE1793 | GUSUN_1793PLUS | HIGH_CONFIDENCE | 4 | 1 |
| L01 | R2_JUNGHWA_BUSA_1778 | R4_BAENGNYEONG_CHEOMSA_1781 | CONFIRMED | 2 | 0 |
| L02 | R1_SEONJEON_BYEOLGUN_1777_1779 | R2_JUNGHWA_BUSA_1778 | PLAUSIBLE | 2 | 1 |
| L03 | R2_JUNGHWA_BUSA_1778 | R3_BYEOKDONG_GUNSU_1779 | PLAUSIBLE | 3 | 0 |
| L04 | R4_BAENGNYEONG_CHEOMSA_1781 | R5_YEONGHEUNG_BUSA_1782_1784 | PLAUSIBLE | 3 | 0 |
| L05 | R5_YEONGHEUNG_BUSA_1782_1784 | R6_BYEOLGUN_EXILE_1784 | PLAUSIBLE | 2 | 1 |
| L06 | R1_SEONJEON_BYEOLGUN_1777_1779 | R6_BYEOLGUN_EXILE_1784 | HIGH_CONFIDENCE | 3 | 0 |
| L07 | R6_BYEOLGUN_EXILE_1784 | R7_BYEOLGUN_JEJU_EXILE_1787 | HIGH_CONFIDENCE | 4 | 0 |
| L08 | R7_BYEOLGUN_JEJU_EXILE_1787 | R8A_FORMER_BUSA_KIM_CASE_1793 | HIGH_CONFIDENCE | 4 | 1 |
| L09 | R8A_FORMER_BUSA_KIM_CASE_1793 | R8B_SINJIDO_TO_BAENGNYEONG_1794 | CONFIRMED | 3 | 0 |
| L10 | R8B_SINJIDO_TO_BAENGNYEONG_1794 | R8C_JANGYEON_RELEASE_1795_1798 | HIGH_CONFIDENCE | 3 | 1 |
| A01 | P_KIM_MYEONGSIN | alias:풍각 김생원 (E035) | HIGH_CONFIDENCE | 1 | 0 |
| A02 | P_KIM_MYEONGSIN | alias:풍각 김상제 (E038) | HIGH_CONFIDENCE | 1 | 0 |
| A03 | P_LEE_GWANGSEOP | role:'병사' (E035, E037) | HIGH_CONFIDENCE | 1 | 0 |

- CONFIRMED는 명시적 상호참조가 있는 두 곳뿐: 중화부사↔백령첨사(I004 국왕 발언), 1793 신지도 정배↔1794 '신지도에서' 백령도 이배(E076).
- PRE1793 내부도 단일 인물로 확정된 것이 아니다: 1777 별군직↔1778 중화부사, 중화↔벽동, 백령↔영흥, 영흥↔1784 별군직은 PLAUSIBLE이다.
- 김명신 별칭(풍각 김생원·풍각 김상제)과 '병사'=이광섭은 CSV 작성자의 괄호 매핑이라 원문 대조 없이 CONFIRMED로 올리지 않았다(HIGH_CONFIDENCE).

### Q7. 동일인 판단을 지지하는 CSV 내부 증거와 반대 증거는 무엇인가? (L00 = R7 ↔ R8A)

| 구분 | 증거 |
|---|---|
| 지지 | SAME_HANJA_NAME[E019;E026]; FORMER_OFFICE_TITLE_MATCH[E003;E006;E026]; CHRONOLOGICAL_COMPATIBILITY[E023;E028]; NO_COMPETING_SAME_NAME_IN_CSV[ALL] |
| 긴장(반대 방향) | AMNESTY_EXCLUSION_TENSION[E023;E025] |
| 결락 | MISSING_RELEASE_RECORD[E025]; MISSING_RETROSPECTIVE_REFERENCE[R8A]; MISSING_KINSHIP_BRIDGE[D01] |

- 직접 증거(해배 기록, 1793 기록 속 제주 정배·별군직 전력 언급, 1793 세그먼트의 친족 연결)는 **하나도 없다.**
- 가장 구체적인 단서는 1793 '전 부사'가 PRE1793의 중화부사·영흥부사 직함 이력과 맞는다는 점이다(단, 1793 기록에 府名이 없다).
- 확정적 반대 증거(같은 시점 두 장소, 다른 부친 등)는 CSV에 없다. 다만 1787 판결의 **勿揀赦典**은 일반 사면에 의한 해배를 배제하므로,
  동일인이라면 특별 해배가 있었어야 하는데 그 기록이 없다 — 이는 반증이 아니라 **풀리지 않은 긴장**이다.
- CSV 안에 다른 具純 후보가 없다는 점은 CSV가 한 인물 중심으로 수집됐기 때문에 약한 단서(`WEAK_SUPPORT`)로만 셌다.

### Q8. 날짜가 불확실한 사건은 무엇이며 interval을 얼마나 좁힐 수 있는가?

| uncertainty_id | uncertain_variable | lower_bound | upper_bound | uncertainty_type | candidate_narrowing_not_applied |
|---|---|---|---|---|---|
| U_RELEASE_1784 | T_release (1784 정배 해배·복귀) | 1784-09-23 | 1787-01-03 | INTERVAL_CENSORED | NA |
| U_RELEASE_1787 | T_release (1787 제주 정배 해배) | 1787-01-03 | 1793-02-22 | INTERVAL_CENSORED | E026/E027 '1793-02-early'가 실제 상순(1–10일)이면 상한 1793-02-10까지; '본래 친숙하여 날마다 상종'은 그 이전 거주를 시사하나 기간 미상 → 적용 안 함 |
| U_JUNGHWA_END | T_end(중화부사 재임) | 1778-12-24 | 1779-08-10 | OFFICE_TRANSITION | NA |
| U_BYEOKDONG_END | T_end(벽동군수) / T_start(백령첨사) | 1779-12-25 | 1781-12-30 | OFFICE_TRANSITION | NA |
| U_BAENGNYEONG_END | T_end(백령첨사) | 1781-12-01 | 1782-12-29 | OFFICE_TRANSITION | NA |
| U_BYEOLGUN_RETURN_1784 | T_start(별군직 복귀, 영흥부사 이후) | 1784-07-16 | 1784-09-23 | OFFICE_TRANSITION | NA |
| U_BYEOLGUN_RETURN_1787 | T_start(1787 별군직 재직) | 1784-09-23 | 1787-01-03 | OFFICE_TRANSITION | NA |
| U_I004 | T_event(EXPLICITLY_LINKS_PRIOR_OFFICE) | 1781-12-01 | 1781-12-30 | MONTH_LEVEL_DATE | NA |
| U_E026 | T_event(PRIOR_FRIENDSHIP) | 1793-02-01 | 1793-02-30 | MONTH_LEVEL_DATE | 한정어 'early'를 상순(1–10일)으로 읽으면 [..-01, ..-10] — 해석 규칙이므로 적용 안 함 |
| U_E027 | T_event(REBUKES_AND_BREAKS_CONTACT) | 1793-02-01 | 1793-02-30 | MONTH_LEVEL_DATE | 한정어 'early'를 상순(1–10일)으로 읽으면 [..-01, ..-10] — 해석 규칙이므로 적용 안 함 |
| U_E030 | T_event(PRIVATE_CONTACT_WITH_OFFICER) | 1793-02-01 | 1793-02-30 | MONTH_LEVEL_DATE | '체포령 뒤' + 한정어 'late' → E031(1793-02-28) 이후면 [02-28, 02-30] — E031이 그 체포령인지 CSV가 명시하지 않아 적용 안 함 |
| U_E038 | T_event(PROVIDES_SUSPECT_NAME) | 1793-03-01 | 1793-03-30 | MONTH_LEVEL_DATE | E038(구순→유제희)→E039(유제희→한재욱)→E035(03-04 체포명령) 순서라면 [03-01, 03-04] — CSV가 순서를 명시하지 않아 적용 안 함 |
| U_E039 | T_event(SUBMITS_SUSPECT_LIST) | 1793-03-01 | 1793-03-30 | MONTH_LEVEL_DATE | E038(구순→유제희)→E039(유제희→한재욱)→E035(03-04 체포명령) 순서라면 [03-01, 03-04] — CSV가 순서를 명시하지 않아 적용 안 함 |
| U_REL_E063 | T_relation(기록일≠행위일) | 1793-02-22 | 1793-05-12 | RECORD_VS_EVENT_DATE | NA |
| U_REL_E064 | T_relation(기록일≠행위일) | 1793-02-22 | 1793-05-12 | RECORD_VS_EVENT_DATE | NA |
| U_REL_E065 | T_relation(기록일≠행위일) | 1793-02-22 | 1793-05-12 | RECORD_VS_EVENT_DATE | NA |
| U_REL_E084 | T_relation(기록일≠행위일) | 1793-02-22 | 1793-05-12 | RECORD_VS_EVENT_DATE | NA |
| U_REL_E085 | T_relation(기록일≠행위일) | 1793-02-22 | 1793-05-12 | RECORD_VS_EVENT_DATE | NA |
| U_REL_E086 | T_relation(기록일≠행위일) | 1793-02-22 | 1793-05-12 | RECORD_VS_EVENT_DATE | NA |
| U_FRIENDSHIP_START | T_start(구순–김명신 친교) | UNKNOWN | 1793-02-30 | LEFT_CENSORED | NA |
| U_DEATH_KIM | T_death(김명신, 옥중) | 1793-03-04 | 1793-05-27 | INTERVAL_CENSORED | NA |
| U_GUSUN_ARREST_1793 | T_arrest(의금부 수금 실행) | 1793-05-12 | 1793-05-27 | INTERVAL_CENSORED | NA |
| U_TRANSFER_JANGYEON | T_transfer(백령도→장연현) | 1794-10-15 | 1798-02-21 | INTERVAL_CENSORED | CSV 단언(E079 date_lunar)을 채택하면 상한 1795-10-15 |
| U_SENTENCE_CONVERSION | T_conversion(절도정배→도3년) | 1793-06-13 | 1798-02-21 | INTERVAL_CENSORED | NA |
| U_POST1798 | T_any_later_event / T_death(구순) | 1798-02-22 | OPEN | RIGHT_CENSORED | NA |

(1793-03 월 단위 수사 행 E040–E049, E070–E075도 같은 방식으로 각각 [1793-03-01, 1793-03-30] 구간을 가진다.)

- **T_release(1787 제주 정배) ∈ (1787-01-03, 1793-02-22)**: 하한은 판결일, 상한은 '구순 집 종' 나복이 등장하는 일자 확정 최초 관측(E028).
  명목 약 73 음력월(윤달 미반영). '1793-02-early' 기록(E026/E027)과 '본래 친숙' 진술은 더 이른 거주를 시사하지만
  일자를 주지 않으므로 상한을 더 좁히지 않았다. **이 변수는 L00 동일인 가정 하에서만 정의된다.**
- **좁힐 수 있었던 것**: 김명신 사망 (1793-03-04, 1793-05-27] — 체포 명령과 '옥사' 보고 사이; 구순 의금부 수감 실행 [05-12, 05-27].
- **좁히지 않은 것(후보 제약으로만 기록)**: 'early/late' 한정어를 상순/하순으로 읽는 해석, E038→E039→E035 순서 가정,
  E079의 '1795-10-15 장연 정배'(지지 행이 없는 CSV 단언 — 확실한 상한은 1798-02-21).
- 민감도 분석 (`gusun_sensitivity_analysis.csv`):

| analysis | scenario | scenario_definition | n_paths | shortest |
|---|---|---|---|---|
| time-respecting paths GUSUN_1793PLUS→김명신 | EARLY | 월 단위·구간 edge를 하한(earliest)에 배치 | 2 | GUSUN_1793PLUS → P_KIM_MYEONGSIN |
| time-respecting paths GUSUN_1793PLUS→김명신 | LATE | 월 단위·구간 edge를 상한(latest)에 배치 | 3 | GUSUN_1793PLUS → P_KIM_MYEONGSIN |
| 1793-03 월 단위 사건(E038,E039 등) vs E035(03-04) 순서 | BOUNDS | [1793-03-01, 1793-03-30] vs 1793-03-04 | NA | 03-04 이전/이후 모두 가능 → 'E038→E039→체포명령' 인과 순서는 UNRESOLVED |
| T_release_1787 interval | BOUNDS | (1787-01-03, 1793-02-22) | NA | 연도별 확률 미산출. 어떤 해배 시점을 택해도 L00 판정(HIGH_CONFIDENCE)은 변하지 않음 — 판정은 해배 시점이 아니라 해배 '기록'의 존재에 달려 있음 |

### Q9. 현재 네트워크에서 가장 큰 data gap은 무엇인가?

1. **1787-01-03 ~ 1793-02-22 구순 기록 전무** — 해배·복귀·이주·거주 시작 모두 미관측. 동일인 판단의 결정적 결락.
2. **1784-09-23 ~ 1787-01-03 해배·별군직 복귀 기록 없음** (E018).
3. **CSV 메타필드가 언급하지만 행으로 없는 근거**: 1782 부자관계 확인 국왕 대화(구세덕–구순 KINSHIP의 근거), 1795 長淵 이배(E078 결락), 백령첨사 임명 행.
   id 결락은 I001, E078, C008, C009, C011.
4. **관직 재임 종료일 0건**: 모든 관직은 임명일(또는 한 시점) 관측뿐이라 재임 기간은 '단일 관직' 모델 가정 없이는 정의되지 않는다.
5. **품계 정보 부재** → rank_level을 만들 수 없음.
6. **1793 제도적 전달 경로의 단절**: 장교·비장→병사, 관찰사→암행어사→안핵어사→중앙 사이의 문서 흐름 edge 없음.
7. **1798-02-21 이후 OPEN** (E083: 검색 실패를 사망·은거로 해석하지 않음).
8. **김명신의 독립 정보**: biographical_coverage_score = 2. CSV에서 확인되는 것은 '반족', '구순 이웃', 풍각 김생원/김상제라는 호칭,
   구순과의 친교→단절, 혐의자 명단·체포·수감, 옥중 사망(1793, 일자 구간만), 질병사 판정과 장형·평문 없음뿐이다.
   생년·본관·관직·가족·재산은 모두 `NA`이며 추정하지 않았다. 이 정보 부족은 김명신의 역사적 비중이 아니라 기록 구조를 반영한다.

### Q10. 어떤 결과가 직접 관측이고 어떤 결과가 파생·추론인가?

| 층 | 해당 결과 |
|---|---|
| **OBSERVED** (CSV 직접) | 102개 사건 행과 그 날짜·장소·요약·출처, 인물 이름·한자·신분 라벨, 관계 edge 67개(행 그대로), 시간 구간이 보정된 관측 edge 12개의 관계 자체, 김명신 사망 사실, 1793 '전 부사' 라벨, 勿揀赦典 |
| **DERIVED** (규칙 변환) | relation_type 17종 정규화와 관계군, 역할필드·라벨·요약문에서 읽은 edge 18개, 관직 차원(scope·proximity·command), career_state·state spell, 날짜 정규화(월 단위→월 경계 구간), 기록일≠행위일 구간, 시기 구분, 성별(친족어가 있는 경우만), biographical_coverage_score |
| **INFERRED** (모델·계산) | 동일인 판정(L00–L10의 status), 중심성 지표, 시간순 경로·단계 연결, 민감도 결과, 노드 교체·전이 순서 |
| **MODEL_ASSUMPTION** | '동시에 하나의 관직'(관직 전환 구간 U_JUNGHWA_END 등), 균등 구간 사전분포(민감도용), 프레임 내 월 단위 배치 규칙 |
| **DERIVED_FOR_VISUALIZATION** | plot_x(명목 음력 소수연도), 애니메이션 프레임 순서, 그래프 레이아웃 좌표 |

## 5. 중심성 사용 제한

`gusun_network_metrics.csv`에 전체·시기별 degree, betweenness, PageRank를 계산했지만 해석하지 않는다.
구순 두 세그먼트가 betweenness 1·2위인 것은 **ego network로 수집했기 때문**이고, 정조가 3위인 것은 국왕 명의 처분이 행정문서에 체계적으로 남기 때문이다.
그래프 노드 크기도 중심성으로 키우지 않았다.

## 6. 자동 검증 결과

| check_no | check | result | detail |
|---|---|---|---|
| 1 | event_start > event_end 없음 | PASS | events 102행·edges 97행 검사 |
| 2 | earliest_possible > latest_possible 없음 (events·edges·uncertainty·career) | PASS | 모든 하한 ≤ 상한 |
| 3 | edge가 존재하지 않는 person_id를 참조하지 않음 | PASS | 41 persons |
| 4 | event_id·edge_id 중복 없음 | PASS | dup events [], edges [] |
| 5 | relation_type ∈ 정의된 vocabulary | PASS | 사용된 유형 ['ACCUSATION', 'COMMAND', 'CONFLICT', 'DETENTION', 'FRIENDLY_ASSOCIATION', 'HOUSEHOLD', 'INVESTIGATION', 'KINSHIP', 'NEIGHBOR', 'OFFICIAL_COLLEAGUE', 'OFFICIAL_SUBORDINATE', 'OFFICIAL_SUPERIOR', 'OTHER', 'PUNISHMENT', 'REEXAMINATION', 'REPORT', 'TESTIMONY'] |
| 6 | UNKNOWN 날짜를 실제 날짜처럼 계산에 사용하지 않음; 월 단위에 일 생성 없음 | PASS | UNKNOWN→plot_x=NaN; 월 단위 event_start는 YYYY-MM 유지 |
| 7 | EXILED/DISMISSED/IMPRISONED을 관직 level로 오인하지 않음 | PASS | rank_level 전부 NA(품계 부재); 처벌 상태는 career_state에만 존재; 관직 lane에 상태 없음 |
| 8 | 원본 CSV에 없는 정보를 생성하지 않음 (인물·사건 id·파생 edge 근거문·관직명) | PASS | persons 41 ⊂ CSV ids; edges 97 모두 CSV event_id 참조; 파생 edge 18개 근거문 확인 |
| 9 | source_url 실제 접속 시도 없음 | PASS | 런타임 소켓 연결 시도 0건 (socket guard); 정적 검사 위반 없음; 패턴 정의 줄이라 제외한 매치 9건; socket import 위치 ['run_all.py:5'] (연결 차단 가드 용도) |

## 7. 원래 연구 질문(1787 정배 구순 = 1793 전 부사 구순?)에 대한 현재 답

이 CSV만으로는 **HIGH_CONFIDENCE (CONFIRMED 아님)**. 지지 근거는 같은 한자명, 부사 직함 이력 일치, 연대 양립이며,
확정에 필요한 것은 (a) 1787–1793 사이 해배·방송 기록, (b) 1793 이후 기록에서 제주 정배·별군직 전력이나 부친 구세덕을 언급하는 구절,
(c) 1793 '전 부사'의 府名이다. 반대로 같은 시기에 다른 具純이 다른 장소에 있었다는 기록이 나오면 두 세그먼트는 이미 분리돼 있으므로
L00만 CONTRADICTED로 바꾸면 된다.


---

## 8. 관직 법정 품계 lookup 결합 (`office_rank_lookup.csv`)

> **lookup의 품계는 관직 자체의 법정·제도적 품계다. 구순 개인의 실제 품계(personal_rank)가 아니다.**
> CSV에서 개인 품계로 읽히는 것은 E002의 '당상관'(노상추일기 전언) 하나뿐이며 `personal_rank`에 따로 보존했다.
> `rank_numeric`(정3품=3.0, 종3품=3.5, 정4품=4.0, 종4품=4.5 …)은 **시각화 Y축 정렬용**이고 권력 점수·사회적 영향력·개인 품계가 아니다.

### 8.1 입력과 조인 규칙

- lookup: `input/office_rank_lookup.csv` (28행 × 16열). 원본 두 CSV는 수정하지 않았다.
  lookup의 `source_url_1/2`(한국민족문화대백과사전·실록·승정원일기·우리역사넷)는 메타데이터로만 보존했고 접속하지 않았다.
  lookup의 품계 판정·`verification_status`는 lookup 작성자의 판단이며, 이 작업에서 독립적으로 재검증하지 않았다.
- 조인 키: master의 `subject_office_status`와 `object_office_status`를 각각 lookup의 `raw_office_status`에 **LEFT JOIN**한다.
  master에는 직함 전용 필드가 없고 이 두 필드가 직함·신분·역할을 담고 있으며, lookup 키 28개가 전부 이 두 필드의 값과 문자 단위로 같다.
- 매칭 순서: **EXACT**(문자열 완전 일치) → **NORMALIZED**(유니코드 NFKC + 공백 정리만, 정규화 후에도 키가 유일할 때) → **UNMATCHED**.
  부분 문자열·유사도 기반 fuzzy 매칭은 구현하지 않았다.
- 요청된 파생 컬럼(`normalized_office_title`, `office_title_hanja`, `record_type`, `administrative_scope`, `statutory_rank`,
  `rank_numeric`, `rank_fixedness`, `rank_visualizable`, `former_statutory_rank`, `office_lookup_match_status`,
  `office_lookup_verification_status`)은 각 행의 **focal 인물**(구순이 있으면 구순 쪽, 없으면 subject)을 기준으로 채웠다.
  subject·object 양쪽의 결과는 `subject_*`, `object_*` 접두사 컬럼으로 모두 남겼다.
- 앞 단계의 관직명 규칙 결과는 `rule_scope_v1`로 남겼다. lookup의 scope와 충돌하는 곳은 없고, lookup 쪽이 더 세분된다
  (예: 별군직 COURT → COURT_MILITARY, 영흥부사·겸영장 LOCAL → LOCAL_MILITARY, 백령첨사 MILITARY → MILITARY_LOCAL).

### 8.2 매칭 결과

| match_status | distinct_values | occurrences |
|---|---|---|
| EXACT | 28 | 87 |
| UNMATCHED | 48 | 113 |

- lookup 28행 중 28행이 사용됐다 (미사용 0행).
- NORMALIZED가 0건인 것은 정상이다: 모든 직함이 원문 그대로 일치했다.
- UNMATCHED 48개 고유값은 대부분 관직이 아니다 (국왕·정부 같은 통치자·기관, 민간인·가내, 죄인·정배 같은 처벌 상태, 정책·사건 노드).
  **직함처럼 보이지만 lookup에 키가 없는 값** 5개는 결합하지 않고 lookup 추가 후보로만 표시했다:
  '별군직 청수 관련', '병영·진영 실무자', '영흥부 아전', '중영 하급 실무자', '체포 장교'. 예를 들어 '체포 장교'는 lookup의 '청주진 장교'와 단어가 겹치지만
  같은 직함이라고 단정할 근거가 없어 자동 결합하지 않았다.
- 전체 목록: `gusun_office_lookup_join_audit.csv`.

### 8.3 구순 직함별 결합 결과

| first | focal_raw_office_status | normalized_office_title | statutory_rank | rank_numeric | rank_fixedness | rank_lane | former_statutory_rank | office_lookup_verification_status | n_rows |
|---|---|---|---|---|---|---|---|---|---|
| 1777-09-02 | 선전관/별군직 계열 | 선전관/별군직 계열 | 가변 | NA | VARIABLE | COURT_MILITARY_VARIABLE | NA | AMBIGUOUS | 1 |
| 1777-09-11 | 선전관→별군직 | 선전관→별군직 | 가변 | NA | VARIABLE | COURT_MILITARY_VARIABLE | NA | CONFIRMED_VARIABLE | 1 |
| 1778-07-04 | 선전관 | 선전관 | 가변 | NA | VARIABLE | COURT_MILITARY_VARIABLE | NA | CONFIRMED_VARIABLE | 1 |
| 1778-12-24 | 중화부사 | 도호부사 | 종3품 | 3.5 | FIXED | 종3품 | NA | CONFIRMED | 1 |
| 1779-08-10 | 별군직 | 별군직 | 비고정 | NA | VARIABLE | COURT_MILITARY_VARIABLE | NA | CONFIRMED_VARIABLE | 6 |
| 1779-12-25 | 벽동군수 | 군수 | 종4품 | 4.5 | FIXED | 종4품 | NA | CONFIRMED | 1 |
| 1781-12 | 백령첨사 | 첨사(첨절제사) | 종3품 | 3.5 | FIXED | 종3품 | NA | DERIVED_CONFIRMED | 1 |
| 1782-12-29 | 영흥부사 | 대도호부사 | 정3품 | 3.0 | FIXED | 정3품 | NA | CONFIRMED | 9 |
| 1784-04-30 | 영흥부사·겸영장 | 대도호부사+겸영장 | 정3품 | 3.0 | FIXED | 정3품 | NA | CONFIRMED | 1 |
| 1793-02-22 | 전 부사·민간 거주 | 전 부사 | 현재 품계 없음 | NA | FORMER_OFFICE | FORMER_OFFICIAL (career-state band) | 정3품 또는 종3품(부의 종류에 따라 다름) | CONFIRMED_STATE | 8 |
| 1793-02-early | 전 부사·청주 덕평 거주 | 전 부사 | 현재 품계 없음 | NA | FORMER_OFFICE | FORMER_OFFICIAL (career-state band) | 정3품 또는 종3품(부의 종류에 따라 다름) | CONFIRMED_STATE | 2 |
| 1793-05-12 | 전 부사 | 전 부사 | 현재 품계 없음 | NA | FORMER_OFFICE | FORMER_OFFICIAL (career-state band) | 정3품 또는 종3품(부의 종류에 따라 다름) | CONFIRMED_STATE | 5 |

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

| check_no | check | result | detail |
|---|---|---|---|
| 1 | FIXED인데 rank_numeric이 없는 행 | PASS | lookup FIXED 12행 모두 값 있음 |
| 2 | VARIABLE/비고정인데 rank_numeric이 들어간 행 | PASS | 비고정 lookup 16행 (FORMER_OFFICE, NO_SINGLE_STATUTORY_RANK, UNRANKED_CLERICAL, VARIABLE) 모두 빈 값 |
| 3 | FORMER_OFFICIAL인데 현재 rank_numeric이 들어간 행 | PASS | FORMER_OFFICIAL 행 14개 모두 rank_numeric 비움 (former_statutory_rank만 보존) |
| 4 | 동일 raw_office_status가 서로 다른 fixed rank로 중복 매핑 | PASS | lookup 키 28개 모두 유일 (정규화 후에도 유일) |
| 5 | unmatched office status (보고 항목) | REPORTED | 고유값 48개 / 출현 113회; 성격 {'RULER_OR_INSTITUTION': 46, 'NON_OFFICE_PERSON_OR_HOUSEHOLD': 33, 'PENAL_OR_CAREER_STATE': 17, 'POLICY_EVENT_OR_LIST': 12, 'POSSIBLE_OFFICE_NOT_IN_LOOKUP': 5}; lookup 추가 후보(직함처럼 보이나 키 없음): ['별군직 청수 관련', '병영·진영 실무자', '영흥부 아전', '중영 하급 실무자', '체포 장교'] |
| 6 | join 후 temporal network 원본 행 수 불변 | PASS | 원본 102행 → 결합 102행, event_id 순서 동일=True |
| 7 | fuzzy merge가 발생하지 않음 | PASS | EXACT 87회·NORMALIZED 0회 모두 문자열 동일성으로 재확인; 부분 문자열이 겹치지만 결합하지 않은 값: ['별군직 청수 관련', '병영·진영 실무자', '중영 하급 실무자', '체포 장교'] |

### 8.5 산출물

| 파일 | 내용 |
|---|---|
| `gusun_temporal_network_with_office_rank.csv` | master 102행 전체 + lookup 파생 컬럼 (행 수 불변) |
| `gusun_office_lookup_join_audit.csv` | 고유 직함 값별 매칭 상태·근거·조치 |
| `gusun_office_rank_validation.csv` | 위 7개 검사 |
| `gusun_temporal_career_with_rank.html` | ① 고정 품계 수치축 ② 가변 직함 category lane ③ career_state band. 다른 인물의 직함은 범례 클릭으로 표시 |
| `intermediate/09_office_scope_rule_vs_lookup.csv` | 앞 단계 규칙 scope와 lookup scope 비교 |

기존 산출물(`gusun_temporal_career.html` 등)은 그대로 보존했다.
