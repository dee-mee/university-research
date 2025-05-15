# Installation Guide

## Prerequisites

### Required Software
- Python 3.8 or higher
- PostgreSQL 12 or higher
- Node.js 14 or higher
- Redis (for WebSocket support)
- Git

### Required Hardware
- Minimum 4GB RAM
- Minimum 2 CPU cores
- 20GB+ free disk space
- Stable internet connection

## Installation Steps

### 1. Clone the Repository
```bash
git clone https://github.com/your-repo/university-research.git
cd university-research
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install Node.js Dependencies
```bash
npm install
```

### 5. Configure Environment
Create a `.env` file in the project root with the following variables:
```
DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 6. Database Setup
```bash
# Create database
createdb your_database_name

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### 7. Collect Static Files
```bash
python manage.py collectstatic
```

### 8. Start Services

#### Development Mode
```bash
# Start Django development server
python manage.py runserver

# Start Redis server
redis-server
```

#### Production Mode
```bash
# Start Gunicorn
pip install gunicorn
gunicorn research_portal.wsgi:application --bind 0.0.0.0:8000

# Start Redis
redis-server

# Start Celery worker
pip install celery
celery -A research_portal worker --loglevel=info
```

## Configuration

### Database Configuration
Edit `research_portal/settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'your_database_name',
        'USER': 'your_database_user',
        'PASSWORD': 'your_database_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### Redis Configuration
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

### Email Configuration
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-specific-password'
```

## Testing

### Run Tests
```bash
python manage.py test
```

### Test Coverage
```bash
coverage run manage.py test
coverage report
```

## Deployment

### Production Setup
1. Configure Nginx as reverse proxy
2. Set up SSL/TLS certificates
3. Configure firewall rules
4. Set up backup system
5. Configure monitoring

### Docker Deployment
```bash
docker-compose up -d
```

## Troubleshooting

### Common Issues
1. Database connection errors
   - Check database credentials
   - Verify database is running
   - Check firewall rules

2. WebSocket connection failures
   - Verify Redis is running
   - Check WebSocket configuration
   - Check network connectivity

3. Performance issues
   - Monitor resource usage
   - Check database indexes
   - Review query performance

## Maintenance

### Regular Tasks
1. Database backups
2. Log rotation
3. System updates
4. Security patches
5. Performance monitoring

### Monitoring
1. System resource usage
2. Database performance
3. API response times
4. Error rates
5. User activity

## Security Considerations

### Best Practices
1. Regular security updates
2. Strong password policies
3. Two-factor authentication
4. Regular security audits
5. Secure file handling

## Support

For support, please:
1. Check the [Troubleshooting Guide](troubleshooting.md)
2. Review the [FAQ](faq.md)
3. Open an issue in the GitHub repository
4. Contact support team
