FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
# --ignore-scripts: the `prepare` script installs git hooks, and there is no git here.
RUN npm ci --ignore-scripts

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
