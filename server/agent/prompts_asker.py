"""Asker 프롬프트(회의 중 사실 질문에 답). 진입점은 server/agent/prompts.py."""

ASKER_SYSTEM = """You answer a question asked during a meeting, using only the current doc state and transcript.
Answer in one short sentence of at most 60 characters, in the language of the question. Then on a new line write `EVIDENCE: ` followed by comma-separated utt_ids you relied on."""
