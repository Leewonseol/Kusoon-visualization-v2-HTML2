# 구순(具純) Temporal Network — 시각화

조선 후기 무관 구순(具純)의 관직·신분·처벌·인간관계를 시간축 위에 복원하고,
같은 시간축 아래에 정조대의 주요 정책·제도 변화를 함께 놓은 정적 시각화 모음입니다.

## 웹사이트 진입점 (GitHub Pages)

- 진입점: 저장소 루트의 **`index.html`**
- 첫 화면은 **전체 시간·정책 대시보드**를 iframe으로 보여주고, 상단 메뉴로 다른 시각화로 전환합니다.
- 특정 시각화로 바로 들어가려면 해시를 붙입니다:
  `index.html#dashboard`, `#zoom1793`, `#career`, `#dynamic`, `#multiplex`
- 서버나 백엔드가 없는 정적 사이트입니다. 모든 링크는 상대경로(`./output/...`)라서 Pages 하위 경로(`/<저장소 이름>/`)에서도 그대로 동작합니다.

## 시각화

| 메뉴 이름 | 파일 | 목적 |
|---|---|---|
| 전체 시간·정책 대시보드 (메인) | [`output/gusun_temporal_context_dashboard.html`](./output/gusun_temporal_context_dashboard.html) | 1776–1799 공통 시간축 위에 A) 구순의 관직(법정 품계 / 가변 직무 / career_state), B) 구순 사건과 관계, C) 정조대 정책 milestone을 나란히 표시. 클릭하면 오른쪽 패널에 상세와 같은 해·전 해·다음 해 정책이 나온다(동시성만, 인과 아님). |
| 1793년 구순–김명신 사건 확대 | [`output/gusun_1793_context_zoom.html`](./output/gusun_1793_context_zoom.html) | 1793년 음력 1–12월을 확대해 상태 변화, 주변 인물 관계, 1793년 신규 정책과 이전부터 이어진 제도(ONGOING)를 구분해 보여준다. |
| 구순 관직·품계 타임라인 | [`output/gusun_temporal_career_with_rank.html`](./output/gusun_temporal_career_with_rank.html) | 관직 자체의 법정 품계(구순 개인 품계 아님)를 수치축에, 선전관·별군직 같은 가변 직무를 별도 lane에, 전직·정배·수감을 상태 띠에 분리. |
| 동적 인물 네트워크 | [`output/gusun_dynamic_network.html`](./output/gusun_dynamic_network.html) | CSV에 기록이 있는 시점만 프레임으로 만든 네트워크 애니메이션(슬라이더). |
| Temporal Multiplex Network | [`output/gusun_temporal_multiplex_network.html`](./output/gusun_temporal_multiplex_network.html) | 상대 인물별 관계 타임라인(전체·1793 확대), 관계 layer 토글 그래프, 시기별 관계 구성. |

그 밖에 `output/gusun_temporal_career.html`(품계 결합 전 경력 storyline)도 있습니다.

각 HTML은 Plotly를 내부에 포함한 self-contained 파일(약 5MB)이라 외부 CDN 없이 열리며, 처음 열 때 시간이 조금 걸릴 수 있습니다.

## 읽을 때 주의할 점

- 이 네트워크는 역사적 현실 전체가 아니라 **입력 CSV에 기록된 관계망**입니다. 연결 수·중심성은 실제 영향력이 아니라 기록 보존량과 행정문서의 관측 편향을 반영합니다.
- 날짜는 모두 **음력**이며 양력으로 바꾸지 않았습니다. X축은 시각화용 명목 소수연도입니다.
- 품계는 **관직 자체의 법정 품계**이고 `rank_numeric`은 정렬용 숫자입니다(권력 점수·개인 품계 아님).
- 정책은 별도의 context layer입니다. 정책과 구순 사건이 같은 시기에 보이는 것은 **인과관계를 뜻하지 않습니다.**
- 1787년 제주 정배 구순과 1793년 전 부사 구순은 **동일인 HIGH_CONFIDENCE(미확정)**로 두고 병합하지 않았습니다.

## 데이터와 재현

- 입력: `input/gusun_temporal_network_master_v0_2.csv`, `input/office_rank_lookup.csv`, `input/jeongjo_policy_timeline.csv`
- 분석 결과 CSV·검증표·상세 README: `output/` (특히 [`output/gusun_temporal_network_README.md`](./output/gusun_temporal_network_README.md))
- 재생성: `pip install pandas networkx plotly scipy` 후 `python scripts/run_all.py`
  (외부 네트워크에 접속하지 않으며, 실행 중 소켓 연결을 차단·기록합니다.)
- `index.html`, `style.css`, 이 README는 랜딩 페이지용이며 위 스크립트가 다시 만들지 않습니다.
