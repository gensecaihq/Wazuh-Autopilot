# Mock Wazuh MCP Server — demo stand-in for gensecaihq/Wazuh-MCP-Server v4.3.0
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MOCK_HOST=0.0.0.0 MOCK_PORT=3000
RUN useradd --create-home --uid 10001 mock
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mock_wazuh ./mock_wazuh

USER mock
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,json,sys; sys.exit(0 if json.load(urllib.request.urlopen('http://127.0.0.1:3000/health', timeout=4))['status']=='healthy' else 1)"
ENTRYPOINT ["python", "-m", "mock_wazuh"]
