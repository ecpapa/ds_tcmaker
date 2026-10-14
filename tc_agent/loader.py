"""기획서 파일(PDF/이미지/텍스트)을 Claude에 보낼 타일 이미지 + 텍스트로 바꾼다.

피그마에서 내보낸 PDF는 보드 전체가 한 페이지(예: 32,638 x 6,652pt)로 들어오는 경우가 많다.
통째로 보내면 글자가 뭉개지므로, 글자가 읽히는 해상도로 겹치게 잘라서 보낸다.
"""

from __future__ import annotations

import base64
import math
import os
import re
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

PDF_EXT = {".pdf"}
IMAGE_EXT = {".png", ".jpg", ".jpeg"}  # PyMuPDF는 webp를 열지 못한다
TEXT_EXT = {".md", ".txt"}
SUPPORTED_EXT = PDF_EXT | IMAGE_EXT | TEXT_EXT

# Claude가 이미지를 축소하지 않고 보는 긴 변 기준 (px)
MAX_EDGE_PX = 1568
# 타일 하나가 덮는 영역 (pt). 1600pt를 1568px로 렌더링하면 약 1px/pt 로 피그마 본문 글자가 읽힌다.
TILE_PT = 1600
OVERLAP = 0.1
# 한 색이 이 비율 이상이면 빈 배경 타일로 보고 건너뛴다
BLANK_RATIO = 0.985
# 텍스트가 없고 PNG가 이보다 작으면(=단색 면 몇 개뿐) 섹션 사이 여백으로 보고 건너뛴다
FLAT_PNG_BYTES = 16_000

# 일부 피그마 폰트는 한글이 "˝Ýí" 같은 라틴 확장 문자로 깨져서 추출된다
_GARBLED = re.compile(r"[\u0080-\u02ff\ufb00-\ufb06\ufffd]")
_MEANINGFUL = re.compile(r"[\uac00-\ud7a3]|[A-Za-z0-9]{2,}")


@dataclass
class Tile:
    label: str
    png: bytes
    region: str
    text: str = ""

    @property
    def b64(self) -> str:
        return base64.standard_b64encode(self.png).decode()


@dataclass
class SpecDocument:
    path: Path
    tiles: list[Tile] = field(default_factory=list)
    text: str = ""
    skipped_blank: int = 0


def _clean_text(raw: str) -> str:
    """인코딩이 깨진 줄은 버리고, 한글이나 영문/숫자 단어가 있는 줄만 남긴다."""
    lines = []
    for line in raw.splitlines():
        s = " ".join(line.split())
        if s and not _GARBLED.search(s) and _MEANINGFUL.search(s):
            lines.append(s)
    return "\n".join(lines)


def _words_in(words: list[tuple], clip: tuple[float, float, float, float]) -> str:
    """페이지 전체에서 한 번 뽑은 단어 목록 중 clip 안에 중심이 있는 단어만 줄 단위로 모은다."""
    x0, y0, x1, y1 = clip
    lines: dict[tuple[int, int], list[str]] = {}
    for wx0, wy0, wx1, wy1, word, block, line, _ in words:
        if x0 <= (wx0 + wx1) / 2 < x1 and y0 <= (wy0 + wy1) / 2 < y1:
            lines.setdefault((block, line), []).append(word)
    return "\n".join(" ".join(ws) for ws in lines.values())


def _is_blank(pix: pymupdf.Pixmap) -> bool:
    ratio, _ = pix.color_topusage()
    return ratio >= BLANK_RATIO


_worker_page: pymupdf.Page | None = None


def _init_worker(path: str, page_index: int) -> None:
    global _worker_page
    _worker_page = pymupdf.open(path)[page_index]


def _render(clip: tuple[float, float, float, float], zoom: float, page: pymupdf.Page | None = None) -> bytes | None:
    pix = (page or _worker_page).get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=pymupdf.Rect(clip), alpha=False)
    return None if _is_blank(pix) else pix.tobytes("png")


def _tile_page(page: pymupdf.Page, page_no: int, doc: SpecDocument, tile_pt: float,
               src_path: Path | None = None) -> None:
    rect = page.rect
    zoom = MAX_EDGE_PX / tile_pt
    step = tile_pt * (1 - OVERLAP)
    cols = math.ceil((rect.width - tile_pt) / step) + 1 if rect.width > tile_pt else 1
    rows = math.ceil((rect.height - tile_pt) / step) + 1 if rect.height > tile_pt else 1
    prefix = f"p{page_no}" if len(page.parent) > 1 else ""

    cells = []
    for r in range(rows):
        for c in range(cols):
            x0 = rect.x0 + min(c * step, max(rect.width - tile_pt, 0))
            y0 = rect.y0 + min(r * step, max(rect.height - tile_pt, 0))
            cells.append((r, c, (x0, y0, min(x0 + tile_pt, rect.x1), min(y0 + tile_pt, rect.y1))))

    # 피그마 보드는 그림자/블러 효과 때문에 타일 한 장에 수 초가 걸릴 수 있어 여러 프로세스로 나눠 렌더링한다
    clips = [clip for _, _, clip in cells]
    if src_path is not None and len(cells) > 1:
        workers = max(1, (os.cpu_count() or 2) - 1)
        with ProcessPoolExecutor(workers, initializer=_init_worker,
                                 initargs=(str(src_path), page.number)) as pool:
            pngs = []
            for i, png in enumerate(pool.map(_render, clips, [zoom] * len(clips)), start=1):
                pngs.append(png)
                print(f"\r  - 렌더링 {i}/{len(clips)}", end="", flush=True)
            print()
    else:
        pngs = [_render(clip, zoom, page) for clip in clips]

    words = page.get_text("words")
    for (r, c, clip), png in zip(cells, pngs):
        text = _clean_text(_words_in(words, clip)) if png else ""
        if png is None or (len(png) < FLAT_PNG_BYTES and not text):
            doc.skipped_blank += 1
            continue
        x0, y0, x1, y1 = clip
        region = (
            f"가로 {x0 / rect.width:.0%}~{x1 / rect.width:.0%}, "
            f"세로 {y0 / rect.height:.0%}~{y1 / rect.height:.0%}"
        )
        doc.tiles.append(Tile(label=f"{prefix}r{r}c{c}", png=png, region=region, text=text))


def _load_pdf(path: Path, doc: SpecDocument, tile_pt: float) -> None:
    with pymupdf.open(path) as pdf:
        for i, page in enumerate(pdf, start=1):
            longest = max(page.rect.width, page.rect.height)
            if longest <= tile_pt:
                # 일반 문서 크기 페이지는 한 장으로 렌더링
                zoom = MAX_EDGE_PX / longest
                pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
                if not _is_blank(pix):
                    doc.tiles.append(
                        Tile(
                            label=f"p{i}",
                            png=pix.tobytes("png"),
                            region=f"{i}페이지 전체",
                            text=_clean_text(page.get_text("text")),
                        )
                    )
            else:
                _tile_page(page, i, doc, tile_pt, src_path=path)


def _load_image(path: Path, doc: SpecDocument, tile_pt: float) -> None:
    # 이미지도 PDF 페이지처럼 열어서 같은 방식으로 자른다 (px를 pt처럼 취급)
    with pymupdf.open(path) as img:
        pdf = pymupdf.open("pdf", img.convert_to_pdf())
    with pdf:
        page = pdf[0]
        if max(page.rect.width, page.rect.height) <= MAX_EDGE_PX:
            doc.tiles.append(Tile(label="img", png=page.get_pixmap().tobytes("png"), region="이미지 전체"))
        else:
            _tile_page(page, 1, doc, tile_pt)


def load_spec(path: Path, tile_pt: float = TILE_PT) -> SpecDocument:
    doc = SpecDocument(path=path)
    ext = path.suffix.lower()
    if ext in PDF_EXT:
        _load_pdf(path, doc, tile_pt)
    elif ext in IMAGE_EXT:
        _load_image(path, doc, tile_pt)
    elif ext in TEXT_EXT:
        doc.text = path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {path.name}")
    return doc
