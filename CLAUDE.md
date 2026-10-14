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

결정 현황 (2026-10-15):

1. 사용 대상: **결정**. 같은 팀 2~3명. 사용자 PC에서 띄우고 동료는 사내망으로 `http://PC주소:8000` 접속
2. 접근 권한: **보류**. 1단계는 없이 만들되 나중에 붙일 수 있게. 동료에게 주소를 알리기 전에 다시 확인
3. 비용 통제: 제안. 렌더링 후 '확인 대기' 상태에서 타일 수를 보여주고 [분석 시작]을 눌러야 API 호출
4. 완료 알림: 제안. 1단계는 목록 화면만
5. 보관 기간: 제안. 1단계는 목록에서 직접 삭제

1단계 구현안 (검토 문서에 상세):

- FastAPI + uvicorn + 작은 HTML 한 화면. Streamlit은 작업이 브라우저 탭에 묶여서 제외
- `web/app.py`, `web/jobs.py`, `web/templates/index.html`, 작업 폴더 `jobs/<작업ID>/`(`status.json` + 결과, `.gitignore`에 추가)
- `loader.py`, `generator.py`의 `print`를 진행 상황 콜백으로 바꾸되 CLI 출력은 유지
- 상태: 대기 → 렌더링 중 → 확인 대기 → 분석 중 → 완료 / 실패·중단됨([다시 시작]으로 대기열 복귀, 자동 재시도 없음)
- Windows에서 렌더링 다중 프로세스가 모듈을 다시 import하므로 작업자 스레드는 서버 시작 시에만 띄움
- 1건당 실제 비용은 아직 모름. 작업별 토큰 사용량을 기록해 예상 비용 표시에 사용

웹 대신 `--watch` + 공유 폴더로 쓰는 대안도 문서에 남아 있음.
