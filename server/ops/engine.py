"""Op 엔진: 검증 → 적용 → diff → provenance, diff로 역연산 (docs/ARCHITECTURE.md 3-2, 3-3).

diff 한 줄 형식: {"kind", "anchor", "before", "after", "index"?}
- kind: cell | row | item | section | heading | ticket | conflict
- before가 None이면 생성, after가 None이면 삭제.
op 하나가 실패해도 회의가 멈추지 않도록 op 단위로 예외를 잡는다.
"""
from __future__ import annotations

import itertools
from typing import Any

from server.model.docs import Conflict, Doc, DocState, Item, Row, Section, Sheet, Ticket
from server.ops.registry import validate_op

_ids = itertools.count(1)


def new_id(prefix: str) -> str:
    return f"{prefix}{next(_ids)}"


class OpError(Exception):
    pass


# ---------------------------------------------------------------- 찾기 헬퍼

def _find_row(sheet: Sheet, row_id: str) -> tuple[int, Row]:
    for i, r in enumerate(sheet.rows):
        if r.row_id == row_id:
            return i, r
    raise OpError(f"row not found: {row_id}")


def _find_section(doc: Doc, section_id: str) -> tuple[int, Section]:
    for i, s in enumerate(doc.sections):
        if s.section_id == section_id:
            return i, s
    raise OpError(f"section not found: {section_id}")


def _find_item(doc: Doc, item_id: str) -> tuple[Section, int, Item]:
    for s in doc.sections:
        for i, it in enumerate(s.items):
            if it.item_id == item_id:
                return s, i, it
    raise OpError(f"item not found: {item_id}")


def _binding_section(state: DocState, binding: str) -> tuple[str, Section]:
    found = state.section_by_binding(binding)  # type: ignore[arg-type]
    if not found:
        raise OpError(f"no section bound to {binding}")
    return found


# ---------------------------------------------------------------- 적용

def apply_op(state: DocState, op: dict[str, Any]) -> list[dict[str, Any]]:
    err = validate_op(op)
    if err:
        raise OpError(err)
    name = op["op"]

    if name == "set_cell":
        sheet = state.sheet(op["doc"])
        if op["column"] not in sheet.columns:
            raise OpError(f"unknown column: {op['column']}")
        _, row = _find_row(sheet, op["row"])
        before = row.cells.get(op["column"])
        row.cells[op["column"]] = op["value"]
        return [{"kind": "cell", "anchor": f"{op['doc']}/{row.row_id}/{op['column']}", "before": before, "after": op["value"]}]

    if name == "add_row":
        sheet = state.sheet(op["doc"])
        row = Row(row_id=new_id("r_new"), cells={k: v for k, v in op["values"].items() if k in sheet.columns})
        sheet.rows.append(row)
        return [{"kind": "row", "anchor": f"{op['doc']}/{row.row_id}", "before": None, "after": row.model_dump(), "index": len(sheet.rows) - 1}]

    if name == "delete_row":
        sheet = state.sheet(op["doc"])
        i, row = _find_row(sheet, op["row"])
        sheet.rows.pop(i)
        return [{"kind": "row", "anchor": f"{op['doc']}/{row.row_id}", "before": row.model_dump(), "after": None, "index": i}]

    if name in ("insert_item", "add_decision", "add_action", "add_note"):
        if name == "insert_item":
            key, (_, section) = op["doc"], _find_section(state.doc(op["doc"]), op["section"])
        else:
            binding = {"add_decision": "decisions", "add_action": "actions", "add_note": "notes"}[name]
            key, section = _binding_section(state, binding)
        item = Item(item_id=new_id("i_"), text=op["text"], meta={"owner": op["owner"]} if op.get("owner") else {})
        index = len(section.items)
        if op.get("after"):
            for j, it in enumerate(section.items):
                if it.item_id == op["after"]:
                    index = j + 1
        section.items.insert(index, item)
        return [{"kind": "item", "anchor": f"{key}/{section.section_id}/{item.item_id}", "before": None, "after": item.model_dump(), "index": index}]

    if name in ("update_item", "claim_action", "delete_item"):
        key, section, i, item = _locate_item(state, op["item"], op.get("doc"))
        before = item.model_dump()
        anchor = f"{key}/{section.section_id}/{item.item_id}"
        if name == "delete_item":
            section.items.pop(i)
            return [{"kind": "item", "anchor": anchor, "before": before, "after": None, "index": i}]
        if name == "update_item":
            item.text = op["text"]
        else:
            item.meta["owner"] = op["owner"]
        return [{"kind": "item", "anchor": anchor, "before": before, "after": item.model_dump(), "index": i}]

    if name == "add_section":
        doc = state.doc(op["doc"])
        sec = Section(section_id=new_id("s_new"), heading=op["heading"])
        doc.sections.append(sec)
        return [{"kind": "section", "anchor": f"{op['doc']}/{sec.section_id}", "before": None, "after": sec.model_dump(), "index": len(doc.sections) - 1}]

    if name == "rename_section":
        _, sec = _find_section(state.doc(op["doc"]), op["section"])
        before, sec.heading = sec.heading, op["heading"]
        return [{"kind": "heading", "anchor": f"{op['doc']}/{sec.section_id}", "before": before, "after": sec.heading}]

    if name == "create_ticket":
        t = Ticket(ticket_id=new_id("t_"), title=op["title"], assignee=op.get("assignee"))
        state.tickets.append(t)
        return [{"kind": "ticket", "anchor": f"tickets/{t.ticket_id}", "before": None, "after": t.model_dump(), "index": len(state.tickets) - 1}]

    if name == "open_conflict":
        c = Conflict(conflict_id=new_id("cf_"), topic=op["topic"], positions=op.get("positions") or [])
        state.conflicts.append(c)
        return [{"kind": "conflict", "anchor": f"conflicts/{c.conflict_id}", "before": None, "after": c.model_dump(), "index": len(state.conflicts) - 1}]

    if name == "resolve_conflict":
        for i, c in enumerate(state.conflicts):
            if c.conflict_id == op["conflict"]:
                before = c.model_dump()
                c.resolved, c.resolution = True, op["resolution"]
                return [{"kind": "conflict", "anchor": f"conflicts/{c.conflict_id}", "before": before, "after": c.model_dump(), "index": i}]
        raise OpError(f"conflict not found: {op['conflict']}")

    raise OpError(f"op not handled by engine: {name}")  # undo_last 는 ChangeManager가 처리


def _locate_item(state: DocState, item_id: str, doc_key: str | None) -> tuple[str, Section, int, Item]:
    keys = [doc_key] if doc_key else [k for k, d in state.docs.items() if isinstance(d, Doc)]
    for key in keys:
        try:
            section, i, item = _find_item(state.doc(key), item_id)
            return key, section, i, item
        except OpError:
            continue
    raise OpError(f"item not found: {item_id}")


# ---------------------------------------------------------------- 역연산

def revert_diff(state: DocState, diff: list[dict[str, Any]]) -> None:
    """diff를 뒤에서부터 되감는다."""
    for d in reversed(diff):
        parts = d["anchor"].split("/")
        kind, before, after = d["kind"], d["before"], d["after"]

        if kind == "cell":
            _, row = _find_row(state.sheet(parts[0]), parts[1])
            row.cells[parts[2]] = before
        elif kind == "row":
            sheet = state.sheet(parts[0])
            if before is None:
                sheet.rows.pop(_find_row(sheet, parts[1])[0])
            elif after is None:
                sheet.rows.insert(d["index"], Row.model_validate(before))
        elif kind == "item":
            _, sec = _find_section(state.doc(parts[0]), parts[1])
            if before is None:
                sec.items = [it for it in sec.items if it.item_id != parts[2]]
            elif after is None:
                sec.items.insert(d["index"], Item.model_validate(before))
            else:
                _, i, _ = _find_item(state.doc(parts[0]), parts[2])
                sec.items[i] = Item.model_validate(before)
        elif kind == "section":
            doc = state.doc(parts[0])
            doc.sections = [s for s in doc.sections if s.section_id != parts[1]]
        elif kind == "heading":
            _find_section(state.doc(parts[0]), parts[1])[1].heading = before
        elif kind == "ticket":
            state.tickets = [t for t in state.tickets if t.ticket_id != parts[1]]
        elif kind == "conflict":
            if before is None:
                state.conflicts = [c for c in state.conflicts if c.conflict_id != parts[1]]
            else:
                state.conflicts[d["index"]] = Conflict.model_validate(before)


def anchors_of(diff: list[dict[str, Any]]) -> list[str]:
    return [d["anchor"] for d in diff]
