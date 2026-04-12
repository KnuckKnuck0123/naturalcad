FROM condaforge/miniforge3:latest

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user && \
    chown -R user:user /opt/conda

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    CONDA_DIR=/opt/conda

WORKDIR $HOME/app

RUN conda config --system --remove-key channels || true && \
    conda config --system --add channels conda-forge && \
    conda config --system --set channel_priority strict && \
    conda create -n cad python=3.10 ocp=7.8.1 -y && \
    conda clean -a -y

ENV PATH=$CONDA_DIR/envs/cad/bin:$PATH
ENV LD_LIBRARY_PATH=$CONDA_DIR/envs/cad/lib:$LD_LIBRARY_PATH

RUN pip install --no-cache-dir --upgrade pip

# Install all the python dependencies of build123d manually, except cadquery-ocp
RUN pip install --no-cache-dir \
    "typing_extensions<5,>=4.6.0" \
    "numpy" \
    "svgpathtools<2,>=1.5.1" \
    "anytree<3,>=2.8.0" \
    "ezdxf<2,>=1.1.0" \
    "ipython<10,>=8.0.0" \
    "lib3mf>=2.4.1" \
    "ocpsvg<0.6,>=0.5" \
    "ocp_gordon>=0.1.17" \
    "trianglesolver" \
    "sympy" \
    "scipy" \
    "webcolors"

# Now install build123d without letting it try to pull cadquery-ocp
RUN pip install --no-cache-dir --no-deps build123d==0.10.0

# Smoke test the CAD runtime during image build so bad native combos fail early
RUN python -c "from build123d import export_stl, export_step; print('build123d import ok')"

COPY --chown=user requirements.txt .
# Remove build123d from pip requirements since we just handled it
RUN grep -v "build123d" requirements.txt > reqs_no_cad.txt && \
    pip install --no-cache-dir -r reqs_no_cad.txt

RUN mkdir -p artifacts/runs artifacts/logs

COPY --chown=user . .

EXPOSE 7860
CMD ["/opt/conda/envs/cad/bin/python", "app.py"]
