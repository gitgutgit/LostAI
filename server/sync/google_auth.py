"""Google OAuth 인증 + Sheets/Docs 서비스 생성. author: Mal-Mi-Jal

PoC(`shared/google_api.py`) 방식 그대로: 데스크톱 앱 OAuth 클라이언트(`credentials.json`)로
브라우저 로그인 → `token.json` 저장. 문서는 **로그인한 계정** 권한으로 열린다.
다른 사람 문서는 그 사람이 내 Gmail을 편집자로 공유해 주면 ID/URL로 열 수 있다.

화면에서 각자 Google 로그인으로 자기 문서를 고르면(`user_auth`, `source_api`) 그 사람이 **문서 주인**이 되고,
`service()`는 서버 토큰 대신 주인 토큰을 쓴다 (`set_owner` / 잠깐만 쓰는 `as_owner`). 주인 토큰은 메모리에만 있다.

    uv run python -m server.sync.google_auth                    # 로그인 + .env의 문서 접근 확인
    uv run python -m server.sync.google_auth --sheet <URL> --doc <URL> [--save]
    uv run python -m server.sync.google_auth --relogin          # 토큰 지우고 다시 로그인

비밀 파일 내용과 문서 ID는 출력하지 않는다 (init-collab §6). 자세한 안내: server/sync/GOOGLE_SETUP.md
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
]

_services: dict[tuple[str, str], Any] = {}
# 지금 회의 원본의 주인 (각자 로그인한 사람). None이면 서버 토큰(token.json)
_owner: Any = None
_owner_label: str | None = None


def credentials_path() -> Path:
    return ROOT / os.getenv("GOOGLE_CREDENTIALS", "credentials.json")


def token_path() -> Path:
    return ROOT / os.getenv("GOOGLE_TOKEN", "token.json")


def materialize_from_env() -> None:
    """배포 환경(Railway 등)에는 파일을 못 올리므로 환경 변수 GOOGLE_TOKEN_JSON / GOOGLE_CREDENTIALS_JSON 에
    파일 내용을 그대로 넣는다 → 파일이 없을 때만 써 둔다 (토큰 갱신도 그 파일에 저장된다)."""
    import base64
    for path, var in ((token_path(), "GOOGLE_TOKEN"), (credentials_path(), "GOOGLE_CREDENTIALS")):
        if path.exists():
            continue
        raw = os.getenv(f"{var}_JSON", "").strip().strip("'\"")  # 대시보드에서 따옴표로 감싸 넣은 경우
        b64 = os.getenv(f"{var}_B64", "").strip()  # 붙여넣기 실수가 적은 한 줄 base64 (results/railway_token_b64.txt)
        if b64:
            try:
                raw = base64.b64decode(b64).decode("utf-8")
            except ValueError:
                raw = ""
        if raw.startswith("{"):
            path.write_text(raw, encoding="utf-8")


def available() -> bool:
    materialize_from_env()
    return token_path().exists() or credentials_path().exists()


def get_creds(interactive: bool = True):
    """유효한 Credentials를 돌려준다. 토큰이 없거나 만료·취소되면 interactive일 때만 브라우저 로그인."""
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    materialize_from_env()
    tok = token_path()
    creds = None
    if tok.exists():
        # 토큰에 실제로 받은 권한 그대로 연다 (SCOPES를 넘기면 예전 토큰의 갱신이 권한 부족으로 실패할 수 있다)
        creds = Credentials.from_authorized_user_file(str(tok))
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # 테스트 모드 앱은 약 7일 뒤 refresh token이 만료된다 (invalid_grant)
                creds = None
    if not creds or not creds.valid:
        if not interactive:
            raise RuntimeError("Google 토큰 없음/만료 → `uv run python -m server.sync.google_auth` 로 로그인")
        cred_file = credentials_path()
        if not cred_file.exists():
            raise FileNotFoundError(f"{cred_file.name} 없음 → server/sync/GOOGLE_SETUP.md 1단계")
        from google_auth_oauthlib.flow import InstalledAppFlow
        creds = InstalledAppFlow.from_client_secrets_file(str(cred_file), SCOPES).run_local_server(port=0)
    tok.write_text(creds.to_json(), encoding="utf-8")
    return creds


def owner() -> str | None:
    """지금 원본 주인 표시 이름 (로그인한 Google 계정 이메일 등). None = 서버 계정."""
    return _owner_label


def set_owner(creds: Any, label: str | None) -> tuple[Any, str | None]:
    """회의 원본 주인을 바꾼다 (None이면 서버 계정). 이전 주인을 돌려준다. Outbox 워커 안에서만 부른다."""
    global _owner, _owner_label
    prev = (_owner, _owner_label)
    _owner, _owner_label = creds, label if creds is not None else None
    _services.clear()  # 서비스 객체는 토큰에 묶여 있다
    return prev


@contextmanager
def as_owner(creds: Any, label: str | None):
    """잠깐 그 사람 토큰으로 Google을 부른다 (바꾸기 전 새 문서 만들기·구조 확인). 끝나면 원래 주인으로."""
    prev = set_owner(creds, label)
    try:
        yield
    finally:
        set_owner(*prev)


def service(name: str, version: str):
    """sheets/v4, docs/v1. Outbox 워커 하나에서만 쓰므로 캐시해도 동시 호출이 생기지 않는다.
    주인이 있으면 주인 토큰, 없으면 서버 토큰. 주인이 바뀌면 캐시를 비운다 (`set_owner`)."""
    key = (name, version)
    if key not in _services:
        from googleapiclient.discovery import build
        creds = _owner if _owner is not None else get_creds(interactive=False)
        _services[key] = build(name, version, credentials=creds, cache_discovery=False)
    return _services[key]


def parse_id(url_or_id: str) -> str:
    """Google 문서 URL 또는 ID → ID."""
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url_or_id)
    return m.group(1) if m else url_or_id.strip()


def _hint(e: Exception) -> str:
    s = str(e)
    if "404" in s:
        return "문서를 찾을 수 없음 (ID 확인)"
    if "403" in s and "has not been used" in s:
        return "이 GCP 프로젝트에서 API가 꺼져 있음 → Sheets/Docs API 사용 설정"
    if "403" in s:
        return "권한 없음 → 문서 주인에게 내 Gmail을 편집자로 공유 요청"
    return s[:160]


def check(sheet_id: str | None, doc_id: str | None) -> bool:
    ok = True
    if sheet_id:
        try:
            meta = service("sheets", "v4").spreadsheets().get(spreadsheetId=sheet_id).execute()
            tabs = [s["properties"]["title"] for s in meta["sheets"]]
            print(f"  ✅ Sheet  '{meta['properties']['title']}'  탭: {tabs}")
        except Exception as e:
            ok = False
            print(f"  ❌ Sheet  {_hint(e)}")
    if doc_id:
        try:
            doc = service("docs", "v1").documents().get(documentId=doc_id).execute()
            print(f"  ✅ Doc    '{doc['title']}'")
        except Exception as e:
            ok = False
            print(f"  ❌ Doc    {_hint(e)}")
    if not sheet_id and not doc_id:
        print("  (확인할 문서 없음: .env GOOGLE_SHEET_ID / GOOGLE_DOC_ID 또는 --sheet/--doc)")
    return ok


def _save_env(values: dict[str, str]) -> None:
    env = ROOT / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    for k, v in values.items():
        for i, line in enumerate(lines):
            if line.startswith(f"{k}="):
                lines[i] = f"{k}={v}"
                break
        else:
            lines.append(f"{k}={v}")
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  .env 갱신: {', '.join(values)} (값은 출력 안 함)")


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(description="Google 로그인 + 문서 접근 확인")
    p.add_argument("--sheet", help="Sheet URL 또는 ID (기본: .env GOOGLE_SHEET_ID)")
    p.add_argument("--doc", help="Doc URL 또는 ID (기본: .env GOOGLE_DOC_ID)")
    p.add_argument("--save", action="store_true", help="접근 성공한 --sheet/--doc을 .env에 저장")
    p.add_argument("--relogin", action="store_true", help="token.json을 지우고 다시 로그인")
    a = p.parse_args()

    if a.relogin and token_path().exists():
        token_path().unlink()
    print(f"credentials.json: {'있음' if credentials_path().exists() else '없음'}  ·  "
          f"token.json: {'있음' if token_path().exists() else '없음 (브라우저 로그인 진행)'}")
    creds = get_creds(interactive=True)
    print("✅ Google 로그인 OK (scopes: " + ", ".join(s.rsplit("/", 1)[-1] for s in (creds.scopes or [])) + ")")

    sheet = parse_id(a.sheet) if a.sheet else os.getenv("GOOGLE_SHEET_ID") or None
    doc = parse_id(a.doc) if a.doc else os.getenv("GOOGLE_DOC_ID") or None
    ok = check(sheet, doc)
    if a.save and ok:
        _save_env({k: v for k, v in (("GOOGLE_SHEET_ID", a.sheet and sheet), ("GOOGLE_DOC_ID", a.doc and doc)) if v})
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
