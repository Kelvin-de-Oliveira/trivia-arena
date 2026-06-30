# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copiar manifests primeiro para aproveitar o cache de camadas Docker
COPY package*.json ./
RUN npm ci

# Copiar código-fonte
COPY . .

# Receber o host do Gateway como build arg
# Fallback para localhost:8000 em ambiente de desenvolvimento local
ARG VITE_API_GATEWAY_HOST=localhost:8000
ENV VITE_API_GATEWAY_HOST=${VITE_API_GATEWAY_HOST}

# Compilar o bundle de produção (output em /app/dist)
RUN npm run build

# ── Stage 2: Serve ────────────────────────────────────────────────────────────
FROM nginx:1.25-alpine

# Copiar os arquivos estáticos compilados
COPY --from=builder /app/dist /usr/share/nginx/html

# Copiar configuração do Nginx para SPA (client-side routing)
COPY nginx-frontend.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
