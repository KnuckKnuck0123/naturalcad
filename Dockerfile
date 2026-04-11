FROM continuumio/miniconda3:latest

# Install system libraries that OpenCascade/Gradio often require
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

# Set up conda environment with build123d from conda-forge
RUN conda create -n cad python=3.10 -y && \
    conda install -n cad -c conda-forge build123d=0.10.0 -y && \
    conda clean -a -y

# We need conda in the path
ENV PATH=$CONDA_DIR/envs/cad/bin:$PATH

# Install the rest of the python requirements via pip
COPY --chown=user requirements.txt .
# Remove build123d from pip requirements since conda handles it
RUN grep -v "build123d" requirements.txt > reqs_no_cad.txt && \
    $CONDA_DIR/envs/cad/bin/pip install --no-cache-dir -r reqs_no_cad.txt

# Create necessary directories and set permissions
RUN mkdir -p artifacts/runs artifacts/logs

# Copy the rest of the application
COPY --chown=user . .

# Hugging Face exposes port 7860 by default
EXPOSE 7860

# Run the app using the conda environment
CMD ["/opt/conda/envs/cad/bin/python", "app.py"]
