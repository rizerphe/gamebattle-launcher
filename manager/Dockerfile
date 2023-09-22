FROM python:3.11-alpine

RUN apk --no-cache add docker git openssl

RUN pip install uvicorn
RUN pip install git+https://github.com/rizerphe/gamebattle-backend.git

WORKDIR /app
COPY gamebattle /app/gamebattle

ENV GAMES_PATH=/app/gamebattle
ENV NETWORK=gamebattle

ENV GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json

EXPOSE 8000
CMD ["uvicorn", "gamebattle_backend.api:launch_app", "--factory", "--host", "0.0.0.0"]
