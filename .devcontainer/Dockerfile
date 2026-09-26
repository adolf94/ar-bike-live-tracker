# Dev container image: the official Python devcontainer base plus Node.js/npm.
#
# devcontainer.json uses "dockerComposeFile", and the Dev Containers spec IGNORES
# the "features" property in that mode -- so Node cannot be added as a feature
# and has to be baked into the image here instead.
#
# Node/npm are installed from the official tarball into /usr/local with the
# binaries linked into /usr/local/bin (the same approach the official node image
# uses). That makes node/npm resolve for every shell and user, including
# non-interactive ones: postCreateCommand, VS Code tasks, and
# `docker compose exec`. An nvm-based install is not used because it only hooks
# into interactive bash and silently picks a different major version.
#
# Keep NODE_VERSION in sync with `node-version` in
# .github/workflows/azure-static-web-apps-*.yml, since that is what builds and
# deploys the frontend.

FROM mcr.microsoft.com/devcontainers/python:3.13

ARG NODE_VERSION=22.23.3
ARG NPM_VERSION=10.9.9

# curl/ca-certificates are usually already present in this base, but a base image
# bump should not be able to break the install below.
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates xz-utils && \
    rm -rf /var/lib/apt/lists/*

# `node --version` / `npm --version` at the end fail the build here rather than
# much later inside postCreateCommand.
RUN set -eux; \
    case "$(dpkg --print-architecture)" in \
        amd64) node_arch=x64 ;; \
        arm64) node_arch=arm64 ;; \
        *) echo "unsupported architecture: $(dpkg --print-architecture)" >&2; exit 1 ;; \
    esac; \
    tarball="node-v${NODE_VERSION}-linux-${node_arch}.tar.xz"; \
    curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/${tarball}" -o "/tmp/${tarball}"; \
    tar -xJf "/tmp/${tarball}" -C /usr/local --strip-components=1 --no-same-owner; \
    rm -f "/tmp/${tarball}"; \
    npm install -g "npm@${NPM_VERSION}"; \
    node --version; \
    npm --version
