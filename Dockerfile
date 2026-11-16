FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY livraria_agentes ./livraria_agentes
COPY dados/loja_inicial.json ./dados/loja_inicial.json
COPY config/paises ./config/paises
RUN pip install --no-cache-dir .
# Pedidos e conversas ficam aqui: monte um disco persistente neste caminho.
ENV LIVRARIA_DADOS=/dados
ENV PORT=8000
# País da loja: mz (Moçambique), sz (Eswatini), za (África do Sul), cd (RD Congo)
ENV LIVRARIA_PAIS=mz
EXPOSE 8000
CMD ["python", "-m", "livraria_agentes.servidor"]
