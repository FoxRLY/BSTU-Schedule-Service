FROM python:latest

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY src/ ./app
RUN pip install -r app/requirements.txt

CMD ["python", "-u", "/app/main.py"]

