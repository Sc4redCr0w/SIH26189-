from app.evaluation import classification_metrics, merge_metrics


def test_classification_metrics_are_reproducible() -> None:
    metrics = classification_metrics({"a", "b", "c"}, {"a", "b", "x"})
    assert metrics.true_positive == 2
    assert metrics.false_positive == 1
    assert metrics.false_negative == 1
    assert metrics.precision == 2 / 3
    assert metrics.recall == 2 / 3


def test_merge_metrics_report_false_merge_rate() -> None:
    metrics = merge_metrics({("a", "b")}, {("a", "b"), ("c", "d")})
    assert metrics["correct_merges"] == 1
    assert metrics["false_merges"] == 1
    assert metrics["false_merge_rate"] == 0.5
