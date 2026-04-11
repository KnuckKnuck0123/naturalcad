FROM continuumio/miniconda3:latest

# Install system libraries
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    CONDA_DIR=/opt/conda

WORKDIR $HOME/app

# Create conda environment and install just the native dependencies (ocp/cadquery-ocp)
RUN conda create -n cad python=3.10 -y && \
    conda install -n cad -c conda-forge "ocp>=7.8,<7.9" -y && \
    conda clean -a -y

ENV PATH=$CONDA_DIR/envs/cad/bin:$PATH

# Install pip requirements including build123d
COPY --chown=user requirements.txt .
RUN $CONDA_DIR/envs/cad/bin/pip install --no-cache-dir --upgrade pip && \
    $CONDA_DIR/envs/cad/bin/pip install --no-cache-dir -r requirements.txt

# Setup app
RUN mkdir -p artifacts/runs artifacts/logs
COPY --chown=user . .

EXPOSE 7860
CMD ["/opt/conda/envs/cad/bin/python", "app.py"]
