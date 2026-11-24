FROM node:24-alpine AS frontend
WORKDIR /work
COPY package.json next.config.mjs tsconfig.json ./
RUN npm install --no-audit --no-fund
COPY app app
COPY components components
COPY public public
COPY tools/tailwind.mjs tools/tailwind.mjs
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.12-slim
WORKDIR /srv/aeris
COPY backend/requirements*.txt backend/
RUN pip install --no-cache-dir -r backend/requirements-postgres.txt
COPY backend backend
COPY vision vision
COPY public/scene public/scene
COPY --from=frontend /work/out out
EXPOSE 8765
CMD ["python","-m","uvicorn","backend.main:app","--host","0.0.0.0","--port","8765","--workers","1"]
