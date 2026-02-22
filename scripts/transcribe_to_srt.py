#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


def _format_srt_timestamp(seconds: float) -> str:
    safe_seconds = max(0.0, seconds)
    total_milliseconds = int(round(safe_seconds * 1000))
    hours, rem = divmod(total_milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


@dataclass(slots=True)
class SubtitleSegment:
    start: float
    end: float
    text: str


def _normalize_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"\s+([,.!?])", r"\1", cleaned)
    return cleaned


def _line_wrap(text: str, max_chars: int) -> str:
    words = text.split(" ")
    if not words:
        return ""

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        lines.append(current)
        current = word
    lines.append(current)
    return "\n".join(lines)


def _to_srt(segments: list[SubtitleSegment], max_chars: int) -> str:
    blocks: list[str] = []
    for idx, seg in enumerate(segments, start=1):
        start = _format_srt_timestamp(seg.start)
        end = _format_srt_timestamp(seg.end)
        text = _line_wrap(_normalize_text(seg.text), max_chars=max_chars)
        blocks.append(f"{idx}\n{start} --> {end}\n{text}")
    return "\n\n".join(blocks) + "\n"


def _transcribe(video_path: Path, model_size: str, language: str | None) -> list[SubtitleSegment]:
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError(
            "whisper 패키지가 설치되어 있지 않습니다. `pip install openai-whisper` 후 다시 시도하세요."
        ) from exc

    model = whisper.load_model(model_size)
    result = model.transcribe(str(video_path), language=language)

    segments: list[SubtitleSegment] = []
    for item in result.get("segments", []):
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        segments.append(
            SubtitleSegment(
                start=float(item["start"]),
                end=float(item["end"]),
                text=text,
            )
        )
    return segments


def main() -> int:
    parser = argparse.ArgumentParser(description="비디오에서 SRT 자막 생성")
    parser.add_argument("video", type=Path, help="입력 비디오 파일 경로")
    parser.add_argument("-o", "--output", type=Path, default=None, help="출력 SRT 경로")
    parser.add_argument("--model", default="small", help="Whisper 모델 크기 (tiny/base/small/medium/large)")
    parser.add_argument("--language", default="ko", help="언어 코드 (예: ko, en). 자동 감지는 auto")
    parser.add_argument("--max-chars", type=int, default=22, help="줄바꿈 최대 글자 수")
    args = parser.parse_args()

    video_path: Path = args.video
    if not video_path.exists():
        raise FileNotFoundError(f"입력 비디오 파일을 찾을 수 없습니다: {video_path}")

    output_path = args.output or video_path.with_suffix(".srt")
    language = None if args.language == "auto" else args.language

    segments = _transcribe(video_path=video_path, model_size=args.model, language=language)
    if not segments:
        raise RuntimeError("전사 결과가 비어 있습니다.")

    srt = _to_srt(segments=segments, max_chars=args.max_chars)
    output_path.write_text(srt, encoding="utf-8")
    print(f"SRT 생성 완료: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
