FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY livraria_agentes ./livraria_agentes
COPY dados/loja_inicial.json ./dados/loja_inicial.json
RUN pip install --no-cache-dir .
# Pedidos e conversas ficam aqui: monte um disco persistente neste caminho.
ENV LIVRARIA_DADOS=/dados
ENV PORT=8000
EXPOSE 8000
CMD ["python", "-m", "livraria_agentes.servidor"]
