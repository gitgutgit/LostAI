"""각자 Google 로그인: 화면 팝업(Google Identity Services 코드 방식)에서 받은 code → 토큰. author: Mal-Mi-Jal

문서 고르기에서 다른 사람 Drive가 보이지 않게 하려고 만들었다 (예전: 서버 계정 하나의 Drive 목록을 모두에게 보여 줌).

- 권한은 `drive.file` 하나 + 계정 이메일. 이 앱이 만든 파일과 그 사람이 Google Picker에서 직접 고른 파일만 열 수 있다.
  파일 목록은 Picker가 그 사람 브라우저에서 Google과 직접 주고받는다 → 우리 서버를 거치지 않는다.
- 토큰은 **메모리에만** 둔다 (디스크·로그에 안 남김). 서버를 다시 켜면 다시 로그인한다.
- 로그인은 입장 토큰이 아니라 로그인 때 새로 만든 **무작위 열쇠(gsid)** 에 묶는다. 입장 토큰은 이름만으로 만들어져서
  (`challenge.make_token`) 같은 이름으로 들어온 사람이 같은 토큰을 받는다 → 그 사람이 남의 Drive를 열면 안 된다.
  gsid는 로그인한 브라우저 탭(sessionStorage)에만 있고, 요청 때 입장 이름과 같이 맞아야 통과한다.
- 설정 (.env, 값은 출력하지 않는다): 웹 애플리케이션 클라이언트 + GOOGLE_PICKER_API_KEY, GOOGLE_PROJECT_NUMBER.
  클라이언트는 셋 중 하나: GOOGLE_OAUTH_CLIENT_FILE(콘솔에서 받은 JSON 파일 경로) / GOOGLE_OAUTH_CLIENT_JSON(그 내용, 배포용)
  / GOOGLE_OAUTH_CLIENT_ID + GOOGLE_OAUTH_CLIENT_SECRET. 자세히: server/sync/GOOGLE_SETUP.md 6-1절
"""
from __future__ import annotations

import base64
import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOKEN_URI = "https://oauth2.googleapis.com/token"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
SCOPES = [DRIVE_FILE_SCOPE, "openid", "https://www.googleapis.com/auth/userinfo.email"]


@dataclass
class GoogleSession:
    creds: Any          # google.oauth2.credentials.Credentials
    email: str
    name: str = ""      # 로그인한 입장 이름 (gsid와 같이 맞아야 한다)


_sessions: dict[str, GoogleSession] = {}  # gsid → 로그인


class LoginError(ValueError):
    pass


def _env(name: str) -> str:
    return os.getenv(name, "").strip().strip("'\"")


def client() -> tuple[str, str]:
    """(client_id, client_secret). JSON 파일·내용이 있으면 그것, 없으면 ID/SECRET 변수. 없으면 ("", "")."""
    raw = _env("GOOGLE_OAUTH_CLIENT_JSON")
    path = _env("GOOGLE_OAUTH_CLIENT_FILE")
    if not raw and path:
        try:
            raw = Path(os.path.expanduser(path)).read_text(encoding="utf-8")
        except OSError:
            raw = ""
    if raw:
        try:
            c = json.loads(raw)
            c = c.get("web") or c.get("installed") or c  # 콘솔 JSON은 {"web": {...}}
            return str(c.get("client_id", "")).strip(), str(c.get("client_secret", "")).strip()
        except (ValueError, AttributeError):
            return "", ""
    return _env("GOOGLE_OAUTH_CLIENT_ID"), _env("GOOGLE_OAUTH_CLIENT_SECRET")


def enabled() -> bool:
    return all(client()) and all(_env(k) for k in ("GOOGLE_PICKER_API_KEY", "GOOGLE_PROJECT_NUMBER"))


def public_config() -> dict[str, Any]:
    """화면에 주는 값. Client ID·Picker API 키·프로젝트 번호는 원래 브라우저에 보이는 값이다 (비밀은 client secret뿐)."""
    return {"enabled": enabled(), "client_id": client()[0], "api_key": _env("GOOGLE_PICKER_API_KEY"),
            "app_id": _env("GOOGLE_PROJECT_NUMBER"), "scope": " ".join(SCOPES)}


def _email_from_id_token(id_token: str | None) -> str:
    """Google 토큰 엔드포인트에서 TLS로 직접 받은 id_token이라 서명 검증 없이 이메일만 읽는다 (표시용)."""
    if not id_token:
        return ""
    try:
        part = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))).get("email", "")
    except (IndexError, ValueError):
        return ""


def _post_token(code: str) -> dict[str, Any]:
    import requests
    cid, secret = client()
    r = requests.post(TOKEN_URI, timeout=10, data={
        "code": code, "client_id": cid, "client_secret": secret,
        "redirect_uri": "postmessage",  # 팝업 코드 방식의 약속된 값
        "grant_type": "authorization_code"})
    if r.status_code != 200:
        # 응답 본문에 값이 섞일 수 있어 오류 이름만 쓴다
        err = (r.json().get("error") if r.headers.get("content-type", "").startswith("application/json") else None) or r.status_code
        raise LoginError(f"Google 로그인 실패 ({err}). 다시 시도해 주세요.")
    return r.json()


def exchange(code: str) -> GoogleSession:
    """code → 토큰. 블로킹 호출 (asyncio.to_thread로 부른다)."""
    from google.oauth2.credentials import Credentials
    t = _post_token(code)
    granted = set((t.get("scope") or "").split())
    if DRIVE_FILE_SCOPE not in granted:
        raise LoginError("Google 로그인 창에서 'Google Drive 파일' 권한을 허용해 주세요.")
    cid, secret = client()
    creds = Credentials(token=t["access_token"], refresh_token=t.get("refresh_token"), token_uri=TOKEN_URI,
                        client_id=cid, client_secret=secret,
                        scopes=sorted(granted))
    return GoogleSession(creds=creds, email=_email_from_id_token(t.get("id_token")) or "Google 계정")


def login(name: str, sess: GoogleSession) -> str:
    """로그인을 저장하고 새 gsid를 돌려준다 (그 브라우저 탭에만 준다)."""
    gsid = secrets.token_urlsafe(32)
    sess.name = name
    _sessions[gsid] = sess
    return gsid


def logout(gsid: str) -> None:
    _sessions.pop(gsid, None)


def get(name: str, gsid: str | None) -> GoogleSession | None:
    """gsid가 있고 그 로그인이 같은 입장 이름일 때만. 이름이 같아도 gsid가 없으면 None."""
    sess = _sessions.get(gsid or "")
    if sess is None or not secrets.compare_digest(sess.name.encode(), name.encode()):
        return None
    return sess


def access_token(sess: GoogleSession) -> str:
    """Picker용 access token (그 사람 브라우저에만 준다). 만료가 가까우면 갱신 → 블로킹."""
    from google.auth.transport.requests import Request
    c = sess.creds
    if not c.valid:
        if not c.refresh_token:
            raise LoginError("Google 로그인이 만료됐어요. 다시 로그인해 주세요.")
        c.refresh(Request())
    return c.token
