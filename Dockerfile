FROM jupyter/scipy-notebook:latest

WORKDIR /app

# Installation des outils pour traiter tes gros CSV
RUN pip install --no-cache-dir duckdb polars

# Activer JupyterLab par défaut
ENV JUPYTER_ENABLE_LAB=yes

# Lancement sans token/mot de passe en dev local
CMD ["start-notebook.sh", "--NotebookApp.token=''"]