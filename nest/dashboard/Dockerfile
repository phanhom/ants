# Stage 1: build SPA (VITE_NEST_URL = URL the browser uses to reach Nest API)
FROM node:20-alpine AS builder
ARG VITE_NEST_URL=http://localhost:22000
ENV VITE_NEST_URL=${VITE_NEST_URL}
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# Stage 2: serve SPA + API (traces from MySQL)
FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev
COPY server ./server
COPY --from=builder /app/dist ./dist
ENV PORT=3000
EXPOSE 3000
CMD ["node", "server/index.cjs"]
