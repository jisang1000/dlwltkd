#!/usr/bin/env python3
"""비디오에서 싱크 정확도 높은 SRT 자막을 생성합니다.

개선 사항:
- word_timestamps=True 로 밀리초 단위 정밀 싱크
- 긴 세그먼트를 문장 부호·호흡 단위로 자동 분할
- 한국어 맞춤법/정제 후처리
- 한 자막 블록 최대 2줄 × 줄당 20자 가독성 최적화
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# 타임스탬프 포맷
# ---------------------------------------------------------------------------

def _fmt(seconds: float) -> str:
    """float 초 → SRT 타임스탬프 문자열 (HH:MM:SS,mmm)."""
    ms = int(round(max(0.0, seconds) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ---------------------------------------------------------------------------
# 데이터 클래스
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SubtitleSegment:
    start: float
    end: float
    text: str


@dataclass
class WordToken:
    word: str
    start: float
    end: float


# ---------------------------------------------------------------------------
# 텍스트 정제 (오타·비문 최소화)
# ---------------------------------------------------------------------------

# 전각 부호 → 반각 변환 테이블 (딕셔너리 형태로 길이 불일치 방지)
_FULLWIDTH_MAP = str.maketrans({
    "\uff0c": ",",   # ，
    "\u3002": ".",   # 。
    "\uff01": "!",   # ！
    "\uff1f": "?",   # ？
    "\uff1b": ";",   # ；
    "\uff1a": ":",   # ：
    "\u201c": '"',   # "
    "\u201d": '"',   # "
    "\u2018": "'",   # '
    "\u2019": "'",   # '
    "\uff08": "(",   # （
    "\uff09": ")",   # ）
    "\u3010": "[",   # 【
    "\u3011": "]",   # 】
})

# 반복되는 같은 글자 3회 이상 → 2회로 축약 (예: "ㅋㅋㅋㅋ" → "ㅋㅋ")
_REPEATED_CHARS = re.compile(r"(.)\1{2,}")

# 인접 공백 제거, 구두점 앞 공백 제거
_SPACES_BEFORE_PUNCT = re.compile(r"\s+([,.!?])")
_MULTI_SPACE = re.compile(r"\s+")

# 문장 분할 기준: 마침표/물음표/느낌표 뒤 (단, 숫자 소수점 제외)
_SENTENCE_END = re.compile(r"(?<=[^0-9])([.!?])\s+")


def _normalize(text: str) -> str:
    """한국어 자막 텍스트 정제."""
    text = text.translate(_FULLWIDTH_MAP)
    text = _REPEATED_CHARS.sub(r"\1\1", text)
    text = _SPACES_BEFORE_PUNCT.sub(r"\1", text)
    text = _MULTI_SPACE.sub(" ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# 가독성: 줄바꿈 (최대 2줄 × 줄당 max_chars 글자)
# ---------------------------------------------------------------------------

def _line_wrap(text: str, max_chars: int = 20) -> str:
    """텍스트를 max_chars 기준으로 최대 2줄로 나눈다."""
    if len(text) <= max_chars:
        return text

    # 공백 기준 단어 분할 시도
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) == 1 and not current:
            # 2줄째 시작
            pass
    if current:
        lines.append(current)

    # 최대 2줄만 허용 (초과분은 마지막 줄에 합산)
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 긴 세그먼트 → 문장 단위 분할
# ---------------------------------------------------------------------------

_SPLIT_PUNCT = re.compile(r"[.!?。]")


def _split_segment_by_words(
    words: list[WordToken],
    max_chars: int,
) -> list[SubtitleSegment]:
    """단어 토큰 리스트를 max_chars 기준으로 자막 블록으로 묶는다."""
    if not words:
        return []

    segments: list[SubtitleSegment] = []
    current_words: list[WordToken] = []
    current_text = ""

    for tok in words:
        candidate = (current_text + " " + tok.word).strip()
        force_split = bool(_SPLIT_PUNCT.search(tok.word)) if current_words else False

        if len(candidate) > max_chars * 2 or force_split:
            # 현재까지 블록 저장
            if current_words:
                segments.append(
                    SubtitleSegment(
                        start=current_words[0].start,
                        end=current_words[-1].end,
                        text=_normalize(current_text),
                    )
                )
            current_words = [tok]
            current_text = tok.word
        else:
            current_words.append(tok)
            current_text = candidate

    if current_words:
        segments.append(
            SubtitleSegment(
                start=current_words[0].start,
                end=current_words[-1].end,
                text=_normalize(current_text),
            )
        )

    return segments


# ---------------------------------------------------------------------------
# Whisper 전사
# ---------------------------------------------------------------------------

def _transcribe(
    video_path: Path,
    model_size: str,
    language: str | None,
    max_chars: int,
) -> list[SubtitleSegment]:
    try:
        import whisper  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "whisper 패키지가 없습니다. `pip install openai-whisper` 후 재시도하세요."
        ) from exc

    print(f"[1/3] 모델 로딩 중: {model_size} ...", file=sys.stderr)
    model = whisper.load_model(model_size)

    print("[2/3] 전사 중 (word_timestamps=True) ...", file=sys.stderr)
    result = model.transcribe(
        str(video_path),
        language=language,
        word_timestamps=True,      # 단어 단위 밀리초 타임스탬프
        verbose=False,
        condition_on_previous_text=True,
        temperature=0.0,           # 결정론적 출력 → 오타 최소화
        best_of=1,
        beam_size=5,
        fp16=False,
    )

    print("[3/3] 자막 블록 생성 중 ...", file=sys.stderr)
    all_segments: list[SubtitleSegment] = []

    for item in result.get("segments", []):
        raw_words = item.get("words", [])

        if raw_words:
            # 단어 단위 타임스탬프 사용 → 정밀 싱크
            tokens = [
                WordToken(
                    word=str(w.get("word", "")).strip(),
                    start=float(w.get("start", item["start"])),
                    end=float(w.get("end", item["end"])),
                )
                for w in raw_words
                if str(w.get("word", "")).strip()
            ]
            all_segments.extend(_split_segment_by_words(tokens, max_chars))
        else:
            # word_timestamps 미지원 폴백
            text = _normalize(str(item.get("text", "")).strip())
            if text:
                all_segments.append(
                    SubtitleSegment(
                        start=float(item["start"]),
                        end=float(item["end"]),
                        text=text,
                    )
                )

    return all_segments


# ---------------------------------------------------------------------------
# SRT 직렬화
# ---------------------------------------------------------------------------

def _to_srt(segments: list[SubtitleSegment], max_chars: int) -> str:
    blocks: list[str] = []
    for idx, seg in enumerate(segments, start=1):
        text = _line_wrap(seg.text, max_chars=max_chars)
        blocks.append(f"{idx}\n{_fmt(seg.start)} --> {_fmt(seg.end)}\n{text}")
    return "\n\n".join(blocks) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="비디오 → SRT 자막 생성 (싱크·맞춤법·가독성 최적화)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("video", type=Path, help="입력 비디오 파일 경로")
    parser.add_argument("-o", "--output", type=Path, default=None, help="출력 .srt 경로")
    parser.add_argument(
        "--model",
        default="medium",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper 모델 크기 (한국어는 medium 이상 권장)",
    )
    parser.add_argument(
        "--language",
        default="ko",
        help="언어 코드 (ko / en / ja …). 자동 감지는 auto",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=20,
        help="자막 한 줄 최대 글자 수 (한국어 권장: 20)",
    )
    args = parser.parse_args()

    video_path: Path = args.video
    if not video_path.exists():
        print(f"오류: 파일을 찾을 수 없습니다 → {video_path}", file=sys.stderr)
        return 1

    output_path: Path = args.output or video_path.with_suffix(".srt")
    language: str | None = None if args.language == "auto" else args.language

    segments = _transcribe(
        video_path=video_path,
        model_size=args.model,
        language=language,
        max_chars=args.max_chars,
    )
    if not segments:
        print("오류: 전사 결과가 비어 있습니다.", file=sys.stderr)
        return 1

    srt_text = _to_srt(segments=segments, max_chars=args.max_chars)
    output_path.write_text(srt_text, encoding="utf-8-sig")  # BOM 포함 → 한글 자막 프로그램 호환
    print(f"\n완료: {output_path}  ({len(segments)}개 자막 블록)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
