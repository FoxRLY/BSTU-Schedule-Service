FROM python:latest

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN mkdir /app
COPY src/requirements.txt app/
RUN pip install -r app/requirements.txt
COPY src/ /app

CMD ["python", "-u", "/app/main.py"]

