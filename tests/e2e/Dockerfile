# The desktop the end-to-end tests run Ynote on: what the package depends
# on, a virtual X server with a window manager, and what the tests drive the
# app and read its results with. Built for each Ubuntu release tested:
#
#     docker build --build-arg BASE=ubuntu:26.04 -t ynote-e2e:26.04 tests/e2e
ARG BASE=ubuntu:26.04
FROM ${BASE}
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
        python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1 \
        gir1.2-ayatanaappindicator3-0.1 \
        xvfb xauth openbox dbus dbus-x11 \
        at-spi2-core gir1.2-atspi-2.0 libatk-adaptor \
        ibus ibus-hangul ibus-gtk3 \
        python3-xlib python3-pytest \
        fonts-ubuntu fonts-noto-core fonts-noto-cjk fonts-noto-color-emoji \
        fonts-dejavu-core \
        desktop-file-utils gtk-update-icon-cache \
    && rm -rf /var/lib/apt/lists/*
# A desktop's locale, as Ubuntu sets up: Pango picks fallback fonts by it,
# such as the Korean font for Hangul in a heading.
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends locales \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i 's/^# *\(en_US.UTF-8\)/\1/' /etc/locale.gen && locale-gen
ENV LANG=en_US.UTF-8
