# ══════════════════════════════════════════════
# 镜像源（通过 docker compose --build-arg 或 .env 覆盖）
# ══════════════════════════════════════════════
ARG NODE_IMAGE=node:22-alpine
ARG PYTHON_IMAGE=python:3.11-slim-bullseye

# ══════════════════════════════════════════════
# Stage 1: 前端构建
# ══════════════════════════════════════════════
FROM ${NODE_IMAGE} AS web-builder

WORKDIR /opt/VansRSA/web
COPY /web/package.json /web/pnpm-lock.yaml /web/pnpm-workspace.yaml ./
RUN corepack enable && corepack prepare pnpm@latest --activate && pnpm install --frozen-lockfile

COPY /web ./
RUN pnpm build


# ══════════════════════════════════════════════
# Stage 2: 生产镜像 (Python + Nginx)
# ══════════════════════════════════════════════
FROM ${PYTHON_IMAGE}

WORKDIR /opt/VansRSA
ADD . .
COPY /deploy/entrypoint.sh .

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=core-apt \
    --mount=type=cache,target=/var/lib/apt,sharing=locked,id=core-apt \
    sed -i "s@http://.*.debian.org@http://mirrors.ustc.edu.cn@g" /etc/apt/sources.list \
    && rm -f /etc/apt/apt.conf.d/docker-clean \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc python3-dev \
        bash nginx vim curl procps net-tools \
        libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
        libharfbuzz0b libffi7 shared-mime-info

RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY --from=web-builder /opt/VansRSA/web/dist /opt/VansRSA/web/dist

ADD /deploy/web.conf /etc/nginx/sites-available/web.conf
RUN rm -f /etc/nginx/sites-enabled/default \
    && ln -s /etc/nginx/sites-available/web.conf /etc/nginx/sites-enabled/

ENV LANG=zh_CN.UTF-8
EXPOSE 80

ENTRYPOINT [ "sh", "entrypoint.sh" ]
