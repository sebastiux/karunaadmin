# ---- build stage ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# VITE_API_URL / VITE_REALTIME_URL are baked in at build time.
# On Railway, set them as build-time variables on the service.
ARG VITE_API_URL
ARG VITE_REALTIME_URL
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_REALTIME_URL=$VITE_REALTIME_URL
RUN npm run build

# ---- serve stage ----
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
# Railway injects $PORT; nginx template substitutes it. Default to 8080 locally.
ENV PORT=8080
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
