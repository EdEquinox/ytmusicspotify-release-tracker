# syntax=docker/dockerfile:1

FROM node:20-alpine AS build
WORKDIR /app

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .

ARG REACT_APP_GIT_SHA=unknown
ARG REACT_APP_VERSION=0.0.0
ENV REACT_APP_GIT_SHA=$REACT_APP_GIT_SHA \
    REACT_APP_VERSION=$REACT_APP_VERSION \
    DISABLE_ESLINT_PLUGIN=true \
    CI=true

RUN yarn build

FROM nginx:1.27-alpine AS production
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 3000
ENTRYPOINT ["/docker-entrypoint.sh"]
