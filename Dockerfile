FROM jupyter/scipy-notebook:latest

WORKDIR /app

# Dependances Python du projet (voir requirements.txt pour le detail
# des versions et les contraintes de compatibilite).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Activer JupyterLab par defaut
ENV JUPYTER_ENABLE_LAB=yes

# Lancement sans token/mot de passe en dev local
CMD ["start-notebook.sh", "--NotebookApp.token=''"]
