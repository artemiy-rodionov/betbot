FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN apt-get update && apt-get upgrade -y && apt-get autoremove && apt-get autoclean
RUN apt-get install -y libsqlite3-dev
RUN mkdir /code
WORKDIR /code
ADD uv.lock pyproject.toml /code

RUN mkdir /code/instance
ADD betbot /code/betbot
ADD run.py /code
ADD config.py /code
RUN uv sync --locked
ENTRYPOINT ["uv", "run", "run.py"]
