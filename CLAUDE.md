# ds_tcmaker

피그마에서 내보낸 기획서(PDF/이미지)를 받아 Claude로 분석하고, 블랙박스 테스트 케이스(엑셀·리포트·JSON)를 만드는 QA 에이전트.
사용법은 README.md, 사용자용 매뉴얼은 docs/ds_tcmaker_manual.pptx.

## 구조

- `main.py`: CLI 진입점. `specs/`의 새 파일을 처리, `--watch`(폴더 감시), `--dry-run`(API 없이 타일만), `--force`, `--effort`, `--tile-pt`
- `tc_agent/loader.py`: PDF/이미지를 글자가 읽히는 크기의 타일(기본 1600pt, 10% 겹침)로 자르고 빈 타일은 제외. 큰 보드는 `ProcessPoolExecutor`로 렌더링해서 CPU를 거의 다 씀
- `tc_agent/generator.py`: 타일을 Claude(`MODEL`)에 보내 `TestSuite`로 구조화된 결과를 받음. 한 요청 이미지 100장 한도
- `tc_agent/schema.py`: 결과 구조(분석 리포트, TC, 기획 확인 필요 사항)
- `tc_agent/exporter.py`: `test_cases.md`, `test_cases.xlsx`, `result.json` 저장. 엑셀 컬럼은 `TC_COLUMNS`
- `prompts/system_prompt.md`: 분석 방식과 TC 작성 규칙. 대부분의 품질 개선은 이 파일만 수정
- `specs/`, `output/`, `.env`는 커밋하지 않음 (사내 기획서와 API 키)

## 작업 환경

- 사용자는 Windows + VS Code + PowerShell에서 실행. 안내 명령은 PowerShell 기준으로 (`.venv\Scripts\Activate.ps1`, `copy`)
- 처음 설치 때 겪은 문제: `source` 미지원, 패키지 누락(`requirements.txt`로 설치), `401 invalid x-api-key`(`.env` 키 값 문제). README와 매뉴얼에 정리됨
- 예시 기획서 기준 타일 64장, 렌더링 약 3분 + 분석 수 분, 1건당 비용 몇 달러

## 이력

- 2026-10-14: `ecpapa/ds_heyAgents`의 `testcase_agent` 브랜치(`qa_tc_agent/` 폴더)에서 이 저장소로 이전. `ds_heyAgents`에는 Slack 오류 통계 에이전트만 남음
- 2026-10-15: 웹 버전(PDF 업로드 → 백그라운드 처리 → 완료 시 다운로드) 검토 시작. 아직 코드는 만들지 않음

## 진행 중: 웹 버전 검토

검토 문서: https://claude.ai/code/artifact/4ae51dc9-00e6-4109-962f-210da0b786d5

구상한 구조: 업로드 화면 → 대기열(한 번에 1건) → 백그라운드 작업자(`load_spec` → `generate` → `save_all` 재사용) → 작업 폴더(상태 + 결과 파일) → 작업 목록 화면(상태, 다운로드).
코드에서 손볼 점은 진행 상황이 `print`로만 나오는 부분.

아직 정하지 않은 것 (만들기 전에 사용자에게 확인):

1. 누가 쓰는지와 실행 위치 (내 PC / 항상 켜둔 PC / 사내 서버)
2. 접근 권한 (없음 / 공용 비밀번호 / 사람별 로그인)
3. 비용 통제 (업로드 후 타일 수·예상 비용을 보여주고 확인 버튼으로 시작하는 2단계 방식 권장)
4. 완료 알림 (목록만 / 메일 / 슬랙)
5. 보관 기간 (예: 30일 후 자동 삭제)

웹 대신 `--watch` + 공유 폴더로 쓰는 대안도 함께 제시한 상태.
