"""scripts/transcribe_to_srt.py 의 순수 함수 단위 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

# scripts 디렉터리를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from transcribe_to_srt import (  # type: ignore[import]
    SubtitleSegment,
    WordToken,
    _fmt,
    _line_wrap,
    _normalize,
    _split_segment_by_words,
    _to_srt,
)


# ---------------------------------------------------------------------------
# _fmt
# ---------------------------------------------------------------------------

def test_fmt_zero():
    assert _fmt(0.0) == "00:00:00,000"


def test_fmt_normal():
    assert _fmt(3723.456) == "01:02:03,456"


def test_fmt_negative_clamped():
    assert _fmt(-1.0) == "00:00:00,000"


def test_fmt_non_round_millis():
    # 62.123 → 1분 2초 123ms
    assert _fmt(62.123) == "00:01:02,123"


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------

def test_normalize_strips_spaces():
    assert _normalize("  안녕  하세요  ") == "안녕 하세요"


def test_normalize_fullwidth_punct():
    assert _normalize("좋아요，정말") == "좋아요,정말"


def test_normalize_space_before_punct():
    assert _normalize("안녕 .") == "안녕."


def test_normalize_repeated_chars():
    # ㅋ 4회 → 2회
    assert _normalize("ㅋㅋㅋㅋ재밌다") == "ㅋㅋ재밌다"


# ---------------------------------------------------------------------------
# _line_wrap
# ---------------------------------------------------------------------------

def test_line_wrap_short_unchanged():
    text = "짧은 텍스트"
    assert _line_wrap(text, max_chars=20) == text


def test_line_wrap_splits():
    text = "이것은 정말 긴 자막 텍스트로 두 줄로 나눠야 합니다"
    result = _line_wrap(text, max_chars=15)
    assert "\n" in result
    lines = result.split("\n")
    assert len(lines) <= 2


def test_line_wrap_max_two_lines():
    text = "가 나 다 라 마 바 사 아 자 차 카 타 파 하"
    result = _line_wrap(text, max_chars=6)
    assert result.count("\n") <= 1


# ---------------------------------------------------------------------------
# _split_segment_by_words
# ---------------------------------------------------------------------------

def test_split_segment_by_words_basic():
    tokens = [
        WordToken("안녕하세요.", 0.0, 0.5),
        WordToken("반갑습니다.", 0.6, 1.2),
        WordToken("좋은", 1.3, 1.5),
        WordToken("하루", 1.5, 1.8),
        WordToken("되세요.", 1.8, 2.2),
    ]
    segs = _split_segment_by_words(tokens, max_chars=20)
    assert len(segs) >= 1
    # 첫 번째 세그먼트 시작 시각
    assert segs[0].start == 0.0


def test_split_segment_empty():
    assert _split_segment_by_words([], max_chars=20) == []


def test_split_segment_timestamps_monotone():
    tokens = [WordToken(f"단어{i}.", float(i), float(i) + 0.4) for i in range(5)]
    segs = _split_segment_by_words(tokens, max_chars=10)
    for a, b in zip(segs, segs[1:]):
        assert a.end <= b.start + 0.001  # 끝 ≤ 다음 시작 (허용 오차 1ms)


# ---------------------------------------------------------------------------
# _to_srt
# ---------------------------------------------------------------------------

def test_to_srt_format():
    segs = [SubtitleSegment(start=1.0, end=2.5, text="안녕하세요.")]
    srt = _to_srt(segs, max_chars=20)
    lines = srt.strip().splitlines()
    assert lines[0] == "1"
    assert "00:00:01,000 --> 00:00:02,500" in lines[1]
    assert lines[2] == "안녕하세요."


def test_to_srt_multiple_blocks():
    segs = [
        SubtitleSegment(0.0, 1.0, "첫 번째"),
        SubtitleSegment(1.5, 2.5, "두 번째"),
    ]
    srt = _to_srt(segs, max_chars=20)
    assert srt.count("\n\n") == 1
    assert "1\n" in srt
    assert "2\n" in srt


def test_to_srt_bom_not_in_string():
    # _to_srt 자체는 BOM 없이 문자열 반환 (BOM은 파일 저장 시 추가)
    segs = [SubtitleSegment(0.0, 1.0, "테스트")]
    srt = _to_srt(segs, max_chars=20)
    assert not srt.startswith("\ufeff")
