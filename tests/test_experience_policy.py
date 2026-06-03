from __future__ import annotations

from focas_experience.report import _experience_level, _mainline_effect


def test_experience_levels_follow_usage_boundaries() -> None:
    assert _experience_level(
        distribution_sample_count=5,
        exact_interval_sample_count=5,
        direction_hit_rate=0.7,
        logic_hit_rate=0.7,
        counterexample_rate=0.2,
    ) == "A"
    assert _experience_level(
        distribution_sample_count=5,
        exact_interval_sample_count=4,
        direction_hit_rate=0.6,
        logic_hit_rate=0.6,
        counterexample_rate=0.4,
    ) == "B"
    assert _experience_level(
        distribution_sample_count=3,
        exact_interval_sample_count=1,
        direction_hit_rate=0.4,
        logic_hit_rate=None,
        counterexample_rate=0.7,
    ) == "C"
    assert _experience_level(
        distribution_sample_count=0,
        exact_interval_sample_count=0,
        direction_hit_rate=1.0,
        logic_hit_rate=1.0,
        counterexample_rate=0.0,
    ) == "D"


def test_a_level_only_assists_p8_and_never_decides_direction_alone() -> None:
    effect = _mainline_effect("A")
    assert "P8 第二阶段相对主线选择" in effect
    assert "不得单独决定最终方向" in effect
