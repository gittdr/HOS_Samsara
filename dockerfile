# --- DOCKERFILE LOCAL ---

# FROM amazonlinux:2023

# # Paquetes base (NO instalamos 'curl' para no pelear con curl-minimal)
# RUN dnf -y install \
#     python3 \
#     python3-pip \
#     unixODBC \
#     unixODBC-devel \
#     tzdata \
#     shadow-utils \
#     && dnf clean all

# # Aceptar EULA de Microsoft antes de instalar el driver
# ENV ACCEPT_EULA=Y

# # Agregar repo de Microsoft y instalar el driver ODBC 18
# RUN rpm --import https://packages.microsoft.com/keys/microsoft.asc && \
#     curl -sSL -o /etc/yum.repos.d/msprod.repo \
#         https://packages.microsoft.com/config/rhel/9/prod.repo && \
#     dnf -y install msodbcsql18 && \
#     dnf clean all

# # (Opcional) Verificaciones en build para que falle temprano si algo falta
# RUN odbcinst -q -d || true && \
#     ls -l /opt/microsoft/msodbcsql18/lib64/ || true && \
#     grep -A2 "ODBC Driver 18 for SQL Server" /etc/odbcinst.ini || true

# # Trabajo y app
# WORKDIR /app
# COPY requirements.txt .
# RUN pip3 install --no-cache-dir -r requirements.txt
# COPY app/ ./app
# COPY main.py .

# # Usuario no root
# RUN useradd -m appuser && chown -R appuser:appuser /app
# USER appuser

# CMD ["python3", "main.py"]



# --- DOCKERFILE PARA LAMBDA ---

# Base oficial de Lambda (Python 3.11 sobre AL2023)
FROM public.ecr.aws/lambda/python:3.12

# Ser root para instalar paquetes
USER root

# 1) Dependencias del SO (solo runtime, sin -devel) + certificados
RUN dnf -y update && \
    dnf -y install unixODBC ca-certificates curl-minimal && \
    dnf clean all

# 2) Repositorio de Microsoft + Driver ODBC 18 (AL2023 ~ RHEL9)
RUN curl -fsSLo /tmp/microsoft.asc https://packages.microsoft.com/keys/microsoft.asc && \
    rpm --import /tmp/microsoft.asc && \
    curl -fsSLo /etc/yum.repos.d/msprod.repo https://packages.microsoft.com/config/rhel/9/prod.repo && \
    ACCEPT_EULA=Y dnf -y install msodbcsql18 mssql-tools18 && \
    dnf clean all && rm -f /tmp/microsoft.asc

# 3) Garantiza que el loader vea las libs del driver
ENV LD_LIBRARY_PATH=/opt/microsoft/msodbcsql18/lib64:/usr/lib64:${LD_LIBRARY_PATH}

# 4) Registra el driver en /etc/odbcinst.ini apuntando al .so real
#    (buscamos el .so instalado y lo escribimos en odbcinst.ini)
RUN DRIVER_FILE=$(ls /opt/microsoft/msodbcsql18/lib64/libmsodbcsql-*.so* | head -n1) \
    RUN set -e; \
    DRIVER_DIR="/opt/microsoft/msodbcsql18/lib64"; \
    DRIVER_FILE="$(ls -1 ${DRIVER_DIR}/libmsodbcsql-*.so* | head -n1)"; \
    if [ -z "${DRIVER_FILE}" ]; then echo "ERROR: msodbcsql18 not found"; exit 1; fi; \
    echo "Detectado DRIVER_FILE=${DRIVER_FILE}"; \
    ln -sf "${DRIVER_FILE}" "${DRIVER_DIR}/libmsodbcsql18.so"; \
    printf "[ODBC Driver 18 for SQL Server]\nDescription=Microsoft ODBC Driver 18 for SQL Server\nDriver=%s\nUsageCount=1\n" "${DRIVER_DIR}/libmsodbcsql18.so" > /etc/odbcinst.ini; \
    chmod 0644 /etc/odbcinst.ini

ENV ODBCSYSINI=/etc
ENV ODBCINSTINI=odbcinst.ini

# 6) Dependencias Python (pyodbc requiere unixODBC ya instalado)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 7) Copia el código
COPY app/ ${LAMBDA_TASK_ROOT}/app/
COPY main.py ${LAMBDA_TASK_ROOT}/

# (Opcional) Variable para el registro de drivers ODBC
ENV ODBCINSTINI=/etc/odbcinst.ini

# 5) Define el handler de Lambda (modulo.funcion)
CMD ["main.lambda_handler"]


# ---- DEPLOY POWERSHELL ----
# # build
# docker build -t lambda-image-hosamsara:latest .

# # tag & push
# docker tag lambda-image-hosamsara:latest 724064605175.dkr.ecr.mx-central-1.amazonaws.com/samsara/hos:latest
# aws ecr get-login-password --region mx-central-1 | docker login --username AWS --password-stdin 724064605175.dkr.ecr.mx-central-1.amazonaws.com
# docker push 724064605175.dkr.ecr.mx-central-1.amazonaws.com/samsara/hos:latest

# PowerShell
# $env:DOCKER_BUILDKIT=0
# docker build -t 724064605175.dkr.ecr.mx-central-1.amazonaws.com/samsara/hos:latest .
# aws ecr get-login-password --region mx-central-1 | docker login --username AWS --password-stdin 724064605175.dkr.ecr.mx-central-1.amazonaws.com
# docker push 724064605175.dkr.ecr.mx-central-1.amazonaws.com/samsara/hos:latest


