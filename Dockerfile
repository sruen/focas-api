FROM python:3.12-slim

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir .

ENV PORT=8787
EXPOSE 8787

CMD ["python", "-m", "focas_api.server"]
