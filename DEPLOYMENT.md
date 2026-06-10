# Deployment Guide for Agents Microservice

## Overview

The Agents microservice is a Python FastAPI application that provides LangGraph orchestration for task planning and assignment. This guide covers deployment options and best practices.

## Deployment Options

### Option 1: Docker Compose (Local Development)

**Best for:** Development, testing, small deployments

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f agents-api

# Stop
docker-compose down
```

**Pros:**
- Simple setup
- Includes Ollama container
- Easy local development

**Cons:**
- Not suitable for production
- Limited scalability
- Single point of failure

### Option 2: Railway (Recommended for Production)

**Best for:** Production, easy deployment, auto-scaling

**Steps:**
1. Create Railway account at https://railway.app
2. Connect your GitHub repository
3. Select the `Agents` folder
4. Configure environment variables
5. Deploy

**Environment Variables:**
```env
DATABASE_URL=postgresql://user:pass@host:5432/dbname
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://your-ollama-service:11434
OLLAMA_MODEL=llama3.1
LLM_MODE=live
```

**Pros:**
- Zero-config deployment
- Auto-scaling
- Built-in monitoring
- Free tier available

**Cons:**
- Requires separate Ollama deployment
- Limited control over infrastructure

### Option 3: Render (Alternative to Railway)

**Best for:** Production, simple deployment

**Steps:**
1. Create Render account at https://render.com
2. Connect GitHub repository
3. Create new Web Service
4. Select Dockerfile
5. Configure environment variables
6. Deploy

**Pros:**
- Simple deployment
- Free SSL certificates
- Auto-scaling
- Good documentation

**Cons:**
- Cold starts on free tier
- Limited free tier

### Option 4: AWS ECS (Enterprise)

**Best for:** Large-scale production, enterprise requirements

**Architecture:**
- ECS Fargate for container orchestration
- RDS PostgreSQL for database
- Application Load Balancer
- CloudWatch for monitoring

**Steps:**
1. Push Docker image to ECR
2. Create ECS task definition
3. Configure ECS cluster
4. Set up ALB
5. Configure environment variables
6. Deploy

**Pros:**
- Highly scalable
- Full control
- Enterprise features
- Cost-effective at scale

**Cons:**
- Complex setup
- Higher learning curve
- More expensive for small deployments

### Option 5: DigitalOcean App Platform

**Best for:** Mid-size production, balance of simplicity and control

**Steps:**
1. Create DigitalOcean account
2. Create new App
3. Connect GitHub repository
4. Configure build settings (Dockerfile)
5. Set environment variables
6. Deploy

**Pros:**
- Simple deployment
- Good performance
- Predictable pricing
- Developer-friendly

**Cons:**
- Smaller ecosystem than AWS
- Less enterprise features

## Ollama Deployment Options

### Option 1: Self-Hosted Ollama (Recommended)

**Docker Compose:**
```yaml
ollama:
  image: ollama/ollama:latest
  ports:
    - "11434:11434"
  volumes:
    - ollama_data:/root/.ollama
```

**Dedicated Server:**
- Rent a GPU server (e.g., Lambda Labs, RunPod)
- Install Ollama
- Configure firewall
- Use as external service

### Option 2: Cloud Ollama Services

**RunPod:**
- GPU instances with Ollama pre-installed
- Pay-as-you-go pricing
- Good for variable workloads

**Lambda Labs:**
- High-performance GPU instances
- Good for heavy workloads
- Competitive pricing

### Option 3: Use Groq Instead

If you prefer not to self-host Ollama:
```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_api_key
GROQ_MODEL=llama-3.3-70b-versatile
```

**Pros:**
- No infrastructure to manage
- Fast inference
- Generous free tier

**Cons:**
- Rate limits
- API costs at scale
- Dependency on external service

## Production Configuration

### Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# LLM Provider
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama-service:11434
OLLAMA_MODEL=llama3.1

# Or use Groq
# LLM_PROVIDER=groq
# GROQ_API_KEY=your_api_key
# GROQ_MODEL=llama-3.3-70b-versatile

# Mode
LLM_MODE=live

# Retry Configuration
LLM_MAX_RETRIES=5
LLM_INITIAL_BACKOFF=1.0
LLM_MAX_BACKOFF=60.0

# Performance
WORKERS=4
LOG_LEVEL=info
```

### Security Best Practices

1. **Use Secrets Management**
   - Never commit API keys
   - Use environment variables
   - Rotate credentials regularly

2. **Network Security**
   - Use HTTPS in production
   - Configure firewall rules
   - Use VPC for cloud deployments

3. **Database Security**
   - Use connection pooling
   - Enable SSL for database connections
   - Regular backups

4. **API Security**
   - Add authentication to `/api/orchestrate`
   - Rate limiting
   - Input validation
   - CORS configuration

### Performance Optimization

1. **Scaling**
   - Horizontal scaling with load balancer
   - Configure appropriate worker count
   - Use connection pooling

2. **Caching**
   - Cache LLM responses when possible
   - Use Redis for distributed caching
   - Cache database queries

3. **Monitoring**
   - Add application monitoring (Sentry, Datadog)
   - Log aggregation (ELK, CloudWatch)
   - Performance metrics (Prometheus)

### Database Configuration

**Connection Pooling:**
```python
# In db/session.py
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

**Recommended:**
- Use managed PostgreSQL (RDS, Neon, Supabase)
- Enable read replicas for scaling
- Regular backups

## CI/CD Pipeline

### GitHub Actions Example

```yaml
name: Deploy Agents

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker image
        run: docker build -t agents-api .
      
      - name: Push to registry
        run: docker push your-registry/agents-api
      
      - name: Deploy to production
        run: # Your deployment command
```

## Monitoring & Logging

### Health Checks

```bash
# Health endpoint
curl http://your-api/api/health
```

### Logging

- Use structured logging (JSON)
- Include request IDs
- Log errors with stack traces
- Set up log retention policies

### Metrics to Track

- Request latency
- Error rate
- LLM response time
- Database query time
- Memory/CPU usage

## Cost Optimization

### Ollama Self-Hosting
- GPU instance: $0.50-$2.00/hour
- Storage: Minimal
- Network: Depends on usage

### Groq API
- Free tier: 30 requests/minute
- Paid: $0.59/1M tokens (varies by model)

### Cloud Hosting
- Railway: Free tier available
- Render: Free tier available
- AWS: $20-100/month depending on scale

## Recommended Setup

**For Development:**
- Docker Compose with local Ollama
- Local PostgreSQL

**For Production (Small Team):**
- Railway or Render for API
- Self-hosted Ollama on GPU server
- Managed PostgreSQL (Neon, Supabase)

**For Production (Enterprise):**
- AWS ECS or GCP Cloud Run
- Self-hosted Ollama on GPU instances
- AWS RDS or Cloud SQL
- CloudWatch/Datadog for monitoring

## Troubleshooting

### Common Issues

1. **Ollama Connection Timeout**
   - Check Ollama is running
   - Verify network connectivity
   - Check firewall rules

2. **Database Connection Errors**
   - Verify DATABASE_URL
   - Check database is accessible
   - Verify credentials

3. **High Memory Usage**
   - Reduce worker count
   - Add memory limits to containers
   - Monitor LLM response sizes

4. **Slow Response Times**
   - Use faster LLM model
   - Add caching
   - Optimize database queries
