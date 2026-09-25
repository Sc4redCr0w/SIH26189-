from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassificationMetrics:
    precision: float
    recall: float
    f1: float
    true_positive: int
    false_positive: int
    false_negative: int

    @classmethod
    def from_counts(cls, true_positive: int, false_positive: int, false_negative: int) -> "ClassificationMetrics":
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return cls(precision, recall, f1, true_positive, false_positive, false_negative)


def classification_metrics(expected: set[str], predicted: set[str]) -> ClassificationMetrics:
    return ClassificationMetrics.from_counts(len(expected & predicted), len(predicted - expected), len(expected - predicted))


def merge_metrics(expected_merges: set[tuple[str, str]], predicted_merges: set[tuple[str, str]]) -> dict[str, float | int]:
    true_positive = len(expected_merges & predicted_merges)
    false_positive = len(predicted_merges - expected_merges)
    false_negative = len(expected_merges - predicted_merges)
    return {
        "correct_merges": true_positive,
        "false_merges": false_positive,
        "false_non_merges": false_negative,
        "correct_merge_rate": true_positive / len(expected_merges) if expected_merges else 0.0,
        "false_merge_rate": false_positive / len(predicted_merges) if predicted_merges else 0.0,
    }
