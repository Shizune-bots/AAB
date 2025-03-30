FROM python:3.10-slim-buster

WORKDIR /usr/src/app

# Set proper permissions
RUN chmod 777 /usr/src/app

# Update system and install necessary packages, including aria2
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y \
    git wget pv jq python3-dev mediainfo gcc \
    libsm6 libxext6 libfontconfig1 libxrender1 libgl1-mesa-glx aria2

# Copy static FFmpeg binaries
COPY --from=mwader/static-ffmpeg:6.1 /ffmpeg /bin/ffmpeg
COPY --from=mwader/static-ffmpeg:6.1 /ffprobe /bin/ffprobe

# Copy project files
COPY . .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Start the bot
CMD ["bash", "run.sh"]