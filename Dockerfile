ARG BRANCH=master
FROM docker.io/endlessm/eos:${BRANCH}
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y \
        appstream-util \
        flake8 \
        gettext \
        git \
        itstool \
        make \
        shellcheck \
        && \
    apt-get clean
