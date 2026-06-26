# org-nexus-console — Vite + React SPA
# Vite inlines VITE_* at build time; pass build-args or Coolify build variables.
# Runtime: `serve` (static SPA). Coolify terminates TLS and proxies to this container.

FROM node:22-bookworm-slim AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL
ARG VITE_FIREBASE_API_KEY
ARG VITE_FIREBASE_AUTH_DOMAIN
ARG VITE_FIREBASE_PROJECT_ID
ARG VITE_FIREBASE_STORAGE_BUCKET
ARG VITE_FIREBASE_MESSAGING_SENDER_ID
ARG VITE_FIREBASE_APP_ID

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY \
    VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN \
    VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID \
    VITE_FIREBASE_STORAGE_BUCKET=$VITE_FIREBASE_STORAGE_BUCKET \
    VITE_FIREBASE_MESSAGING_SENDER_ID=$VITE_FIREBASE_MESSAGING_SENDER_ID \
    VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID

RUN npm run build

FROM node:22-bookworm-slim AS runner

WORKDIR /app
RUN npm install -g serve@14

COPY --from=builder /app/dist ./dist

ENV NODE_ENV=production
EXPOSE 3000

# Uses Node (already in image); no curl/wget required.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD node -e 'require("http").get("http://127.0.0.1:3001/", (r) => { r.resume(); process.exit(r.statusCode >= 200 && r.statusCode < 400 ? 0 : 1); }).on("error", () => process.exit(1));'

CMD ["serve", "-s", "dist", "-l", "3001"]