"""op 정의 한 곳 (docs/ARCHITECTURE.md 4-3). ← 계약 파일.

여기 정의에서 파생되는 것
- LLM 툴 스키마 (`tool_schemas()`)          → server/agent/editor.py
- 검증 (`validate_op()`)                    → server/ops/engine.py
- 채점용 이름 묶기 (`EVAL_ALIAS`)            → eval/
적용·역연산 구현은 server/ops/engine.py 의 핸들러가 op 이름으로 찾는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

OpKind = Literal["sheet", "doc", "record", "control"]


@dataclass(frozen=True)
class OpSpec:
    name: str
    kind: OpKind
    description: str
    params: dict[str, dict[str, Any]]  # JSON Schema properties
    required: tuple[str, ...] = ()
    google: Literal["sheets", "docs", "linear", None] = None  # 동기화 대상
    extra: dict[str, Any] = field(default_factory=dict)


_S = {"type": "string"}
_ANY = {"type": ["string", "number", "null"]}

OPS: dict[str, OpSpec] = {
    s.name: s
    for s in [
        # ---- 시트 ----
        OpSpec("set_cell", "sheet", "시트의 한 칸 값을 바꾼다.",
               {"doc": _S, "row": {**_S, "description": "row_id"}, "column": _S, "value": _ANY},
               ("doc", "row", "column", "value"), google="sheets"),
        OpSpec("add_row", "sheet", "시트에 행을 추가한다.",
               {"doc": _S, "values": {"type": "object", "description": "column → value"}},
               ("doc", "values"), google="sheets"),
        OpSpec("delete_row", "sheet", "시트의 행을 지운다.",
               {"doc": _S, "row": _S}, ("doc", "row"), google="sheets"),
        # ---- 문서 ----
        OpSpec("insert_item", "doc", "문서 섹션에 항목을 넣는다. after가 있으면 그 항목 뒤에.",
               {"doc": _S, "section": {**_S, "description": "section_id"}, "text": _S, "after": _S},
               ("doc", "section", "text"), google="docs"),
        OpSpec("update_item", "doc", "문서 항목의 문장을 바꾼다.",
               {"doc": _S, "item": {**_S, "description": "item_id"}, "text": _S},
               ("doc", "item", "text"), google="docs"),
        OpSpec("delete_item", "doc", "문서 항목을 지운다.",
               {"doc": _S, "item": _S}, ("doc", "item"), google="docs"),
        OpSpec("add_section", "doc", "문서에 섹션을 추가한다.",
               {"doc": _S, "heading": _S}, ("doc", "heading"), google="docs"),
        OpSpec("rename_section", "doc", "섹션 제목을 바꾼다.",
               {"doc": _S, "section": _S, "heading": _S}, ("doc", "section", "heading"), google="docs"),
        # ---- 기록 (binding 섹션에 들어간다) ----
        OpSpec("add_decision", "record", "결정 사항을 기록한다.",
               {"text": _S}, ("text",), google="docs"),
        OpSpec("add_action", "record", "액션 아이템을 기록한다.",
               {"text": _S, "owner": _S}, ("text",), google="docs"),
        OpSpec("claim_action", "record", "기존 액션의 담당자를 정한다.",
               {"item": _S, "owner": _S}, ("item", "owner"), google="docs"),
        OpSpec("add_note", "record", "메모를 남긴다.",
               {"text": _S}, ("text",), google="docs"),
        OpSpec("create_ticket", "record", "티켓을 만든다.",
               {"title": _S, "assignee": _S}, ("title",), google="linear"),
        OpSpec("open_conflict", "record", "의견 충돌을 연다.",
               {"topic": _S, "positions": {"type": "array", "items": {"type": "object"}}},
               ("topic",)),
        OpSpec("resolve_conflict", "record", "충돌을 해소한다.",
               {"conflict": _S, "resolution": _S}, ("conflict", "resolution")),
        # ---- 말로 하는 취소 ----
        OpSpec("undo_last", "control", "대상을 말하지 않은 취소(\"방금 거 취소\"). 가장 최근 변경을 되돌린다.",
               {}, ()),
    ]
}

# 평가 대본 호환: 채점할 때 이 이름으로 묶어서 센다.
EVAL_ALIAS: dict[str, str] = {
    "insert_item": "edit_doc",
    "update_item": "edit_doc",
    "delete_item": "edit_doc",
    "add_section": "edit_doc",
    "rename_section": "edit_doc",
}


def tool_schemas() -> list[dict[str, Any]]:
    """Anthropic tool 정의 목록. 순서가 바뀌면 프롬프트 캐시가 깨지므로 정렬해서 낸다."""
    out = []
    for name in sorted(OPS):
        s = OPS[name]
        out.append({
            "name": s.name,
            "description": s.description,
            "input_schema": {
                "type": "object",
                "properties": s.params,
                "required": list(s.required),
            },
        })
    return out


def validate_op(op: dict[str, Any]) -> str | None:
    """문제가 있으면 오류 문장, 없으면 None."""
    name = op.get("op")
    spec = OPS.get(name or "")
    if spec is None:
        return f"unknown op: {name}"
    missing = [k for k in spec.required if k not in op]
    if missing:
        return f"{name}: missing {missing}"
    return None
