# Docker Deployment Guide

This guide explains how to run the Fooocus Telegram Bot using Docker Compose.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose v2.0+
- For GPU support: NVIDIA GPU with NVIDIA Container Toolkit installed

### Installing NVIDIA Container Toolkit (for GPU support)

```bash
# Add the package repositories
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install nvidia-container-toolkit
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Restart Docker
sudo systemctl restart docker
```

## Quick Start

1. **Set up your environment variables**:
   ```bash
   cp .env.example .env
   nano .env  # Edit and add your BOT_TOKEN
   ```

2. **Start the services** (with GPU):
   ```bash
   docker compose up -d
   ```

   Or for CPU-only systems:
   ```bash
   docker compose -f docker-compose.cpu.yml up -d
   ```

3. **Check the logs**:
   ```bash
   # View all logs
   docker compose logs -f

   # View bot logs only
   docker compose logs -f telegram-bot

   # View Fooocus API logs only
   docker compose logs -f fooocus-api
   ```

## Configuration

### Environment Variables

Edit your `.env` file:

```env
BOT_TOKEN=your_telegram_bot_token_here
```

The `FOOOCUS_IP` and `FOOOCUS_PORT` are automatically configured in the docker-compose.yml to use the service name `fooocus-api`.

### Volumes

The setup uses Docker volumes to persist data:

- `fooocus-models`: Stores downloaded AI models
- `fooocus-outputs`: Stores generated images

To inspect volumes:
```bash
docker volume ls
docker volume inspect fooocus-tg-bot_fooocus-models
```

## Common Commands

### Start services
```bash
docker compose up -d
```

### Stop services
```bash
docker compose down
```

### Restart services
```bash
docker compose restart
```

### View logs
```bash
docker compose logs -f
```

### Rebuild after code changes
```bash
docker compose up -d --build
```

### Remove everything (including volumes)
```bash
docker compose down -v
```

## Troubleshooting

### Bot can't connect to Fooocus API

1. Check if Fooocus API is healthy:
   ```bash
   docker compose ps
   docker compose logs fooocus-api
   ```

2. Verify the health check:
   ```bash
   docker exec fooocus-api curl -f http://localhost:8888/ping
   ```

### GPU not detected

1. Verify NVIDIA Container Toolkit is installed:
   ```bash
   docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
   ```

2. Check Docker daemon configuration:
   ```bash
   cat /etc/docker/daemon.json
   ```

   Should contain:
   ```json
   {
     "runtimes": {
       "nvidia": {
         "path": "nvidia-container-runtime",
         "runtimeArgs": []
       }
     }
   }
   ```

### Out of memory

If you're running out of memory, you can limit container resources in `docker-compose.yml`:

```yaml
services:
  fooocus-api:
    # ... other config ...
    deploy:
      resources:
        limits:
          memory: 8G
        reservations:
          memory: 4G
```

### First run takes a long time

The first time you run Fooocus, it needs to download AI models (several GB). This is normal. Monitor progress:

```bash
docker compose logs -f fooocus-api
```

## Using External Fooocus Instance

If you already have Fooocus running elsewhere, you can run only the bot:

1. Create a minimal `docker-compose.override.yml`:
   ```yaml
   version: '3.8'
   
   services:
     telegram-bot:
       environment:
         - FOOOCUS_IP=your.fooocus.host
         - FOOOCUS_PORT=8888
   ```

2. Remove the fooocus-api service from the main compose file, or run:
   ```bash
   docker compose up telegram-bot
   ```

## Production Considerations

1. **Use secrets management** instead of `.env` files for sensitive data
2. **Set up log rotation** to prevent disk space issues
3. **Configure backups** for the volumes
4. **Use a reverse proxy** (nginx/traefik) if exposing Fooocus API
5. **Monitor resource usage** with tools like Prometheus/Grafana

## Updating

To update to the latest versions:

```bash
# Pull latest images
docker compose pull

# Rebuild and restart
docker compose up -d --build
```
