"""문서 고르기·새로 만들기: 서버 Google 계정의 Sheets/Docs 목록과 빈 회의 문서 만들기. author: Mal-Mi-Jal

목록은 Drive 메타데이터 읽기 권한(파일 이름·종류·수정 시각만)으로 본다. 예전 토큰에는 이 권한이 없다
→ `uv run python -m server.sync.google_auth --relogin` 한 번. 만들기는 Sheets/Docs 권한만으로 된다.
모든 함수는 블로킹 Google 호출 → Outbox 워커에서 부른다 (outbox.run_exclusive, Google 동시 호출 금지).
"""
from __future__ import annotations

from typing import Any

from server.sync import google_auth

MIME = {"sheet": "application/vnd.google-apps.spreadsheet", "doc": "application/vnd.google-apps.document"}

# 새 회의 문서 틀: 음성으로 바로 고칠 수 있게 열 이름과 섹션 제목을 미리 둔다
NEW_SHEET_COLUMNS = ["작업", "담당", "기간(일)", "상태", "메모"]
NEW_DOC_SECTIONS = ["목표", "메모", "리스크"]  # 결정 사항·액션은 처음 기록될 때 끝에 생긴다 (google_source)


class NeedsRelogin(RuntimeError):
    pass


def list_files(kind: str, query: str = "", limit: int = 20) -> list[dict[str, Any]]:
    """최근 수정 순. 나와 공유된 문서도 포함 (팀 원본처럼 남이 만든 문서)."""
    if not google_auth.has_scope(google_auth.DRIVE_LIST_SCOPE):
        raise NeedsRelogin("문서 목록 권한이 없어요. 서버 PC에서 `uv run python -m server.sync.google_auth --relogin` 후 다시 시도해 주세요.")
    from googleapiclient.discovery import build
    # 목록은 가끔만 부르니 매번 토큰 파일을 다시 읽는다 (서버가 떠 있는 동안 재로그인해도 바로 반영)
    drive = build("drive", "v3", credentials=google_auth.get_creds(interactive=False), cache_discovery=False)
    q = f"mimeType='{MIME[kind]}' and trashed=false"
    if query.strip():
        q += " and name contains '" + query.replace("\\", "\\\\").replace("'", "\\'") + "'"
    res = drive.files().list(q=q, orderBy="modifiedTime desc", pageSize=limit,
                             fields="files(id,name,modifiedTime,ownedByMe)").execute()
    return [{"id": f["id"], "name": f["name"], "modified": f.get("modifiedTime"), "mine": f.get("ownedByMe", False)}
            for f in res.get("files", [])]


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
