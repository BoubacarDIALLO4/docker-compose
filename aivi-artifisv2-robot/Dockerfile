FROM amd64/python:3.7-slim-buster

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

RUN find . -type f -iname "*.sh" -exec chmod +x {} \;

CMD [ "python3", "-u", "./main.py" ]