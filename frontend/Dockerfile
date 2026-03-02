# ── Frontend Dockerfile ───────────────────────────────────────────────────────
# Stage 1: build the static Vite bundle.
# Stage 2: serve with nginx (tiny footprint, handles gzip + asset caching).

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first — Docker caches this layer until deps change.
COPY package.json package-lock.json* ./
RUN npm ci --silent

# Copy source and build.
COPY . .

# VITE_API_URL is injected at build time so the bundle points to the
# deployed backend URL. Default to localhost for local Docker Compose use.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# ── Stage 2: nginx runtime ────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# Remove default nginx page.
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets.
COPY --from=builder /app/dist /usr/share/nginx/html

# Custom nginx config: all routes → index.html (SPA routing support).
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
