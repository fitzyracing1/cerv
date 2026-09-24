FROM python:3.12-slim
WORKDIR /app
COPY mock_server.py /app/mock_server.py
COPY data /app/data
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/health')"
CMD ["python", "mock_server.py", "--port", "3000", "--host", "0.0.0.0"]
