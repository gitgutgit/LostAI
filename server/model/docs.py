"""Sheet/Doc 중립 문서 모델과 앵커 (docs/ARCHITECTURE.md 4-2). ← 계약 파일.

앵커 형식
- 시트 칸:   "<doc_key>/<row_id>/<column>"   예) board/r_pay423/추정
- 시트 행:   "<doc_key>/<row_id>"            예) board/r_pay423
- 문서 항목: "<doc_key>/<section_id>/<item_id>"  예) notes/s_risk/i_12
- 문서 섹션: "<doc_key>/<section_id>"
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Union

from pydantic import BaseModel, Field

Binding = Literal["decisions", "risks", "actions", "notes"]


class Row(BaseModel):
    row_id: str
    cells: dict[str, Any] = Field(default_factory=dict)


class Sheet(BaseModel):
    kind: Literal["sheet"] = "sheet"
    title: str
    columns: list[str]
    rows: list[Row] = Field(default_factory=list)


class Item(BaseModel):
    item_id: str
    text: str
    meta: dict[str, Any] = Field(default_factory=dict)  # 예) 액션 담당자 owner


class Section(BaseModel):
    section_id: str
    heading: str
    binding: Binding | None = None
    items: list[Item] = Field(default_factory=list)


class Doc(BaseModel):
    kind: Literal["doc"] = "doc"
    title: str
    sections: list[Section] = Field(default_factory=list)


AnyDoc = Union[Sheet, Doc]


class Conflict(BaseModel):
    conflict_id: str
    topic: str
    positions: list[dict[str, str]] = Field(default_factory=list)  # [{"who":..., "says":...}]
    resolved: bool = False
    resolution: str | None = None


class Ticket(BaseModel):
    ticket_id: str
    title: str
    assignee: str | None = None
    external_id: str | None = None


class DocState(BaseModel):
    docs: dict[str, AnyDoc] = Field(default_factory=dict)
    conflicts: list[Conflict] = Field(default_factory=list)
    tickets: list[Ticket] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)  # anchor → 마지막 change_id

    # ---- 조회 헬퍼 ----
    def sheet(self, key: str) -> Sheet:
        d = self.docs[key]
        assert isinstance(d, Sheet), f"{key} is not a sheet"
        return d

    def doc(self, key: str) -> Doc:
        d = self.docs[key]
        assert isinstance(d, Doc), f"{key} is not a doc"
        return d

    def section_by_binding(self, binding: Binding) -> tuple[str, Section] | None:
        for key, d in self.docs.items():
            if isinstance(d, Doc):
                for s in d.sections:
                    if s.binding == binding:
                        return key, s
        return None


def parse_anchor(anchor: str) -> list[str]:
    return anchor.split("/")


def make_anchor(*parts: str) -> str:
    return "/".join(parts)


def load_seed(name: str) -> DocState:
    path = Path(__file__).parent / "seeds" / f"{name}.json"
    return DocState.model_validate(json.loads(path.read_text(encoding="utf-8")))
