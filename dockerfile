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

# -- STAGE 1: BUILDER (Amazon Linux 2023) --
FROM amazonlinux:2023 AS builder

# Aceptar EULA de Microsoft para instalar msodbcsql18 sin TTY
ENV ACCEPT_EULA=Y

# Paquetes del sistema necesarios para ODBC + pip
RUN dnf -y install \
    python3 python3-pip \
    unixODBC unixODBC-devel \
    tzdata \
    && dnf clean all

# Repo de Microsoft + Driver ODBC 18
RUN rpm --import https://packages.microsoft.com/keys/microsoft.asc && \
    curl -sSL -o /etc/yum.repos.d/msprod.repo https://packages.microsoft.com/config/rhel/9/prod.repo && \
    dnf -y install msodbcsql18 && \
    dnf clean all

# Sanity checks en build (no fallan la build si algo cambia)
RUN odbcinst -q -d || true && \
    grep -A2 "ODBC Driver 18 for SQL Server" /etc/odbcinst.ini || true && \
    ls -l /opt/microsoft/msodbcsql18/lib64/ || true

# Instalar dependencias Python en carpeta portable
WORKDIR /opt/app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt -t /opt/python


# -- STAGE 2: RUNTIME (AWS Lambda Python 3.11) --
FROM public.ecr.aws/lambda/python:3.11

# Copiar dependencias Python al root de la función
COPY --from=builder /opt/python ${LAMBDA_TASK_ROOT}/

# Copiar runtime ODBC (Driver Manager + driver MS) y registro
COPY --from=builder /usr/lib64/libodbc* /usr/lib64/
COPY --from=builder /opt/microsoft /opt/microsoft
COPY --from=builder /etc/odbcinst.ini /etc/odbcinst.ini

# (Opcional) variable para el registro de drivers ODBC
ENV ODBCINSTINI=/etc/odbcinst.ini

# Copiar el código de la función
COPY app/ ${LAMBDA_TASK_ROOT}/app/
COPY main.py ${LAMBDA_TASK_ROOT}/

# Handler de Lambda (archivo main.py, función lambda_handler)
CMD ["main.lambda_handler"]

