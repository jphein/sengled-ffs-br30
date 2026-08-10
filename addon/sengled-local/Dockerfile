ARG BUILD_FROM
FROM ${BUILD_FROM}

# SengledTools ships NO LICENSE file, so its source carries no granted
# redistribution permission. We therefore CLONE it at build time on the user's
# own machine rather than vendoring a copy into this add-on -- nothing upstream
# is redistributed by us. The ref is pinned in build.yaml for reproducibility.
ARG SENGLEDTOOLS_REPO
ARG SENGLEDTOOLS_REF

# py3-cryptography comes from apk on purpose: it carries a compiled extension and
# building it with pip on Alpine drags in rust + gcc. psutil is deliberately NOT
# apk'd: amqtt requires psutil>=7.0.0, and pip cannot cleanly uninstall Alpine's
# distutils-packaged psutil 5.9.6 to upgrade it (the build aborts on
# "Cannot uninstall 'psutil'"). Let pip pull a prebuilt musllinux psutil wheel
# from HA's wheel index instead -- still no compile.
RUN apk add --no-cache \
        python3 \
        py3-pip \
        py3-cryptography \
        git \
    && pip3 install --no-cache-dir --break-system-packages \
        "amqtt" \
        "paho-mqtt" \
        "psutil"

# Fetch upstream at the pinned revision, keep only the library package.
RUN git clone --quiet "${SENGLEDTOOLS_REPO}" /tmp/sengledtools \
    && git -C /tmp/sengledtools checkout --quiet "${SENGLEDTOOLS_REF}" \
    && mkdir -p /opt/sengled-upstream \
    && cp -r /tmp/sengledtools/sengled /opt/sengled-upstream/sengled \
    && rm -rf /tmp/sengledtools

COPY rootfs /

RUN chmod a+x /usr/local/sengled-local/run.sh

WORKDIR /usr/local/sengled-local
CMD [ "/usr/local/sengled-local/run.sh" ]
