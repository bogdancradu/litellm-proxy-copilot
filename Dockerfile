FROM ghcr.io/berriai/litellm:main-stable

RUN apk add --no-cache nodejs npm git ca-certificates
RUN npm install -g @modelcontextprotocol/server-memory @modelcontextprotocol/server-filesystem @modelcontextprotocol/server-sequential-thinking

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY config.yaml ./config.yaml
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

EXPOSE 4000
EXPOSE 4001

COPY run_proxy.py ./run_proxy.py
