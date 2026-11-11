# Este arquivo foi feito para rodar o Dashboard do aplicativo usando containers

# para rodar, baixe o docker ou podman e execute o commando build nessa imagem, Exemplo: 'podman build -t icmpmaster-run .'
# logo após execute a imagem expondo o porte do localhost núumero 8501. Exemplo: 'podman run -p 8501:8501 icmpmaster-run'

# a imagem necessita de 1.93 GB de armazenamento.

FROM python:3.11.18-alpine

COPY . /app

WORKDIR /app

RUN apk add --no-cache \
    musl \
    build-base

RUN pip3 install --break-system-packages -r requirements.txt

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]