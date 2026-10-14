"""specs/ 폴더의 기획서를 읽어 output/ 폴더에 블랙박스 테스트 케이스를 생성한다.

사용법:
    python main.py                 # specs/ 안의 새 파일을 한 번 처리
    python main.py --watch         # specs/ 폴더를 지켜보다가 파일이 들어오면 처리
    python main.py --dry-run       # API 호출 없이 타일 이미지만 만들어서 확인
    python main.py specs/a.pdf     # 특정 파일만 처리
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from tc_agent.loader import SUPPORTED_EXT, TILE_PT, load_spec

ROOT = Path(__file__).resolve().parent
SPECS_DIR = ROOT / "specs"
OUTPUT_DIR = ROOT / "output"


def find_specs(force: bool) -> list[Path]:
    files = sorted(p for p in SPECS_DIR.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXT)
    if force:
        return files
    return [p for p in files if not (OUTPUT_DIR / p.stem / "test_cases.md").exists()]


def process(path: Path, args: argparse.Namespace) -> bool:
    print(f"\n▶ {path.name}")
    doc = load_spec(path, tile_pt=args.tile_pt)
    print(f"  - 타일 {len(doc.tiles)}장 (빈 영역 {doc.skipped_blank}장 제외)")
    out_dir = OUTPUT_DIR / path.stem

    if args.dry_run or args.save_tiles:
        tile_dir = out_dir / "tiles"
        tile_dir.mkdir(parents=True, exist_ok=True)
        for tile in doc.tiles:
            (tile_dir / f"{tile.label}.png").write_bytes(tile.png)
        print(f"  - 타일 이미지 저장: {tile_dir}")
    if args.dry_run:
        return True

    # API 키가 필요한 모듈은 실제 호출할 때만 불러온다
    from tc_agent.exporter import save_all
    from tc_agent.generator import GenerationError, generate

    print(f"  - Claude 분석 중 (effort={args.effort}, 기획서 크기에 따라 수 분 걸릴 수 있어요)")
    try:
        suite = generate(doc, effort=args.effort)
    except GenerationError as e:
        print(f"  ✗ 실패: {e}")
        return False
    for f in save_all(suite, out_dir, title=path.stem):
        print(f"  ✓ {f.relative_to(ROOT)}")
    print(f"  - TC {len(suite.test_cases)}건, 기획 확인 필요 {len(suite.open_questions)}건")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="기획서 → 블랙박스 테스트 케이스 생성 에이전트")
    parser.add_argument("files", nargs="*", type=Path, help="처리할 파일 (생략하면 specs/ 폴더 전체)")
    parser.add_argument("--watch", action="store_true", help="specs/ 폴더를 계속 감시")
    parser.add_argument("--interval", type=int, default=5, help="감시 주기(초)")
    parser.add_argument("--force", action="store_true", help="이미 처리한 파일도 다시 생성")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 타일만 생성")
    parser.add_argument("--save-tiles", action="store_true", help="타일 이미지도 output/에 저장")
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--tile-pt", type=float, default=TILE_PT,
                        help="타일 하나의 크기(pt). 글자가 작으면 줄이세요 (타일 수는 늘어남)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    SPECS_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    if args.files:
        for f in args.files:
            process(f, args)
        return 0

    if not args.watch:
        targets = find_specs(args.force)
        if not targets:
            print(f"처리할 새 기획서가 없어요. {SPECS_DIR.relative_to(ROOT)}/ 폴더에 PDF나 이미지를 넣어주세요.")
        for f in targets:
            process(f, args)
        return 0

    print(f"👀 {SPECS_DIR.relative_to(ROOT)}/ 폴더 감시 중... (종료: Ctrl+C)")
    seen_sizes: dict[Path, int] = {}
    failed: set[Path] = set()  # 실패한 파일은 API 비용이 반복되지 않게 다시 시도하지 않는다
    try:
        while True:
            for f in find_specs(force=False):
                if f in failed:
                    continue
                # 복사가 끝날 때까지 기다린다: 두 번 연속 크기가 같을 때만 처리
                size = f.stat().st_size
                if seen_sizes.get(f) == size:
                    if not process(f, args):
                        failed.add(f)
                    seen_sizes.pop(f, None)
                else:
                    seen_sizes[f] = size
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n종료합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
