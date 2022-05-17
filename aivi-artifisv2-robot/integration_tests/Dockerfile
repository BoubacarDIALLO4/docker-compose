FROM python:3.9

COPY requirements.txt ./
RUN pip install -r requirements.txt

WORKDIR /app

COPY . .

RUN find ./scripts/ -type f -iname "*.sh" -exec chmod +x {} \;