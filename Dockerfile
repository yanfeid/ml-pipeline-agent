# Base image
FROM python:3.12.6

# Certificates 
ENV CURL_CA_BUNDLE=''

# Project label
LABEL project="rmr-agent-service"

# Set the working directory
WORKDIR /rmr_agent

# Copy and install dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip --index-url https://artifactory.paypalcorp.com/artifactory/api/pypi/paypal-python-all/simple  \
    && pip install -r requirements.txt --index-url https://artifactory.paypalcorp.com/artifactory/api/pypi/paypal-python-all/simple

# Copy the the entire project directory including the app code
COPY . .

# Set environment variables
ARG azure_client_id
ARG azure_client_secret
ARG azure_scope
ARG gpt_endpoint

ENV AZURE_ACCESS_API https://login.microsoftonline.com/fb007914-6020-4374-977e-21bac5f3f4c8/oauth2/v2.0/token
ENV AZURE_CLIENT_ID ${azure_client_id}
ENV AZURE_CLIENT_SECRET ${azure_client_secret}
ENV AZURE_SCOPE ${azure_scope}
ENV GPT_ENDPOINT ${gpt_endpoint}

# Expose the port the app will run on
EXPOSE 8000

# Run application
CMD ["python", "run_api.py"]