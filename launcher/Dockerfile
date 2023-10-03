FROM python:3.11-slim
WORKDIR /usr/src/app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN rm requirements.txt

COPY launch.py .
EXPOSE 8080

CMD ["python", "launch.py"]
