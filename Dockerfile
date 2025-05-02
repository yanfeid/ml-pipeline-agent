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

# Expose the port the app will run on
EXPOSE 8000

# Run application
CMD ["python", "run_api.py"]