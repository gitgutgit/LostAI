"""문서 고르기: 빈 회의 문서 만들기 (Sheet 보드 / Doc 회의 노트). author: Mal-Mi-Jal

부르는 쪽 토큰(지금 주인 또는 `google_auth.as_owner`로 잠깐 쓰는 사람)의 Drive에 만든다. drive.file 권한으로 충분하다.
예전에 있던 서버 계정 Drive 목록(list_files)은 다른 사람에게 내 문서가 보여서 없앴다 → 고르기는 Google Picker (source_api).
모든 함수는 블로킹 Google 호출 → Outbox 워커에서 부른다 (outbox.run_exclusive, Google 동시 호출 금지).
"""
from __future__ import annotations

from typing import Any

from server.sync import google_auth

# 새 회의 문서 틀: 음성으로 바로 고칠 수 있게 열 이름과 섹션 제목을 미리 둔다
NEW_SHEET_COLUMNS = ["작업", "담당", "기간(일)", "상태", "메모"]
NEW_DOC_SECTIONS = ["목표", "메모", "리스크"]  # 결정 사항·액션은 처음 기록될 때 끝에 생긴다 (google_source)


def create_sheet(title: str) -> str:
    sheets = google_auth.service("sheets", "v4").spreadsheets()
    header = {"values": [{"userEnteredValue": {"stringValue": c}, "userEnteredFormat": {"textFormat": {"bold": True}}}
                         for c in NEW_SHEET_COLUMNS]}
    body = {"properties": {"title": title},
            "sheets": [{"properties": {"title": "보드", "gridProperties": {"frozenRowCount": 1}},
                        "data": [{"startRow": 0, "startColumn": 0, "rowData": [header]}]}]}
    return sheets.create(body=body, fields="spreadsheetId").execute()["spreadsheetId"]


def doc_template_requests(title: str) -> list[dict[str, Any]]:
    """제목(TITLE) + 섹션 제목(HEADING_2)마다 빈 문단 하나. 인덱스 1부터, UTF-16 길이로 센다."""
    paras = [(title, "TITLE")]
    for h in NEW_DOC_SECTIONS:
        paras += [(h, "HEADING_2"), ("", "NORMAL_TEXT")]
    text = "".join(p + "\n" for p, _ in paras)
    reqs: list[dict[str, Any]] = [{"insertText": {"location": {"index": 1}, "text": text}}]
    i = 1
    for p, style in paras:
        n = len(p.encode("utf-16-le")) // 2 + 1
        if style != "NORMAL_TEXT":
            reqs.append({"updateParagraphStyle": {"range": {"startIndex": i, "endIndex": i + n},
                                                  "paragraphStyle": {"namedStyleType": style}, "fields": "namedStyleType"}})
        i += n
    return reqs


def create_doc(title: str) -> str:
    docs = google_auth.service("docs", "v1").documents()
    did = docs.create(body={"title": title}).execute()["documentId"]
    docs.batchUpdate(documentId=did, body={"requests": doc_template_requests(title)}).execute()
    return did
