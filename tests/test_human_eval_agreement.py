from src.tender_metrics.human_eval import cohen_kappa, percent_agreement, summarize_rater_pair


def test_cohen_kappa_perfect_and_chance():
    assert cohen_kappa([1, 1, 0, 0], [1, 1, 0, 0]) == 1.0
    # Equal marginals, no agreement beyond labels imbalance -> low/zero kappa path covered
    assert percent_agreement([1, 0, 1, 0], [1, 0, 0, 1]) == 0.5


def test_summarize_rater_pair():
    sheets_a = [
        {"case_id": "CASE-1", "package_id": "design_package", "scores": {"BP1": 2, "BP2": 1, "BP3": 1, "BP4": 2, "BP5": 1}},
        {"case_id": "CASE-2", "package_id": "design_package", "scores": {"BP1": 1, "BP2": 1, "BP3": 0, "BP4": 1, "BP5": 1}},
    ]
    sheets_b = [
        {"case_id": "CASE-1", "package_id": "design_package", "scores": {"BP1": 2, "BP2": 1, "BP3": 2, "BP4": 2, "BP5": 1}},
        {"case_id": "CASE-2", "package_id": "design_package", "scores": {"BP1": 1, "BP2": 0, "BP3": 0, "BP4": 1, "BP5": 1}},
    ]
    summary = summarize_rater_pair(sheets_a, sheets_b)
    assert summary["shared_packets"] == 2
    assert summary["per_dimension"]["BP1"]["percent_agreement"] == 1.0
    assert summary["per_dimension"]["BP1"]["cohen_kappa"] == 1.0
