FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY blackboard_service/ ./blackboard_service/

CMD ["uvicorn", "blackboard_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
