"""google_docs.push 변환 테스트 (네트워크 없음, 가짜 API). author: Mal-Mi-Jal"""
import pytest

from server.model.docs import load_seed
from server.ops.engine import apply_op, revert_diff
from server.sync import google_docs as gd


class FakeReq:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class FakeDocsApi:
    """기존 탭 'Tab 1'(사람이 쓴 계획서)만 있는 문서."""

    def __init__(self):
        self.tabs = [{"tabProperties": {"tabId": "t.0", "title": "Tab 1"},
                      "documentTab": {"body": {"content": [{"endIndex": 264}]}}}]
        self.batches: list[list[dict]] = []
        self.gets = 0

    def get(self, documentId, includeTabsContent=False, fields=None):
        self.gets += 1
        return FakeReq({"tabs": self.tabs})

    def batchUpdate(self, documentId, body):
        reqs = body["requests"]
        if "addDocumentTab" in reqs[0]:
            tid = f"t.new{len(self.tabs)}"
            self.tabs.append({"tabProperties": {"tabId": tid, "title": reqs[0]["addDocumentTab"]["tabProperties"]["title"]},
                              "documentTab": {"body": {"content": [{"endIndex": 2}]}}})
            return FakeReq({"replies": [{"addDocumentTab": {"tabProperties": {"tabId": tid}}}]})
        self.batches.append(reqs)
        # 다음 조회 때 탭 길이가 맞게: 넣은 글 길이 + 마지막 줄바꿈
        ins = next((r["insertText"] for r in reqs if "insertText" in r), None)
        if ins:
            tab = next(t for t in self.tabs if t["tabProperties"]["tabId"] == ins["location"]["tabId"])
            tab["documentTab"]["body"]["content"] = [{"endIndex": 1 + gd._u16(ins["text"]) + 1}]
        return FakeReq({})


@pytest.fixture
def api(monkeypatch):
    fake = FakeDocsApi()
    monkeypatch.setenv("GOOGLE_DOC_ID", "https://docs.google.com/document/d/DOC_ID/edit?tab=t.0")
    monkeypatch.setattr(gd, "_api", lambda: fake)
    gd._tabs.clear()
    gd._item_who.clear()
    gd._tab_end.clear()
    return fake


def _change(state, ops, cid="ch_1", who="Ines"):
    diff = []
    for op in ops:
        diff += apply_op(state, op)
    return {"change_id": cid, "requested_by": who, "reason": f"{who}: x", "ops": ops, "diff": diff}


def _all_tab_ids(reqs):
    out = set()
    for r in reqs:
        body = next(iter(r.values()))
        rng = body.get("range") or body.get("location") or {}
        out.add(rng.get("tabId"))
    return out


def test_creates_own_tab_and_never_touches_existing(api):
    s = load_seed("sprint")
    gd.push_all(s)
    assert [t["tabProperties"]["title"] for t in api.tabs] == ["Tab 1", "회의 노트"]
    assert _all_tab_ids(api.batches[-1]) == {"t.new1"}  # 기존 Tab 1(t.0)에는 요청 없음
    text = next(r["insertText"]["text"] for r in api.batches[-1] if "insertText" in r)
    assert text.startswith("결정 사항\n(없음)\n리스크")
    assert "Public App Store / Play Store release" in text


def test_applied_highlight_who_then_revert(api):
    s = load_seed("sprint")
    gd.push_all(s)
    ch = _change(s, [{"op": "add_decision", "text": "출시 연기 🚀"}])
    gd.push(s, "change.applied", ch)
    reqs = api.batches[-1]
    assert reqs[0]["deleteContentRange"]["range"]["endIndex"] > 2  # 이전 내용 지우고
    text = next(r["insertText"]["text"] for r in reqs if "insertText" in r)
    assert "출시 연기 🚀  · Ines" in text
    hl = [r for r in reqs if "updateTextStyle" in r and "backgroundColor" in r["updateTextStyle"]["textStyle"]]
    assert len(hl) == 1
    # 하이라이트 범위가 UTF-16 기준으로 그 항목 줄과 정확히 맞는지
    rng = hl[0]["updateTextStyle"]["range"]
    line = "출시 연기 🚀  · Ines"
    start = 1 + gd._u16(text[: text.index(line)])
    assert (rng["startIndex"], rng["endIndex"]) == (start, start + gd._u16(line))

    revert_diff(s, ch["diff"])
    gd.push(s, "change.reverted", ch)
    text = next(r["insertText"]["text"] for r in api.batches[-1] if "insertText" in r)
    assert "출시 연기" not in text and gd._item_who == {}


def test_sheet_only_change_skips_docs(api):
    s = load_seed("sprint")
    gd.push(s, "change.applied", _change(s, [{"op": "set_cell", "doc": "board", "row": "r_pay423", "column": "추정", "value": 3}]))
    assert api.batches == []


def test_push_skips_lookup_after_first_write(api):
    s = load_seed("sprint")
    gd.push_all(s)
    gets = api.gets
    gd.push(s, "change.applied", _change(s, [{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "리스크 하나"}]))
    gd.push(s, "change.applied", _change(s, [{"op": "add_decision", "text": "결정 하나"}], cid="ch_2"))
    assert api.gets == gets  # 조회 없이 batchUpdate만
    # 기억한 길이가 실제 탭 길이(가짜 API가 계산)와 같아야 지우기 범위가 맞다
    tab = next(t for t in api.tabs if t["tabProperties"]["title"] == "회의 노트")
    assert gd._tab_end[("DOC_ID", "회의 노트")] == tab["documentTab"]["body"]["content"][-1]["endIndex"]
    gd.push_all(s)
    assert api.gets == gets + 1  # 전체 동기화는 항상 다시 조회
