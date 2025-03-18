# Base image
FROM dockerhub.paypalcorp.com/python:3.9

# Set working directory
WORKDIR /rmr_agent

# Certificates 
ENV CURL_CA_BUNDLE=''

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


# Install dependencies (including from your enterprise Artifactory)
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --trusted-host artifactory.paypalcorp.com -i https://artifactory.paypalcorp.com/artifactory/api/pypi/paypal-python-all/simple rmr_agent==0.1.0


# Expose the port your app will run on
EXPOSE 8000

# Run the FastAPI app with Uvicorn
CMD ["rmr_agent", "--host", "0.0.0.0", "--port", "8000"]