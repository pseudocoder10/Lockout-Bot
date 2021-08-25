FROM python:3.8.2-buster

# Copy files to /app
ADD . ./app

# Set workdir
WORKDIR /app

# Install dependencies
RUN apt-get install -y make automake gcc g++

# Install python dependencies
RUN pip install -r requirements.txt

# Run the bot
CMD ["python", "main.py"]
