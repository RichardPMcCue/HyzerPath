FROM node:26-slim AS build

WORKDIR /app

COPY package.json package-lock.json .npmrc ./

RUN npm ci

COPY . .

ARG VITE_API_URL=/api

RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80