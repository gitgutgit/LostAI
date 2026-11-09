# Railway 배포용: 화면(Vite 빌드) + 서버(FastAPI)를 컨테이너 하나로. author: Mal-Mi-Jal
# 빌드 위치는 레포 루트. Railway 서비스 변수 RAILWAY_DOCKERFILE_PATH=server/deploy/Dockerfile (자세한 것: server/deploy/RAILWAY.md)
# 비밀(.env, token.json, credentials.json)은 이미지에 넣지 않는다 → Railway 변수로 (GOOGLE_TOKEN_JSON 등)

FROM node:20-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
# uv.lock과 같은 고정 버전 (uv export로 뽑음 → 컨테이너에 uv 버전을 맞출 필요 없음)
COPY server/deploy/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY server/ server/
COPY fixtures/ fixtures/
COPY --from=web /app/web/dist web/dist
# Railway가 PORT를 준다. 종료 신호(SIGTERM) 때 원본 문서를 되돌릴 시간이 필요 → RAILWAY_DEPLOYMENT_DRAINING_SECONDS=30
CMD ["sh", "-c", "python -m uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-graceful-shutdown 30"]
