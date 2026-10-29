from app.chat.reconciler import compose_answer


def _verdict(status: str) -> dict:
    return {
        "status": status,
        "policy": "制度要求 ≤2 小时",
        "data": "实际平均 3.4 小时",
        "explanation": "实际超出制度要求",
    }


def test_violation_presents_both_sources_and_keeps_both():
    text = compose_answer(_verdict("violation"))
    assert "制度要求" in text
    assert "实际数据" in text
    assert "未达到制度要求" in text
    assert "未做取舍" in text


def test_conflict_is_labelled_explicitly():
    text = compose_answer(_verdict("conflict"))
    assert "冲突" in text
    assert "未做取舍" in text


def test_insufficient_does_not_claim_conclusion():
    text = compose_answer(_verdict("insufficient"))
    assert "无法直接比对" in text
    assert "未做取舍" not in text
