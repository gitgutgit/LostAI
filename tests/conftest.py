"""테스트는 실제 외부 문서에 쓰지 않는다. author: Mal-Mi-Jal

server.app이 .env를 읽지만 load_dotenv는 이미 있는 환경 변수를 덮지 않으므로,
여기서 빈 값으로 먼저 잡아 두면 동기화가 꺼진다. 실제 Google 확인은 tests 밖 명령으로 한다
(`uv run python -m server.sync.google_sheets --demo-change`).
"""
import os

for key in ("GOOGLE_SHEET_ID", "GOOGLE_DOC_ID", "LINEAR_API_KEY"):
    os.environ[key] = ""
os.environ.setdefault("AGENT_MODE", "MOCK")
os.environ["SEED"] = "sprint"  # .env가 SEED=google(원본 모드)이어도 테스트는 시드로
# 이벤트 로그와 화면에서 고른 문서 기록(google_source_choice.json)을 실제 results/ 와 떼어 놓는다
import tempfile  # noqa: E402

os.environ["EVENT_LOG_DIR"] = tempfile.mkdtemp(prefix="lostai_test_")
