FROM registry.redhat.io/rhel10/nodejs-24-minimal:latest AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY --exclude=node_modules --exclude=.vscode . .
RUN npm run build

FROM registry.redhat.io/rhel10/nginx-126:latest

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
