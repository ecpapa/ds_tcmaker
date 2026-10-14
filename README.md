# 기획서 → 블랙박스 테스트 케이스 생성 에이전트

피그마에서 내보낸 기획서(PDF/이미지)를 `specs/` 폴더에 넣으면, Claude가 기획 로직을 분석해
`output/` 폴더에 블랙박스 테스트 케이스를 만들어 줍니다.

```
specs/생활비지원이벤트.pdf
        │  ① 보드를 글자가 읽히는 크기의 타일로 자름 (빈 여백은 제외)
        ▼
   타일 이미지 + 텍스트 레이어
        │  ② Claude가 prompts/system_prompt.md 의 프레임워크로 분석
        ▼
output/생활비지원이벤트/
   ├─ test_cases.md    분석 리포트([image_analysis]) + TC 표 + 기획 확인 필요 사항
   ├─ test_cases.xlsx  TC 시트(결과 P/F, 비고 칸 포함) + 기획확인필요 시트
   └─ result.json      원본 결과 (다른 도구로 넘길 때 사용)
```

## 1. 설치 (VS Code 터미널)

**Windows (PowerShell)**

```powershell
git clone https://github.com/ecpapa/ds_tcmaker.git
cd ds_tcmaker
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env           # .env 를 열어 ANTHROPIC_API_KEY 입력
```

**macOS / Linux**

```bash
git clone https://github.com/ecpapa/ds_tcmaker.git
cd ds_tcmaker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # .env 를 열어 ANTHROPIC_API_KEY 입력
```

> PowerShell에서 "스크립트를 실행할 수 없습니다" 오류가 나면 한 번만
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 를 실행하세요.
>
> `401 invalid x-api-key` 오류가 나면 `.env`의 키 앞뒤에 공백·따옴표가 없는지,
> Windows 시스템 환경 변수에 예전 `ANTHROPIC_API_KEY`가 남아 있지 않은지 확인하세요.

VS Code에서는 실행/디버그(F5) 메뉴에 `TC 생성`, `폴더 감시`, `dry-run` 구성이 준비되어 있습니다.

## 2. 실행

```bash
python main.py --dry-run         # API 호출 없이 타일만 만들어 output/<파일명>/tiles 에서 확인
python main.py                   # specs/ 의 새 기획서를 처리
python main.py --watch           # specs/ 폴더를 감시하다가 파일이 들어오면 자동 처리
python main.py specs/a.pdf --force   # 특정 파일을 다시 생성
```

| 옵션 | 설명 |
|---|---|
| `--effort` | `low`~`max`. 기본 `high`. 높을수록 꼼꼼하지만 느리고 비쌈 |
| `--tile-pt` | 타일 크기(기본 1600pt). 글자가 작아 잘 안 읽히면 줄이고, 타일이 100장을 넘으면 키우세요 |
| `--save-tiles` | 실제 실행 때도 타일 이미지를 저장 |

## 3. 프롬프트 수정

분석 방식과 TC 작성 규칙은 `prompts/system_prompt.md`에 있습니다. 코드 수정 없이 이 파일만 고치면 됩니다.
결과 항목(컬럼)을 바꾸고 싶다면 `tc_agent/schema.py`와 `tc_agent/exporter.py`의 `TC_COLUMNS`를 함께 고치세요.

## 참고

- 피그마 보드 PDF는 그림자 같은 효과 때문에 렌더링이 느립니다. 예시 기획서(32,638×6,652pt)는 4코어 기준 약 3분 걸립니다.
- 한 번 실행에 타일 수십 장이 들어가므로 비용은 기획서 1건당 대략 몇 달러 수준입니다. 먼저 `--dry-run`으로 타일 수를 확인하세요.
- `specs/`와 `output/`은 `.gitignore`에 들어 있어 기획서가 커밋되지 않습니다.
